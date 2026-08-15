import numpy as np
import pandas as pd

from core.indicators import add_all_indicators
from core.strategy_factory import build_strategy
from core.risk_manager import RiskManager


class PortfolioBacktester:
    """
    Multi-symbol backtesting engine with a single shared balance and a portfolio-
    level drawdown kill-switch - the scenario engine/backtester.py's single-symbol
    Backtester cannot represent, but that engine/testnet_trader.py actually runs in
    production (config["symbols"], one shared account_balance across every pair).

    Mirrors testnet_trader.py's capital-reservation accounting: opening a position
    reserves its position_size_usd out of the shared free-cash balance; closing one
    returns that capital plus net PnL. This is what makes concurrent, correlated
    exposure across symbols visible in results, instead of each symbol silently
    getting sized off the full account balance as if it were the only position open
    (which is what engine/backtester.py's single-symbol runs do, and why they never
    caught the sizing bug fixed in testnet_trader.py).
    """

    def __init__(self, config: dict):
        self.config = config
        self.strategy = build_strategy(config)
        self.risk_manager = RiskManager(config)
        self.fee_pct = float(config.get("fee_pct", 0.00075))
        self.slippage_pct = float(config.get("slippage_pct", 0.0005))
        self.max_drawdown_pct = float(config.get("max_drawdown_pct", 25.0))
        self.min_signal_strength = float(config.get("min_signal_strength", 4))
        self.min_notional_usd = float(config.get("min_notional_usd", 10.0))
        self.max_concurrent_positions = int(config.get("max_concurrent_positions", 3))
        self.funding_rate_pct_per_8h = float(config.get("funding_rate_pct_per_8h", 0.01)) / 100.0

    def _funding_cost(self, pos: dict, exit_timestamp) -> float:
        """Approximate funding paid over the life of a perpetual futures position."""
        entry_ts = pd.Timestamp(pos["entry_time"])
        exit_ts = pd.Timestamp(exit_timestamp)
        hours_held = max((exit_ts - entry_ts).total_seconds() / 3600.0, 0.0)
        periods = hours_held / 8.0
        return pos["position_size_usd"] * self.funding_rate_pct_per_8h * periods

    def run(self, dfs_by_symbol: dict) -> dict:
        """
        ``dfs_by_symbol``: {symbol: raw OHLCV DataFrame}, all on the same timeframe.
        Series are aligned by inner-joining on timestamp (Binance candles for
        different pairs on the same timeframe share open times), so every step of
        the simulation sees every symbol's candle for that same moment in time.
        """
        symbols = list(dfs_by_symbol.keys())
        signals_by_symbol = {}
        for symbol in symbols:
            config = self.config.copy()
            config["symbol"] = symbol
            df_ind = add_all_indicators(dfs_by_symbol[symbol].reset_index(drop=True), config)
            df_sig = self.strategy.generate_signals(df_ind)
            signals_by_symbol[symbol] = df_sig.set_index("timestamp")

        common_index = None
        for df_sig in signals_by_symbol.values():
            common_index = df_sig.index if common_index is None else common_index.intersection(df_sig.index)
        idx_list = list(common_index.sort_values())
        n = len(idx_list)

        initial_capital = float(self.config.get("initial_capital", 10000.0))
        balance = initial_capital
        peak_equity = balance
        max_drawdown = 0.0
        halted = False

        positions = {}
        trades = []
        equity_curve = []

        for i in range(n):
            ts = idx_list[i]
            rows = {s: signals_by_symbol[s].loc[ts] for s in symbols}

            # 1. Mark-to-market equity & portfolio kill-switch, evaluated once per
            # tick across every open position before any symbol's entries/exits are
            # processed - mirrors testnet_trader.check_market_and_execute. `balance`
            # is free cash only (see capital-reservation note above), so each
            # position contributes its reserved position_size_usd plus its floating
            # PnL to total equity, not just the floating PnL alone.
            current_equity = balance
            for s, pos in positions.items():
                price = float(rows[s]["close"])
                if pos["type"] == "LONG":
                    floating_pnl = (price - pos["entry_price"]) * pos["position_size_asset"]
                else:
                    floating_pnl = (pos["entry_price"] - price) * pos["position_size_asset"]
                current_equity += pos["position_size_usd"] + floating_pnl

            if current_equity > peak_equity:
                peak_equity = current_equity
            dd = (peak_equity - current_equity) / peak_equity * 100.0 if peak_equity > 0 else 0.0
            if dd > max_drawdown:
                max_drawdown = float(dd)
            if not halted and dd >= self.max_drawdown_pct:
                halted = True

            equity_curve.append({"timestamp": str(ts), "equity": round(float(current_equity), 2)})

            # 2-3. Manage each symbol's open position (SL/TP/trailing), then
            # evaluate new entries - same two-phase order as testnet_trader.py.
            for symbol in symbols:
                row = rows[symbol]
                close = float(row["close"])
                high = float(row["high"])
                low = float(row["low"])
                pos = positions.get(symbol)

                if pos is not None:
                    pos_type = pos["type"]
                    sl = pos["stop_loss"]
                    tp = pos["take_profit"]
                    exit_price = None
                    exit_reason = None

                    if pos_type == "LONG":
                        if low <= sl:
                            exit_price = sl * (1 - self.slippage_pct)
                            exit_reason = "Break-Even / Stop Loss" if sl > pos["entry_price"] else "Stop Loss"
                        elif high >= tp:
                            exit_price = tp
                            exit_reason = "Take Profit"
                    else:
                        if high >= sl:
                            exit_price = sl * (1 + self.slippage_pct)
                            exit_reason = "Break-Even / Stop Loss" if sl < pos["entry_price"] else "Stop Loss"
                        elif low <= tp:
                            exit_price = tp
                            exit_reason = "Take Profit"

                    if exit_price is None:
                        new_sl = self.risk_manager.update_trailing_stop(
                            close, pos["entry_price"], sl, 1 if pos_type == "LONG" else -1, pos["sl_distance"]
                        )
                        pos["stop_loss"] = float(new_sl)
                    else:
                        exit_price = float(exit_price)
                        if pos_type == "LONG":
                            pnl_gross = (exit_price - pos["entry_price"]) * pos["position_size_asset"]
                        else:
                            pnl_gross = (pos["entry_price"] - exit_price) * pos["position_size_asset"]
                        fee = (pos["position_size_usd"] + (pos["position_size_asset"] * exit_price)) * self.fee_pct
                        funding = self._funding_cost(pos, ts)
                        pnl_net = pnl_gross - fee - funding
                        # Return the reserved capital plus net PnL - see the class
                        # docstring on the shared balance representing free cash only.
                        balance += pos["position_size_usd"] + pnl_net

                        trades.append({
                            "id": len(trades) + 1,
                            "symbol": symbol,
                            "type": pos_type,
                            "entry_time": str(pos["entry_time"]),
                            "entry_price": round(float(pos["entry_price"]), 2),
                            "exit_time": str(ts),
                            "exit_price": round(exit_price, 2),
                            "size_usd": round(float(pos["position_size_usd"]), 2),
                            "pnl_usd": round(float(pnl_net), 2),
                            "pnl_pct": round(float(pnl_net / pos["position_size_usd"] * 100.0), 2),
                            "exit_reason": exit_reason,
                            "strength": int(pos["strength"]),
                        })
                        positions.pop(symbol, None)

                else:
                    signal = int(row["signal"])
                    strength = int(row["signal_strength"])
                    if (
                        not halted
                        and len(positions) < self.max_concurrent_positions
                        and signal != 0
                        and strength >= self.min_signal_strength
                        and i + 1 < n
                    ):
                        next_open = float(signals_by_symbol[symbol].loc[idx_list[i + 1], "open"])
                        fill_price = next_open * (1 + self.slippage_pct) if signal == 1 else next_open * (1 - self.slippage_pct)
                        atr = float(row["atr"]) if not np.isnan(row["atr"]) else close * 0.015
                        ema50 = float(row["ema_50"]) if "ema_50" in row and not np.isnan(row["ema_50"]) else None

                        levels = self.risk_manager.calculate_trade_levels(
                            entry_price=fill_price,
                            atr=atr,
                            signal_type=signal,
                            current_balance=balance,
                            ema50=ema50,
                        )

                        if levels["position_size_usd"] < self.min_notional_usd:
                            continue

                        positions[symbol] = {
                            "type": "LONG" if signal == 1 else "SHORT",
                            "entry_time": ts,
                            "entry_price": float(fill_price),
                            "stop_loss": float(levels["stop_loss"]),
                            "take_profit": float(levels["take_profit"]),
                            "sl_distance": float(levels["sl_distance"]),
                            "position_size_asset": float(levels["position_size_asset"]),
                            "position_size_usd": float(levels["position_size_usd"]),
                            "strength": strength,
                        }
                        balance = round(balance - levels["position_size_usd"], 2)

        # Mark any still-open positions to market at the last common close, so
        # final_balance/equity reflect them - but keep them out of win-rate/profit
        # factor, same reasoning as engine/backtester.py: a sample-end cutoff isn't
        # a genuine strategy exit.
        if positions and n > 0:
            last_ts = idx_list[-1]
            for symbol, pos in list(positions.items()):
                exit_price = float(signals_by_symbol[symbol].loc[last_ts, "close"])
                pos_type = pos["type"]
                if pos_type == "LONG":
                    pnl_gross = (exit_price - pos["entry_price"]) * pos["position_size_asset"]
                else:
                    pnl_gross = (pos["entry_price"] - exit_price) * pos["position_size_asset"]
                fee = (pos["position_size_usd"] + (pos["position_size_asset"] * exit_price)) * self.fee_pct
                funding = self._funding_cost(pos, last_ts)
                pnl_net = pnl_gross - fee - funding
                balance += pos["position_size_usd"] + pnl_net
                trades.append({
                    "id": len(trades) + 1,
                    "symbol": symbol,
                    "type": pos_type,
                    "entry_time": str(pos["entry_time"]),
                    "entry_price": round(float(pos["entry_price"]), 2),
                    "exit_time": str(last_ts),
                    "exit_price": round(exit_price, 2),
                    "size_usd": round(float(pos["position_size_usd"]), 2),
                    "pnl_usd": round(float(pnl_net), 2),
                    "pnl_pct": round(float(pnl_net / pos["position_size_usd"] * 100.0), 2),
                    "exit_reason": "Fin del Backtest (Posición Abierta)",
                    "strength": int(pos["strength"]),
                })
            positions = {}

        realized_trades = [t for t in trades if t["exit_reason"] != "Fin del Backtest (Posición Abierta)"]
        total_trades = len(realized_trades)
        winning_trades = [t for t in realized_trades if t["pnl_usd"] > 0]
        losing_trades = [t for t in realized_trades if t["pnl_usd"] <= 0]
        win_rate = (len(winning_trades) / total_trades * 100.0) if total_trades > 0 else 0.0

        total_profit = sum(t["pnl_usd"] for t in winning_trades)
        total_loss = abs(sum(t["pnl_usd"] for t in losing_trades))
        profit_factor = (total_profit / total_loss) if total_loss > 0 else (total_profit if total_profit > 0 else 0.0)

        total_net_pnl = balance - initial_capital
        total_return_pct = (total_net_pnl / initial_capital) * 100.0 if initial_capital > 0 else 0.0

        if len(realized_trades) > 1 and n > 1:
            returns = [t["pnl_pct"] for t in realized_trades]
            std_dev = float(np.std(returns))
            span_days = (idx_list[-1] - idx_list[0]).total_seconds() / 86400.0
            trades_per_year = (total_trades / (span_days / 365.25)) if span_days > 0 else 0.0
            sharpe_ratio = float(np.mean(returns) / std_dev * np.sqrt(trades_per_year)) if std_dev > 0 and trades_per_year > 0 else 0.0
        else:
            sharpe_ratio = 0.0

        trades_by_symbol = {}
        for t in realized_trades:
            trades_by_symbol.setdefault(t["symbol"], []).append(t)

        return {
            "summary": {
                "symbols": symbols,
                "initial_capital": round(float(initial_capital), 2),
                "final_balance": round(float(balance), 2),
                "total_net_pnl": round(float(total_net_pnl), 2),
                "total_return_pct": round(float(total_return_pct), 2),
                "total_trades": int(total_trades),
                "winning_trades": int(len(winning_trades)),
                "losing_trades": int(len(losing_trades)),
                "win_rate": round(float(win_rate), 2),
                "profit_factor": round(float(profit_factor), 2),
                "gross_profit": round(float(total_profit), 2),
                "gross_loss": round(float(total_loss), 2),
                "max_drawdown": round(float(max_drawdown), 2),
                "sharpe_ratio": round(float(sharpe_ratio), 2),
                "kill_switch_triggered": bool(halted),
                "trades_per_symbol": {s: len(trades_by_symbol.get(s, [])) for s in symbols},
            },
            "trades": trades,
            "equity_curve": equity_curve,
        }
