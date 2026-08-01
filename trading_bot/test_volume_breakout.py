import pandas as pd
import numpy as np
import sys, os

sys.path.insert(0, r'C:\Users\Pc\.gemini\antigravity\scratch\trading_bot')

from engine.data_fetcher import DataFetcher
from core.indicators import add_all_indicators, calculate_volume_profile

fetcher = DataFetcher()

def test_volume_breakout_quant(symbol="BTC/USDT", timeframe="1h", limit=1000):
    df = fetcher.fetch_ohlcv(symbol, timeframe, limit=limit)
    df_ind = add_all_indicators(df, {"ema_fast": 20, "ema_medium": 50, "ema_slow": 200})
    
    # Donchian Channels (20-period High / Low)
    lookback = 20
    df_ind["upper_channel"] = df_ind["high"].shift(1).rolling(window=lookback).max()
    df_ind["lower_channel"] = df_ind["low"].shift(1).rolling(window=lookback).min()
    df_ind["vol_ma"] = df_ind["volume"].rolling(window=20).mean()
    
    # Calculate POC
    vol_prof = calculate_volume_profile(df_ind)
    poc = vol_prof["poc"]
    
    signals = np.zeros(len(df_ind))
    
    for i in range(25, len(df_ind)):
        curr = df_ind.iloc[i]
        prev = df_ind.iloc[i-1]
        
        close = curr["close"]
        open_p = curr["open"]
        high = curr["high"]
        low = curr["low"]
        vol = curr["volume"]
        vol_ma = curr["vol_ma"]
        
        upper = curr["upper_channel"]
        lower = curr["lower_channel"]
        
        rsi = curr["rsi"]
        adx = curr["adx"]
        ema20 = curr["ema_20"]
        ema50 = curr["ema_50"]
        ema200 = curr["ema_200"]
        
        # 1. Breakout + Volume Spike (Vol >= 1.2x SMA) + ADX >= 22 + Above POC
        long_breakout = (close > upper) and (vol >= vol_ma * 1.15) and (adx >= 20) and (close > poc) and (close > ema200) and (rsi >= 52)
        short_breakout = (close < lower) and (vol >= vol_ma * 1.15) and (adx >= 20) and (close < poc) and (close < ema200) and (rsi <= 48)
        
        if long_breakout:
            signals[i] = 1
        elif short_breakout:
            signals[i] = -1

    # Backtest with 1:2.5 Risk/Reward Ratio & Tight Breakout Invalidation SL
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
        atr = float(curr["atr"]) if not np.isnan(curr["atr"]) else close * 0.015
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

        # Manage Open Position
        if position is not None:
            pos_type = position["type"]
            sl = position["sl"]
            tp = position["tp"]
            entry = position["entry"]
            risk_dist = position["risk_dist"]
            
            # Break-even at 1.0x Risk
            if pos_type == "LONG" and high >= entry + risk_dist:
                sl = max(sl, entry + (0.1 * risk_dist))
            elif pos_type == "SHORT" and low <= entry - risk_dist:
                sl = min(sl, entry - (0.1 * risk_dist))
                
            exit_price = None
            if pos_type == "LONG":
                if low <= sl: exit_price = sl
                elif high >= tp: exit_price = tp
            else:
                if high >= sl: exit_price = sl
                elif low <= tp: exit_price = tp
                
            if exit_price is not None:
                pnl = (exit_price - entry) * position["size_asset"] if pos_type == "LONG" else (entry - exit_price) * position["size_asset"]
                fee = (position["size_usd"] + (position["size_asset"] * exit_price)) * fee_pct
                net_pnl = pnl - fee
                balance += net_pnl
                trades.append(net_pnl)
                position = None

        if position is None and sig != 0:
            sl_dist = 1.5 * atr
            if sig == 1:
                sl = close - sl_dist
                tp = close + (sl_dist * 2.5) # 1:2.5 RR
            else:
                sl = close + sl_dist
                tp = close - (sl_dist * 2.5)
                
            risk_usd = balance * 0.015
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
    
    print(f"VOLUME BREAKOUT [{symbol:10s} | {timeframe:3s}] Trades: {total_trades:3d} | WinRate: {win_rate:5.1f}% | Net PnL: ${total_net_pnl:8.2f} | Return: {(total_net_pnl/initial_cap)*100:6.2f}% | PF: {pf:4.2f} | MaxDD: {max_dd:5.2f}%")

print("=== TESTING VOLUME PROFILE BREAKOUT STRATEGY ===")
for sym in ["SOL/USDT", "ETH/USDT", "BTC/USDT", "BNB/USDT"]:
    for tf in ["15m", "1h", "4h", "1d"]:
        test_volume_breakout_quant(sym, tf, 1000)
