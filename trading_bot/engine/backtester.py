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
        
    def run(self, df: pd.DataFrame) -> dict:
        df_ind = add_all_indicators(df, self.config)
        df_sig = self.strategy.generate_signals(df_ind)
        
        initial_capital = float(self.config.get("initial_capital", 10000.0))
        balance = initial_capital
        peak_balance = balance
        max_drawdown = 0.0
        
        position = None
        trades = []
        equity_curve = []
        
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

            # 1. Manage Active Position
            if position is not None:
                pos_type = position["type"]
                sl = position["stop_loss"]
                tp = position["take_profit"]
                sl_dist = position["sl_distance"]
                
                # Check Break-Even Trailing Stop adjustment
                new_sl = self.risk_manager.update_trailing_stop(
                    close, position["entry_price"], sl, 1 if pos_type == "LONG" else -1, sl_dist
                )
                position["stop_loss"] = float(new_sl)
                sl = position["stop_loss"]
                
                exit_price = None
                exit_reason = None
                
                if pos_type == "LONG":
                    if low <= sl:
                        exit_price = sl
                        exit_reason = "Break-Even / Stop Loss" if sl > position["entry_price"] else "Stop Loss"
                    elif high >= tp:
                        exit_price = tp
                        exit_reason = "Take Profit"
                elif pos_type == "SHORT":
                    if high >= sl:
                        exit_price = sl
                        exit_reason = "Break-Even / Stop Loss" if sl < position["entry_price"] else "Stop Loss"
                    elif low <= tp:
                        exit_price = tp
                        exit_reason = "Take Profit"
                        
                # Close Trade if trigger hit
                if exit_price is not None:
                    exit_price = float(exit_price)
                    if pos_type == "LONG":
                        pnl_gross = (exit_price - position["entry_price"]) * position["position_size_asset"]
                    else:
                        pnl_gross = (position["entry_price"] - exit_price) * position["position_size_asset"]
                        
                    fee = (position["position_size_usd"] + (position["position_size_asset"] * exit_price)) * self.fee_pct
                    pnl_net = pnl_gross - fee
                    balance += pnl_net
                    
                    trades.append({
                        "id": len(trades) + 1,
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
            if position is None and signal != 0 and strength >= 3:
                levels = self.risk_manager.calculate_trade_levels(
                    entry_price=close,
                    atr=atr,
                    signal_type=signal,
                    current_balance=balance,
                    ema50=ema50
                )
                
                position = {
                    "type": "LONG" if signal == 1 else "SHORT",
                    "entry_time": timestamp,
                    "entry_price": float(close),
                    "stop_loss": float(levels["stop_loss"]),
                    "take_profit": float(levels["take_profit"]),
                    "sl_distance": float(levels["sl_distance"]),
                    "position_size_asset": float(levels["position_size_asset"]),
                    "position_size_usd": float(levels["position_size_usd"]),
                    "strength": strength,
                    "reason": reason
                }

        # Calculate Summary Metrics
        total_trades = len(trades)
        winning_trades = [t for t in trades if t["pnl_usd"] > 0]
        losing_trades = [t for t in trades if t["pnl_usd"] <= 0]
        
        win_rate = (len(winning_trades) / total_trades * 100.0) if total_trades > 0 else 0.0
        
        total_profit = sum([t["pnl_usd"] for t in winning_trades])
        total_loss = abs(sum([t["pnl_usd"] for t in losing_trades]))
        profit_factor = (total_profit / total_loss) if total_loss > 0 else (total_profit if total_profit > 0 else 0.0)
        
        total_net_pnl = balance - initial_capital
        total_return_pct = (total_net_pnl / initial_capital) * 100.0
        
        if len(trades) > 1:
            returns = [t["pnl_pct"] for t in trades]
            std_dev = float(np.std(returns))
            sharpe_ratio = float((np.mean(returns) / std_dev * np.sqrt(252))) if std_dev > 0 else 0.0
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
                "max_drawdown": round(float(max_drawdown), 2),
                "sharpe_ratio": round(float(sharpe_ratio), 2),
                "volume_profile": vol_profile
            },
            "trades": trades,
            "equity_curve": equity_curve,
            "candles": candles_records
        }
