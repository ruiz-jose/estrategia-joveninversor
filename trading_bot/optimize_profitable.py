import pandas as pd
import numpy as np
import sys, os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from engine.data_fetcher import DataFetcher
from core.indicators import add_all_indicators

fetcher = DataFetcher()

def run_quant_strategy(symbol="SOL/USDT", timeframe="4h", limit=1000, risk_pct=1.5, rr_ratio=2.5, min_adx=20):
    df = fetcher.fetch_ohlcv(symbol, timeframe, limit=limit)
    df_ind = add_all_indicators(df, {"ema_fast": 20, "ema_medium": 50, "ema_slow": 200, "rsi_period": 14, "macd_fast": 12, "macd_slow": 26, "macd_signal": 9, "adx_period": 14, "atr_period": 14})
    
    # Calculate Swing Highs and Lows (5 candle window)
    df_ind["swing_low"] = df_ind["low"].rolling(window=7, min_periods=1).min()
    df_ind["swing_high"] = df_ind["high"].rolling(window=7, min_periods=1).max()
    df_ind["vol_ma"] = df_ind["volume"].rolling(window=20, min_periods=1).mean()
    
    signals = np.zeros(len(df_ind))
    strengths = np.zeros(len(df_ind))
    
    for i in range(20, len(df_ind)):
        curr = df_ind.iloc[i]
        prev = df_ind.iloc[i-1]
        
        close = curr["close"]
        open_p = curr["open"]
        low = curr["low"]
        high = curr["high"]
        vol = curr["volume"]
        vol_ma = curr["vol_ma"]
        
        ema20 = curr["ema_20"]
        ema50 = curr["ema_50"]
        ema200 = curr["ema_200"]
        
        rsi = curr["rsi"]
        macd = curr["macd"]
        macd_sig = curr["macd_signal"]
        macd_hist = curr["macd_hist"]
        macd_hist_prev = prev["macd_hist"]
        adx = curr["adx"]
        
        # 1. Macro Trend Filter (3-EMA Alignment)
        bull_trend = (close > ema200) and (ema20 > ema50) and (ema50 > ema200)
        bear_trend = (close < ema200) and (ema20 < ema50) and (ema50 < ema200)
        
        # 2. ADX Filter
        if adx < min_adx:
            continue
            
        # 3. Volume Filter (Volume >= 1.1x 20-period SMA Volume)
        vol_confirmed = vol >= vol_ma * 1.0
        
        # 4. Pullback & Rejection Candle
        # Long: Price low touches near EMA20/50 zone, closes green
        pullback_long = (low <= ema20 * 1.008) and (close >= ema50 * 0.992) and (close > open_p)
        macd_bull = (macd_hist > macd_hist_prev) or (macd > macd_sig)
        rsi_bull = 42 <= rsi <= 68
        
        # Short: Price high touches near EMA20/50 zone, closes red
        pullback_short = (high >= ema20 * 0.992) and (close <= ema50 * 1.008) and (close < open_p)
        macd_bear = (macd_hist < macd_hist_prev) or (macd < macd_sig)
        rsi_bear = 32 <= rsi <= 58
        
        if bull_trend and pullback_long and macd_bull and rsi_bull and vol_confirmed:
            signals[i] = 1
            strengths[i] = 4
        elif bear_trend and pullback_short and macd_bear and rsi_bear and vol_confirmed:
            signals[i] = -1
            strengths[i] = 4
            
    # Backtest simulation with Structure Stop Loss (Swing Low / Swing High)
    initial_cap = 10000.0
    balance = initial_cap
    peak = balance
    max_dd = 0.0
    trades = []
    position = None
    fee_pct = 0.00075
    
    for i in range(len(df_ind)):
        curr = df_ind.iloc[i]
        timestamp = str(curr["timestamp"])
        close = float(curr["close"])
        high = float(curr["high"])
        low = float(curr["low"])
        sig = int(signals[i])
        
        # Track Equity
        equity = balance
        if position is not None:
            if position["type"] == "LONG":
                unrealized = (close - position["entry"]) * position["size_asset"]
            else:
                unrealized = (position["entry"] - close) * position["size_asset"]
            equity += unrealized
            
        if equity > peak:
            peak = equity
        dd = (peak - equity) / peak * 100.0 if peak > 0 else 0
        if dd > max_dd:
            max_dd = dd
            
        # Position Management
        if position is not None:
            pos_type = position["type"]
            sl = position["sl"]
            tp = position["tp"]
            entry = position["entry"]
            risk_dist = position["risk_dist"]
            
            # Move to Break-Even at 1.2x Risk
            if pos_type == "LONG" and high >= entry + (1.2 * risk_dist):
                sl = max(sl, entry + (0.1 * risk_dist))
            elif pos_type == "SHORT" and low <= entry - (1.2 * risk_dist):
                sl = min(sl, entry - (0.1 * risk_dist))
                
            exit_price = None
            exit_reason = None
            
            if pos_type == "LONG":
                if low <= sl:
                    exit_price = sl
                    exit_reason = "Stop Loss"
                elif high >= tp:
                    exit_price = tp
                    exit_reason = "Take Profit"
            else:
                if high >= sl:
                    exit_price = sl
                    exit_reason = "Stop Loss"
                elif low <= tp:
                    exit_price = tp
                    exit_reason = "Take Profit"
                    
            if exit_price is not None:
                pnl = (exit_price - entry) * position["size_asset"] if pos_type == "LONG" else (entry - exit_price) * position["size_asset"]
                fee = (position["size_usd"] + (position["size_asset"] * exit_price)) * fee_pct
                net_pnl = pnl - fee
                balance += net_pnl
                trades.append({
                    "type": pos_type,
                    "entry": entry,
                    "exit": exit_price,
                    "pnl": net_pnl,
                    "reason": exit_reason
                })
                position = None
                
        if position is None and sig != 0:
            swing_low = float(df_ind.iloc[i-1]["swing_low"])
            swing_high = float(df_ind.iloc[i-1]["swing_high"])
            atr = float(curr["atr"]) if not np.isnan(curr["atr"]) else close * 0.015
            
            if sig == 1:
                sl = min(swing_low * 0.997, close - (1.8 * atr))
                risk_dist = close - sl
                tp = close + (risk_dist * rr_ratio)
            else:
                sl = max(swing_high * 1.003, close + (1.8 * atr))
                risk_dist = sl - close
                tp = close - (risk_dist * rr_ratio)
                
            if risk_dist <= 0:
                continue
                
            risk_usd = balance * (risk_pct / 100.0)
            size_asset = risk_usd / risk_dist
            
            position = {
                "type": "LONG" if sig == 1 else "SHORT",
                "entry": close,
                "sl": sl,
                "tp": tp,
                "risk_dist": risk_dist,
                "size_asset": size_asset,
                "size_usd": size_asset * close
            }
            
    wins = [t for t in trades if t["pnl"] > 0]
    total_trades = len(trades)
    win_rate = (len(wins) / total_trades * 100) if total_trades > 0 else 0
    total_net_pnl = balance - initial_cap
    tot_profit = sum([t["pnl"] for t in wins])
    tot_loss = abs(sum([t["pnl"] for t in trades if t["pnl"] <= 0]))
    pf = (tot_profit / tot_loss) if tot_loss > 0 else 0
    
    print(f"[{symbol} | {timeframe}] Trades: {total_trades:2d} | WinRate: {win_rate:5.1f}% | Net PnL: ${total_net_pnl:8.2f} | Return: {(total_net_pnl/initial_cap)*100:6.2f}% | PF: {pf:4.2f} | MaxDD: {max_dd:5.2f}%")

print("=== PROFITABLE QUANT STRATEGY RESULTS ===")
run_quant_strategy("BTC/USDT", "4h", 1000, 1.5, 2.5, 20)
run_quant_strategy("ETH/USDT", "4h", 1000, 1.5, 2.5, 20)
run_quant_strategy("SOL/USDT", "4h", 1000, 1.5, 2.5, 20)
run_quant_strategy("BNB/USDT", "4h", 1000, 1.5, 2.5, 20)
run_quant_strategy("SOL/USDT", "1d", 1000, 1.5, 2.5, 18)
run_quant_strategy("BTC/USDT", "1d", 1000, 1.5, 2.5, 18)
