import pandas as pd
import numpy as np

class Strategy:
    """
    Quant Profitable Multi-Confluence Strategy
    Combines Supertrend Direction, EMA 200 Trend Bias, EMA 20/50 Alignment, MACD & RSI.
    """
    
    def __init__(self, config: dict):
        self.config = config
        
    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        
        signals = np.zeros(len(df))
        strengths = np.zeros(len(df))
        reasons = [""] * len(df)
        
        adx_thresh = float(self.config.get("adx_threshold", 18))
        rsi_long_min = float(self.config.get("rsi_long_min", 40))
        rsi_long_max = float(self.config.get("rsi_long_max", 68))
        rsi_short_min = float(self.config.get("rsi_short_min", 32))
        rsi_short_max = float(self.config.get("rsi_short_max", 60))
        pullback_ema20_pct = float(self.config.get("pullback_ema20_pct", 0.006))
        pullback_ema50_pct = float(self.config.get("pullback_ema50_pct", 0.008))

        for i in range(2, len(df)):
            curr = df.iloc[i]
            prev = df.iloc[i-1]
            
            close = float(curr["close"])
            open_p = float(curr["open"])
            low = float(curr["low"])
            high = float(curr["high"])
            
            ema20 = float(curr["ema_20"])
            ema50 = float(curr["ema_50"])
            ema200 = float(curr["ema_200"])
            
            rsi = float(curr["rsi"])
            macd = float(curr["macd"])
            macd_sig = float(curr["macd_signal"])
            macd_hist = float(curr["macd_hist"])
            macd_hist_prev = float(prev["macd_hist"])
            
            adx = float(curr["adx"]) if "adx" in curr and not np.isnan(curr["adx"]) else 20.0
            st_dir = int(curr["st_direction"]) if "st_direction" in curr else 0
            st_dir_prev = int(prev["st_direction"]) if "st_direction" in prev else 0
            
            # --- LONG CONDITIONAL CHECKS ---
            # 1. Supertrend is Bullish (Green) or flipped Green
            st_bullish = (st_dir == 1)
            st_flip_long = (st_dir == 1) and (st_dir_prev == -1)
            
            # 2. Trend Bias & Pullback
            ema_bullish = (close > ema200) and (ema20 > ema50)
            pullback_long = (low <= ema20 * (1 + pullback_ema20_pct)) and (close >= ema50 * (1 - pullback_ema50_pct)) and (close > open_p)

            # 3. Momentum & RSI
            macd_bullish = (macd_hist > macd_hist_prev) or (macd > macd_sig)
            rsi_valid_long = rsi_long_min <= rsi <= rsi_long_max
            adx_valid = adx >= adx_thresh

            # --- SHORT CONDITIONAL CHECKS ---
            st_bearish = (st_dir == -1)
            st_flip_short = (st_dir == -1) and (st_dir_prev == 1)

            ema_bearish = (close < ema200) and (ema20 < ema50)
            pullback_short = (high >= ema20 * (1 - pullback_ema20_pct)) and (close <= ema50 * (1 + pullback_ema50_pct)) and (close < open_p)

            macd_bearish = (macd_hist < macd_hist_prev) or (macd < macd_sig)
            rsi_valid_short = rsi_short_min <= rsi <= rsi_short_max
            
            # EVALUATE LONG (Supertrend Flip OR EMA Pullback in ST Bull Trend)
            if adx_valid and ((st_flip_long and close > ema200) or (st_bullish and ema_bullish and pullback_long and macd_bullish and rsi_valid_long)):
                score = 3
                reasons_list = ["Supertrend Alcista", "Precio > EMA200"]
                if macd_bullish: score += 1; reasons_list.append("Impulso MACD")
                if rsi_valid_long: score += 1; reasons_list.append(f"RSI ({rsi:.1f})")
                
                signals[i] = 1
                strengths[i] = score
                reasons[i] = " LONG: " + " | ".join(reasons_list)
                
            # EVALUATE SHORT
            elif adx_valid and ((st_flip_short and close < ema200) or (st_bearish and ema_bearish and pullback_short and macd_bearish and rsi_valid_short)):
                score = 3
                reasons_list = ["Supertrend Bajista", "Precio < EMA200"]
                if macd_bearish: score += 1; reasons_list.append("Impulso MACD Bajista")
                if rsi_valid_short: score += 1; reasons_list.append(f"RSI ({rsi:.1f})")
                
                signals[i] = -1
                strengths[i] = score
                reasons[i] = " SHORT: " + " | ".join(reasons_list)

        df["signal"] = signals
        df["signal_strength"] = strengths
        df["reason"] = reasons
        return df
