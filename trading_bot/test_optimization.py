import pandas as pd
import numpy as np
import sys, os

sys.path.insert(0, r'C:\Users\Pc\.gemini\antigravity\scratch\trading_bot')

from config import DEFAULT_CONFIG
from engine.data_fetcher import DataFetcher

fetcher = DataFetcher()
df = fetcher.fetch_ohlcv('BTC/USDT', '1h', limit=500)

# Import components
from core.indicators import add_all_indicators

df_ind = add_all_indicators(df, DEFAULT_CONFIG)

def test_strategy_variant(sl_mode="EMA50", rr=1.8, trailing_mode="BE_ONLY", adx_min=20):
    signals = np.zeros(len(df_ind))
    strengths = np.zeros(len(df_ind))
    
    for i in range(2, len(df_ind)):
        curr = df_ind.iloc[i]
        prev = df_ind.iloc[i-1]
        
        close = curr["close"]
        open_p = curr["open"]
        low = curr["low"]
        high = curr["high"]
        volume = curr["volume"]
        vol_ma = df_ind.iloc[i-10:i]["volume"].mean()
        
        ema20 = curr["ema_20"]
        ema50 = curr["ema_50"]
        ema200 = curr["ema_200"]
        
        rsi = curr["rsi"]
        macd = curr["macd"]
        macd_sig = curr["macd_signal"]
        macd_hist = curr["macd_hist"]
        macd_hist_prev = prev["macd_hist"]
        
        adx = curr["adx"]
        sqz_mom = curr["squeeze_mom"]
        sqz_mom_prev = prev["squeeze_mom"]
        
        if adx < adx_min:
            continue
            
        # Long: 3-EMA alignment & Price touching EMA20/50 zone with bullish reaction
        trend_bullish = (close > ema200) and (ema50 > ema200) and (ema20 > ema50)
        pullback_long = (low <= ema20 * 1.005) and (close >= ema50 * 0.995) and (close > open_p)
        macd_bullish = (macd_hist > macd_hist_prev) or (macd > macd_sig)
        sqz_bullish = (sqz_mom > sqz_mom_prev) and (sqz_mom > 0)
        
        # Short: 3-EMA alignment & Price touching EMA20/50 zone with bearish reaction
        trend_bearish = (close < ema200) and (ema50 < ema200) and (ema20 < ema50)
        pullback_short = (high >= ema20 * 0.995) and (close <= ema50 * 1.005) and (close < open_p)
        macd_bearish = (macd_hist < macd_hist_prev) or (macd < macd_sig)
        sqz_bearish = (sqz_mom < sqz_mom_prev) and (sqz_mom < 0)
        
        if trend_bullish and pullback_long and (macd_bullish or sqz_bullish) and 40 <= rsi <= 65:
            signals[i] = 1
            strengths[i] = 3
        elif trend_bearish and pullback_short and (macd_bearish or sqz_bearish) and 35 <= rsi <= 60:
            signals[i] = -1
            strengths[i] = 3
            
    # Backtest simulation
    initial_cap = 10000.0
    balance = initial_cap
    peak = balance
    max_dd = 0.0
    trades = []
    position = None
    
    for i in range(len(df_ind)):
        curr = df_ind.iloc[i]
        timestamp = str(curr["timestamp"])
        close = float(curr["close"])
        high = float(curr["high"])
        low = float(curr["low"])
        atr = float(curr["atr"]) if not np.isnan(curr["atr"]) else close * 0.015
        sig = int(signals[i])
        
        if position is not None:
            pos_type = position["type"]
            sl = position["stop_loss"]
            tp = position["take_profit"]
            entry = position["entry_price"]
            risk_dist = position["risk_dist"]
            
            # Trailing to Break-Even once 1x R/R is reached
            if trailing_mode == "BE_ONLY":
                if pos_type == "LONG" and high >= entry + risk_dist:
                    sl = max(sl, entry + (risk_dist * 0.1))
                elif pos_type == "SHORT" and low <= entry - risk_dist:
                    sl = min(sl, entry - (risk_dist * 0.1))
            
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
                fee = (position["size_usd"] + (position["size_asset"] * exit_price)) * 0.00075
                net_pnl = pnl - fee
                balance += net_pnl
                trades.append(net_pnl)
                position = None
                
        if position is None and sig != 0:
            ema50 = float(curr["ema_50"])
            ema20 = float(curr["ema_20"])
            
            if sl_mode == "EMA50":
                if sig == 1:
                    sl = min(close - (2.0 * atr), ema50 * 0.995)
                else:
                    sl = max(close + (2.0 * atr), ema50 * 1.005)
                risk_dist = abs(close - sl)
            else:
                risk_dist = 2.5 * atr
                sl = close - risk_dist if sig == 1 else close + risk_dist
                
            tp = close + (risk_dist * rr) if sig == 1 else close - (risk_dist * rr)
            
            risk_usd = balance * 0.015
            size_asset = risk_usd / risk_dist
            
            position = {
                "type": "LONG" if sig == 1 else "SHORT",
                "entry_price": close,
                "stop_loss": sl,
                "take_profit": tp,
                "risk_dist": risk_dist,
                "size_asset": size_asset,
                "size_usd": size_asset * close
            }
            
    wins = [t for t in trades if t > 0]
    win_rate = (len(wins) / len(trades) * 100) if len(trades) > 0 else 0
    total_pnl = balance - initial_cap
    print(f"SL: {sl_mode} | RR: {rr} | Trailing: {trailing_mode} | Trades: {len(trades)} | Win Rate: {win_rate:.1f}% | Net PnL: ${total_pnl:.2f}")

print("=== TESTING STRATEGY VARIATIONS ===")
test_strategy_variant(sl_mode="EMA50", rr=1.5, trailing_mode="BE_ONLY", adx_min=20)
test_strategy_variant(sl_mode="EMA50", rr=1.8, trailing_mode="BE_ONLY", adx_min=20)
test_strategy_variant(sl_mode="EMA50", rr=2.0, trailing_mode="BE_ONLY", adx_min=20)
test_strategy_variant(sl_mode="ATR_2.5", rr=1.8, trailing_mode="BE_ONLY", adx_min=20)
