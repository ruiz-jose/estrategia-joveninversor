import pandas as pd
import numpy as np
from core.indicators import add_all_indicators, calculate_volume_profile
from core.strategy import Strategy
from core.risk_manager import RiskManager

class Backtester:
    """
    Backtesting Engine for Joven Inversor Strategy.
    Simulates trades with realistic execution, SL/TP, Break-Even trailing stop, and fee modeling.
    """
    
    def __init__(self, config: dict):
        self.config = config
        self.strategy = Strategy(config)
        self.risk_manager = RiskManager(config)
        self.fee_pct = float(config.get("fee_pct", 0.00075))
        self.slippage_pct = float(config.get("slippage_pct", 0.0005))
        # Perpetual futures funding (charged/paid every 8h on position notional) was
        # previously unmodeled here, so historical PF/return figures never reflected
        # a cost the live futures bot actually pays. Binance funding rates float and
        # can be negative, but default to a small positive cost as a conservative
        # (not overstating profitability) approximation absent fetched historical
        # rate data - see core/risk_manager or config.py for the knob.
        self.funding_rate_pct_per_8h = float(config.get("funding_rate_pct_per_8h", 0.01)) / 100.0
        self.max_drawdown_pct = float(config.get("max_drawdown_pct", 25.0))
        self.min_signal_strength = float(config.get("min_signal_strength", 4))
        self.min_notional_usd = float(config.get("min_notional_usd", 10.0))

    def _funding_cost(self, position: dict, exit_timestamp: str) -> float:
        """Approximate funding paid over the life of a perpetual futures position."""
        entry_ts = pd.Timestamp(position["entry_time"])
        exit_ts = pd.Timestamp(exit_timestamp)
        hours_held = max((exit_ts - entry_ts).total_seconds() / 3600.0, 0.0)
        periods = hours_held / 8.0
        return position["position_size_usd"] * self.funding_rate_pct_per_8h * periods

    def run(self, df: pd.DataFrame, indicator_warmup_df: pd.DataFrame | None = None) -> dict:
        """Run the simulation, optionally warming indicators with prior candles.

        ``indicator_warmup_df`` is used only to establish indicator state; no trade
        can be opened or closed during those candles.  This lets out-of-sample
        tests retain the information that would be available in a live run.
        """
        warmup_len = 0
        if indicator_warmup_df is not None and not indicator_warmup_df.empty:
            warmup_len = len(indicator_warmup_df)
            source_df = pd.concat([indicator_warmup_df, df], ignore_index=True)
        else:
            source_df = df.reset_index(drop=True)

        df_ind = add_all_indicators(source_df, self.config)
        df_sig = self.strategy.generate_signals(df_ind).iloc[warmup_len:].reset_index(drop=True)
        
        initial_capital = float(self.config.get("initial_capital", 10000.0))
        balance = initial_capital
        peak_balance = balance
        max_drawdown = 0.0
        
        position = None
        trades = []
        equity_curve = []
        halted = False
        halted_at_trade = None

        for i in range(len(df_sig)):
            curr = df_sig.iloc[i]
            timestamp = str(curr["timestamp"])
            close = float(curr["close"])
            high = float(curr["high"])
            low = float(curr["low"])
            ema50 = float(curr["ema_50"]) if "ema_50" in curr and not np.isnan(curr["ema_50"]) else None
            atr = float(curr["atr"]) if not np.isnan(curr["atr"]) else close * 0.015
            signal = int(curr["signal"])
            strength = int(curr["signal_strength"])
            reason = str(curr["reason"])
            
            # Record current equity
            current_equity = balance
            if position is not None:
                if position["type"] == "LONG":
                    unrealized_pnl = (close - position["entry_price"]) * position["position_size_asset"]
                else:
                    unrealized_pnl = (position["entry_price"] - close) * position["position_size_asset"]
                current_equity += unrealized_pnl
                
            equity_curve.append({
                "timestamp": timestamp,
                "equity": round(float(current_equity), 2),
                "close": round(close, 2)
            })
            
            if current_equity > peak_balance:
                peak_balance = current_equity
            dd = (peak_balance - current_equity) / peak_balance * 100.0 if peak_balance > 0 else 0.0
            if dd > max_drawdown:
                max_drawdown = float(dd)
            if not halted and dd >= self.max_drawdown_pct:
                halted = True
                halted_at_trade = len(trades)

            # 1. Manage Active Position
            if position is not None:
                pos_type = position["type"]
                sl = position["stop_loss"]
                tp = position["take_profit"]

                # Check SL/TP against the stop as it stood entering this candle.
                # The break-even adjustment below is computed from this candle's
                # close, which isn't known until the candle ends, so it must not
                # retroactively protect against this same candle's high/low.
                exit_price = None
                exit_reason = None

                if pos_type == "LONG":
                    if low <= sl:
                        exit_price = sl * (1 - self.slippage_pct)
                        exit_reason = "Break-Even / Stop Loss" if sl > position["entry_price"] else "Stop Loss"
                    elif high >= tp:
                        exit_price = tp
                        exit_reason = "Take Profit"
                elif pos_type == "SHORT":
                    if high >= sl:
                        exit_price = sl * (1 + self.slippage_pct)
                        exit_reason = "Break-Even / Stop Loss" if sl < position["entry_price"] else "Stop Loss"
                    elif low <= tp:
                        exit_price = tp
                        exit_reason = "Take Profit"

                if exit_price is None:
                    # Not stopped/hit-target this candle: tighten the stop for
                    # future candles using this candle's close.
                    new_sl = self.risk_manager.update_trailing_stop(
                        close, position["entry_price"], sl, 1 if pos_type == "LONG" else -1, position["sl_distance"]
                    )
                    position["stop_loss"] = float(new_sl)

                # Close Trade if trigger hit
                if exit_price is not None:
                    exit_price = float(exit_price)
                    if pos_type == "LONG":
                        pnl_gross = (exit_price - position["entry_price"]) * position["position_size_asset"]
                    else:
                        pnl_gross = (position["entry_price"] - exit_price) * position["position_size_asset"]
                        
                    fee = (position["position_size_usd"] + (position["position_size_asset"] * exit_price)) * self.fee_pct
                    funding = self._funding_cost(position, timestamp)
                    pnl_net = pnl_gross - fee - funding
                    balance += pnl_net

                    trades.append({
                        "id": len(trades) + 1,
                        "symbol": self.config.get("symbol", "N/A"),
                        "type": pos_type,
                        "entry_time": str(position["entry_time"]),
                        "entry_price": round(float(position["entry_price"]), 2),
                        "exit_time": timestamp,
                        "exit_price": round(float(exit_price), 2),
                        "stop_loss": round(float(position["stop_loss"]), 2),
                        "take_profit": round(float(position["take_profit"]), 2),
                        "size_usd": round(float(position["position_size_usd"]), 2),
                        "pnl_usd": round(float(pnl_net), 2),
                        "pnl_pct": round(float((pnl_net / position["position_size_usd"]) * 100.0), 2),
                        "exit_reason": exit_reason,
                        "strength": int(position["strength"])
                    })
                    position = None

            # 2. Check for New Signal
            if not halted and position is None and signal != 0 and strength >= self.min_signal_strength:
                if i + 1 >= len(df_sig):
                    continue  # no next candle to fill on
                next_open = float(df_sig.iloc[i + 1]["open"])
                fill_price = next_open * (1 + self.slippage_pct) if signal == 1 else next_open * (1 - self.slippage_pct)
                levels = self.risk_manager.calculate_trade_levels(
                    entry_price=fill_price,
                    atr=atr,
                    signal_type=signal,
                    current_balance=balance,
                    ema50=ema50
                )

                # Skip entries too small to actually place on the exchange -
                # a position the backtest can't have really executed
                # shouldn't count as validated evidence either.
                if levels["position_size_usd"] < self.min_notional_usd:
                    continue

                position = {
                    "type": "LONG" if signal == 1 else "SHORT",
                    "entry_time": timestamp,
                    "entry_price": float(fill_price),
                    "stop_loss": float(levels["stop_loss"]),
                    "take_profit": float(levels["take_profit"]),
                    "sl_distance": float(levels["sl_distance"]),
                    "position_size_asset": float(levels["position_size_asset"]),
                    "position_size_usd": float(levels["position_size_usd"]),
                    "strength": strength,
                    "reason": reason
                }

        # If a position is still open when the sample ends, mark it to market
        # at the last close instead of silently dropping its P&L from the
        # summary (final_balance/win_rate/profit_factor previously ignored it).
        if position is not None and len(df_sig) > 0:
            last = df_sig.iloc[-1]
            exit_price = float(last["close"])
            pos_type = position["type"]
            if pos_type == "LONG":
                pnl_gross = (exit_price - position["entry_price"]) * position["position_size_asset"]
            else:
                pnl_gross = (position["entry_price"] - exit_price) * position["position_size_asset"]

            fee = (position["position_size_usd"] + (position["position_size_asset"] * exit_price)) * self.fee_pct
            funding = self._funding_cost(position, str(last["timestamp"]))
            pnl_net = pnl_gross - fee - funding
            balance += pnl_net

            trades.append({
                "id": len(trades) + 1,
                "symbol": self.config.get("symbol", "N/A"),
                "type": pos_type,
                "entry_time": str(position["entry_time"]),
                "entry_price": round(float(position["entry_price"]), 2),
                "exit_time": str(last["timestamp"]),
                "exit_price": round(exit_price, 2),
                "stop_loss": round(float(position["stop_loss"]), 2),
                "take_profit": round(float(position["take_profit"]), 2),
                "size_usd": round(float(position["position_size_usd"]), 2),
                "pnl_usd": round(float(pnl_net), 2),
                "pnl_pct": round(float((pnl_net / position["position_size_usd"]) * 100.0), 2),
                "exit_reason": "Fin del Backtest (Posición Abierta)",
                "strength": int(position["strength"])
            })
            position = None

        # Calculate Summary Metrics.
        # Trades closed only because the sample ran out (exit_reason == "Fin
        # del Backtest (Posición Abierta)") are real for equity/balance
        # purposes (the mark-to-market above is legitimate), but they are not
        # genuine SL/TP/strategy exits - counting them in win_rate/profit
        # factor lets an arbitrary window cutoff manufacture "wins" or
        # "losses" that had nothing to do with the strategy's edge.
        realized_trades = [t for t in trades if t["exit_reason"] != "Fin del Backtest (Posición Abierta)"]

        total_trades = len(realized_trades)
        winning_trades = [t for t in realized_trades if t["pnl_usd"] > 0]
        losing_trades = [t for t in realized_trades if t["pnl_usd"] <= 0]

        win_rate = (len(winning_trades) / total_trades * 100.0) if total_trades > 0 else 0.0

        total_profit = sum([t["pnl_usd"] for t in winning_trades])
        total_loss = abs(sum([t["pnl_usd"] for t in losing_trades]))
        profit_factor = (total_profit / total_loss) if total_loss > 0 else (total_profit if total_profit > 0 else 0.0)

        total_net_pnl = balance - initial_capital
        total_return_pct = (total_net_pnl / initial_capital) * 100.0

        if len(realized_trades) > 1 and len(df_sig) > 1:
            returns = [t["pnl_pct"] for t in realized_trades]
            std_dev = float(np.std(returns))
            span_days = (pd.Timestamp(df_sig.iloc[-1]["timestamp"]) - pd.Timestamp(df_sig.iloc[0]["timestamp"])).total_seconds() / 86400.0
            trades_per_year = (total_trades / (span_days / 365.25)) if span_days > 0 else 0.0
            sharpe_ratio = float((np.mean(returns) / std_dev * np.sqrt(trades_per_year))) if std_dev > 0 and trades_per_year > 0 else 0.0
        else:
            sharpe_ratio = 0.0
            
        vol_profile = calculate_volume_profile(df_sig)

        candles_records = []
        for row in df_sig.tail(200).to_dict(orient="records"):
            c_dict = {}
            for k, v in row.items():
                if isinstance(v, (np.floating, float)):
                    c_dict[k] = round(float(v), 4) if not np.isnan(v) else None
                elif isinstance(v, (np.integer, int)):
                    c_dict[k] = int(v)
                elif isinstance(v, (bool, np.bool_)):
                    c_dict[k] = bool(v)
                elif isinstance(v, pd.Timestamp):
                    c_dict[k] = str(v)
                else:
                    c_dict[k] = str(v) if v is not None else None
            candles_records.append(c_dict)

        return {
            "summary": {
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
                "kill_switch_at_trade": halted_at_trade,
                "volume_profile": vol_profile
            },
            "trades": trades,
            "equity_curve": equity_curve,
            "candles": candles_records
        }
