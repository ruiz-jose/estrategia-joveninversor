import pandas as pd
import numpy as np
import sys, os

sys.path.insert(0, r'C:\Users\Pc\.gemini\antigravity\scratch\trading_bot')

from engine.data_fetcher import DataFetcher
from core.indicators import calculate_ema, calculate_atr

fetcher = DataFetcher()

def calculate_supertrend(df, period=10, multiplier=3.0):
    df = df.copy()
    atr = calculate_atr(df, period)
    
    hl2 = (df["high"] + df["low"]) / 2
    basic_ub = hl2 + (multiplier * atr)
    basic_lb = hl2 - (multiplier * atr)
    
    final_ub = np.zeros(len(df))
    final_lb = np.zeros(len(df))
    supertrend = np.zeros(len(df))
    direction = np.zeros(len(df))
    
    for i in range(1, len(df)):
        if basic_ub.iloc[i] < final_ub[i-1] or df["close"].iloc[i-1] > final_ub[i-1]:
            final_ub[i] = basic_ub.iloc[i]
        else:
            final_ub[i] = final_ub[i-1]
            
        if basic_lb.iloc[i] > final_lb[i-1] or df["close"].iloc[i-1] < final_lb[i-1]:
            final_lb[i] = basic_lb.iloc[i]
        else:
            final_lb[i] = final_lb[i-1]
            
        if direction[i-1] == 1:
            if df["close"].iloc[i] < final_lb[i]:
                direction[i] = -1
                supertrend[i] = final_ub[i]
            else:
                direction[i] = 1
                supertrend[i] = final_lb[i]
        else:
            if df["close"].iloc[i] > final_ub[i]:
                direction[i] = 1
                supertrend[i] = final_lb[i]
            else:
                direction[i] = -1
                supertrend[i] = final_ub[i]
                
    df["supertrend"] = supertrend
    df["st_direction"] = direction
    return df

def test_supertrend_bot(symbol="SOL/USDT", timeframe="1h", limit=1000, atr_period=10, mult=3.0, rr=2.0):
    df = fetcher.fetch_ohlcv(symbol, timeframe, limit=limit)
    df["ema_200"] = calculate_ema(df, 200)
    df["atr"] = calculate_atr(df, 14)
    df = calculate_supertrend(df, period=atr_period, multiplier=mult)
    
    signals = np.zeros(len(df))
    for i in range(200, len(df)):
        close = df["close"].iloc[i]
        ema200 = df["ema_200"].iloc[i]
        st_dir = df["st_direction"].iloc[i]
        st_dir_prev = df["st_direction"].iloc[i-1]
        
        # Signal on Supertrend flip in alignment with EMA 200
        if st_dir == 1 and st_dir_prev == -1 and close > ema200:
            signals[i] = 1
        elif st_dir == -1 and st_dir_prev == 1 and close < ema200:
            signals[i] = -1
            
    # Backtest
    initial_cap = 10000.0
    balance = initial_cap
    peak = balance
    max_dd = 0.0
    trades = []
    position = None
    fee_pct = 0.00075
    
    for i in range(len(df)):
        curr = df.iloc[i]
        close = float(curr["close"])
        high = float(curr["high"])
        low = float(curr["low"])
        atr = float(curr["atr"]) if not np.isnan(curr["atr"]) else close * 0.015
        st_val = float(curr["supertrend"])
        sig = int(signals[i])
        
        equity = balance
        if position is not None:
            if position["type"] == "LONG":
                unrealized = (close - position["entry"]) * position["size_asset"]
            else:
                unrealized = (position["entry"] - close) * position["size_asset"]
            equity += unrealized
            
        if equity > peak: peak = equity
        dd = (peak - equity) / peak * 100.0 if peak > 0 else 0
        if dd > max_dd: max_dd = dd

        # Position Exit Check (Exit on Supertrend reversal OR TP)
        if position is not None:
            pos_type = position["type"]
            sl = position["sl"]
            tp = position["tp"]
            entry = position["entry"]
            
            exit_price = None
            if pos_type == "LONG":
                if low <= sl: exit_price = sl
                elif high >= tp: exit_price = tp
                elif curr["st_direction"] == -1: exit_price = close # Exit on ST Flip
            else:
                if high >= sl: exit_price = sl
                elif low <= tp: exit_price = tp
                elif curr["st_direction"] == 1: exit_price = close
                
            if exit_price is not None:
                pnl = (exit_price - entry) * position["size_asset"] if pos_type == "LONG" else (entry - exit_price) * position["size_asset"]
                fee = (position["size_usd"] + (position["size_asset"] * exit_price)) * fee_pct
                net_pnl = pnl - fee
                balance += net_pnl
                trades.append(net_pnl)
                position = None

        if position is None and sig != 0:
            sl_dist = abs(close - st_val)
            if sl_dist < close * 0.005: sl_dist = close * 0.015 # Min 1.5% SL
            
            if sig == 1:
                sl = close - sl_dist
                tp = close + (sl_dist * rr)
            else:
                sl = close + sl_dist
                tp = close - (sl_dist * rr)
                
            risk_usd = balance * 0.02 # 2% Risk
            size_asset = risk_usd / sl_dist
            
            position = {
                "type": "LONG" if sig == 1 else "SHORT",
                "entry": close,
                "sl": sl,
                "tp": tp,
                "risk_dist": sl_dist,
                "size_asset": size_asset,
                "size_usd": size_asset * close
            }

    wins = [t for t in trades if t > 0]
    total_trades = len(trades)
    win_rate = (len(wins) / total_trades * 100) if total_trades > 0 else 0
    total_net_pnl = balance - initial_cap
    tot_profit = sum(wins)
    tot_loss = abs(sum([t for t in trades if t <= 0]))
    pf = (tot_profit / tot_loss) if tot_loss > 0 else 0
    
    print(f"SUPERTREND BOT [{symbol:10s} | {timeframe:3s}] Trades: {total_trades:3d} | WinRate: {win_rate:5.1f}% | Net PnL: ${total_net_pnl:8.2f} | Return: {(total_net_pnl/initial_cap)*100:6.2f}% | PF: {pf:4.2f} | MaxDD: {max_dd:5.2f}%")

print("=== TESTING SUPERTREND + EMA 200 QUANT STRATEGY ===")
for sym in ["SOL/USDT", "ETH/USDT", "BTC/USDT", "BNB/USDT"]:
    for tf in ["1h", "4h", "1d"]:
        test_supertrend_bot(sym, tf, 1000, 10, 3.0, 2.5)
