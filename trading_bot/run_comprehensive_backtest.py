import sys
import os
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from engine.data_fetcher import DataFetcher
from engine.backtester import Backtester
from config import DEFAULT_CONFIG
from core.indicators import add_all_indicators
from core.strategy import Strategy

fetcher = DataFetcher()

def evaluate_default_strategy():
    print("=========================================================================", flush=True)
    print(" 1. ESTRATEGIA BASE DEFAULT (EMA 20/50/200 + RSI + MACD + ADX Squeeze)", flush=True)
    print("=========================================================================", flush=True)
    print(f"{'SYMBOL':10s} | {'TF':4s} | {'TRADES':6s} | {'WIN RATE':8s} | {'NET PnL ($)':12s} | {'RETURN %':9s} | {'PROFIT FACTOR':13s} | {'MAX DD %':8s}", flush=True)
    print("-" * 85, flush=True)
    
    symbols = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT']
    timeframes = ['15m', '1h', '4h', '1d']
    
    results = []
    for sym in symbols:
        for tf in timeframes:
            try:
                df = fetcher.fetch_ohlcv(sym, tf, limit=500)
                bt = Backtester(DEFAULT_CONFIG)
                res = bt.run(df)
                s = res['summary']
                results.append((sym, tf, s))
                print(f"{sym:10s} | {tf:4s} | {s['total_trades']:6d} | {s['win_rate']:7.1f}% | ${s['total_net_pnl']:11.2f} | {s['total_return_pct']:8.2f}% | {s['profit_factor']:13.2f} | {s['max_drawdown']:7.2f}%")
            except Exception as e:
                print(f"Error {sym} {tf}: {e}")
    print()
    return results

def test_adaptive_bot(symbol="BTC/USDT", timeframe="1h", limit=500):
    df = fetcher.fetch_ohlcv(symbol, timeframe, limit=limit)
    df_ind = add_all_indicators(df, {"ema_fast": 20, "ema_medium": 50, "ema_slow": 200})
    
    bb_len = 20
    df_ind["bb_sma"] = df_ind["close"].rolling(window=bb_len).mean()
    df_ind["bb_std"] = df_ind["close"].rolling(window=bb_len).std()
    df_ind["bb_upper"] = df_ind["bb_sma"] + 2.0 * df_ind["bb_std"]
    df_ind["bb_lower"] = df_ind["bb_sma"] - 2.0 * df_ind["bb_std"]
    
    signals = np.zeros(len(df_ind))
    
    for i in range(25, len(df_ind)):
        curr = df_ind.iloc[i]
        close = curr["close"]
        open_p = curr["open"]
        low = curr["low"]
        high = curr["high"]
        adx = curr["adx"]
        rsi = curr["rsi"]
        ema20 = curr["ema_20"]
        ema50 = curr["ema_50"]
        ema200 = curr["ema_200"]
        
        # Trend vs Range
        if adx >= 23:
            if close > ema200 and ema20 > ema50 and low <= ema20 * 1.004 and close > open_p and rsi >= 45:
                signals[i] = 1
            elif close < ema200 and ema20 < ema50 and high >= ema20 * 0.996 and close < open_p and rsi <= 55:
                signals[i] = -1
        else:
            if low <= curr["bb_lower"] and close > open_p and rsi <= 35:
                signals[i] = 1
            elif high >= curr["bb_upper"] and close < open_p and rsi >= 65:
                signals[i] = -1

    initial_cap = 10000.0
    balance = initial_cap
    peak = balance
    max_dd = 0.0
    trades = []
    position = None
    fee_pct = 0.00075
    
    for i in range(len(df_ind)):
        curr = df_ind.iloc[i]
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
            
        if equity > peak:
            peak = equity
        dd = (peak - equity) / peak * 100.0 if peak > 0 else 0
        if dd > max_dd:
            max_dd = dd

        if position is not None:
            pos_type = position["type"]
            sl = position["sl"]
            tp = position["tp"]
            entry = position["entry"]
            risk_dist = position["risk_dist"]
            
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
            sl_dist = 2.0 * atr
            if sig == 1:
                sl = close - sl_dist
                tp = close + (sl_dist * 2.0)
            else:
                sl = close + sl_dist
                tp = close - (sl_dist * 2.0)
                
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
    
    return {
        "symbol": symbol,
        "tf": timeframe,
        "total_trades": total_trades,
        "win_rate": win_rate,
        "net_pnl": total_net_pnl,
        "return_pct": (total_net_pnl/initial_cap)*100,
        "profit_factor": pf,
        "max_dd": max_dd
    }

def evaluate_adaptive_strategy():
    print("=========================================================================")
    print(" 2. ESTRATEGIA ADAPTATIVA DUAL REGIME (Tendencia EMA + Reversión Bollinger)")
    print("=========================================================================")
    print(f"{'SYMBOL':10s} | {'TF':4s} | {'TRADES':6s} | {'WIN RATE':8s} | {'NET PnL ($)':12s} | {'RETURN %':9s} | {'PROFIT FACTOR':13s} | {'MAX DD %':8s}")
    print("-" * 85)
    
    symbols = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT']
    timeframes = ['15m', '1h', '4h', '1d']
    
    for sym in symbols:
        for tf in timeframes:
            try:
                res = test_adaptive_bot(sym, tf, 500)
                print(f"{res['symbol']:10s} | {res['tf']:4s} | {res['total_trades']:6d} | {res['win_rate']:7.1f}% | ${res['net_pnl']:11.2f} | {res['return_pct']:8.2f}% | {res['profit_factor']:13.2f} | {res['max_dd']:7.2f}%")
            except Exception as e:
                print(f"Error {sym} {tf}: {e}")
    print()

def run_quant_strategy(symbol="SOL/USDT", timeframe="4h", limit=500, risk_pct=1.5, rr_ratio=2.5, min_adx=20):
    df = fetcher.fetch_ohlcv(symbol, timeframe, limit=limit)
    df_ind = add_all_indicators(df, {"ema_fast": 20, "ema_medium": 50, "ema_slow": 200, "rsi_period": 14, "macd_fast": 12, "macd_slow": 26, "macd_signal": 9, "adx_period": 14, "atr_period": 14})
    
    df_ind["swing_low"] = df_ind["low"].rolling(window=7, min_periods=1).min()
    df_ind["swing_high"] = df_ind["high"].rolling(window=7, min_periods=1).max()
    df_ind["vol_ma"] = df_ind["volume"].rolling(window=20, min_periods=1).mean()
    
    signals = np.zeros(len(df_ind))
    
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
        
        bull_trend = (close > ema200) and (ema20 > ema50) and (ema50 > ema200)
        bear_trend = (close < ema200) and (ema20 < ema50) and (ema50 < ema200)
        
        if adx < min_adx:
            continue
            
        vol_confirmed = vol >= vol_ma * 1.0
        pullback_long = (low <= ema20 * 1.008) and (close >= ema50 * 0.992) and (close > open_p)
        macd_bull = (macd_hist > macd_hist_prev) or (macd > macd_sig)
        rsi_bull = 42 <= rsi <= 68
        
        pullback_short = (high >= ema20 * 0.992) and (close <= ema50 * 1.008) and (close < open_p)
        macd_bear = (macd_hist < macd_hist_prev) or (macd < macd_sig)
        rsi_bear = 32 <= rsi <= 58
        
        if bull_trend and pullback_long and macd_bull and rsi_bull and vol_confirmed:
            signals[i] = 1
        elif bear_trend and pullback_short and macd_bear and rsi_bear and vol_confirmed:
            signals[i] = -1

    initial_cap = 10000.0
    balance = initial_cap
    peak = balance
    max_dd = 0.0
    trades = []
    position = None
    fee_pct = 0.00075
    
    for i in range(len(df_ind)):
        curr = df_ind.iloc[i]
        close = float(curr["close"])
        high = float(curr["high"])
        low = float(curr["low"])
        sig = int(signals[i])
        
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

        if position is not None:
            pos_type = position["type"]
            sl = position["sl"]
            tp = position["tp"]
            entry = position["entry"]
            risk_dist = position["risk_dist"]
            
            if pos_type == "LONG" and high >= entry + (1.2 * risk_dist):
                sl = max(sl, entry + (0.1 * risk_dist))
            elif pos_type == "SHORT" and low <= entry - (1.2 * risk_dist):
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
            
    wins = [t for t in trades if t > 0]
    total_trades = len(trades)
    win_rate = (len(wins) / total_trades * 100) if total_trades > 0 else 0
    total_net_pnl = balance - initial_cap
    tot_profit = sum(wins)
    tot_loss = abs(sum([t for t in trades if t <= 0]))
    pf = (tot_profit / tot_loss) if tot_loss > 0 else 0
    
    return {
        "symbol": symbol,
        "tf": timeframe,
        "total_trades": total_trades,
        "win_rate": win_rate,
        "net_pnl": total_net_pnl,
        "return_pct": (total_net_pnl/initial_cap)*100,
        "profit_factor": pf,
        "max_dd": max_dd
    }

def evaluate_quant_structure_strategy():
    print("=========================================================================")
    print(" 3. ESTRATEGIA ESTRUCTURAL Y DE ADX OPTIMIZADA (Swing High/Low + Risk 1.5%)")
    print("=========================================================================")
    print(f"{'SYMBOL':10s} | {'TF':4s} | {'TRADES':6s} | {'WIN RATE':8s} | {'NET PnL ($)':12s} | {'RETURN %':9s} | {'PROFIT FACTOR':13s} | {'MAX DD %':8s}")
    print("-" * 85)
    
    symbols = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT']
    timeframes = ['15m', '1h', '4h', '1d']
    
    for sym in symbols:
        for tf in timeframes:
            try:
                res = run_quant_strategy(sym, tf, 500, 1.5, 2.5, 20)
                print(f"{res['symbol']:10s} | {res['tf']:4s} | {res['total_trades']:6d} | {res['win_rate']:7.1f}% | ${res['net_pnl']:11.2f} | {res['return_pct']:8.2f}% | {res['profit_factor']:13.2f} | {res['max_dd']:7.2f}%")
            except Exception as e:
                print(f"Error {sym} {tf}: {e}")
    print()

if __name__ == "__main__":
    evaluate_default_strategy()
    evaluate_adaptive_strategy()
    evaluate_quant_structure_strategy()
