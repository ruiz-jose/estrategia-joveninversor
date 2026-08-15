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

        signals   = np.zeros(len(df))
        strengths = np.zeros(len(df))
        reasons   = [""] * len(df)

        adx_thresh    = float(self.config.get("adx_threshold",     20))
        rsi_long_min  = float(self.config.get("rsi_long_min",       40))
        rsi_long_max  = float(self.config.get("rsi_long_max",       72))
        rsi_short_min = float(self.config.get("rsi_short_min",      28))
        rsi_short_max = float(self.config.get("rsi_short_max",      60))
        di_min_sep    = float(self.config.get("di_min_separation",   2.0))
        ema50_band    = float(self.config.get("pullback_ema50_band", 0.018))

        for i in range(3, len(df)):
            curr = df.iloc[i]
            prev = df.iloc[i - 1]

            close  = float(curr["close"])
            open_p = float(curr["open"])

            ema50  = float(curr["ema_50"])
            ema200 = float(curr["ema_200"])

            rsi       = float(curr["rsi"])
            macd_hist = float(curr["macd_hist"])
            mh_prev   = float(prev["macd_hist"])

            adx      = float(curr["adx"])      if ("adx"      in curr.index and not np.isnan(curr["adx"]))      else 0.0
            plus_di  = float(curr["plus_di"])  if ("plus_di"  in curr.index and not np.isnan(curr["plus_di"]))  else 0.0
            minus_di = float(curr["minus_di"]) if ("minus_di" in curr.index and not np.isnan(curr["minus_di"])) else 0.0

            sqz_on   = bool(curr["squeeze_on"])  if ("squeeze_on"  in curr.index and pd.notna(curr["squeeze_on"]))  else False
            sqz_on_p = bool(prev["squeeze_on"])  if ("squeeze_on"  in prev.index and pd.notna(prev["squeeze_on"]))  else False
            sqz_mom  = float(curr["squeeze_mom"]) if ("squeeze_mom" in curr.index and not np.isnan(curr["squeeze_mom"])) else 0.0
            sqz_mom_p = float(prev["squeeze_mom"]) if ("squeeze_mom" in prev.index and not np.isnan(prev["squeeze_mom"])) else 0.0

            st_dir      = int(curr["st_direction"]) if "st_direction" in curr.index else 0
            st_dir_prev = int(prev["st_direction"]) if "st_direction" in prev.index else 0

            # ── Derived flags ────────────────────────────────────────────────
            macro_bull = close > ema200
            macro_bear = close < ema200

            # +DI/-DI directional pressure with minimum separation
            di_long  = (plus_di  - minus_di) >= di_min_sep
            di_short = (minus_di - plus_di)  >= di_min_sep

            st_bull       = (st_dir == 1)
            st_bear       = (st_dir == -1)
            st_flip_long  = (st_dir == 1)  and (st_dir_prev == -1)
            st_flip_short = (st_dir == -1) and (st_dir_prev == 1)

            # Squeeze just released this bar with directional momentum
            sqz_bull = sqz_on_p and (not sqz_on) and (sqz_mom > 0) and (sqz_mom > sqz_mom_p)
            sqz_bear = sqz_on_p and (not sqz_on) and (sqz_mom < 0) and (sqz_mom < sqz_mom_p)

            # Price touching EMA50 support/resistance zone
            near_ema50 = (abs(close - ema50) / ema50) <= ema50_band

            rsi_l = rsi_long_min  <= rsi <= rsi_long_max
            rsi_s = rsi_short_min <= rsi <= rsi_short_max

            # ── LONG patterns ────────────────────────────────────────────────
            long_fired = False
            score = 0
            rl = []

            if st_flip_long and macro_bull and di_long and adx >= adx_thresh and rsi_l:
                # Pattern A: first bullish ST bar confirmed by +DI dominance
                score = 4
                rl = [f"ST Flip LONG", f"+DI {plus_di:.1f}>{minus_di:.1f}", f"ADX {adx:.1f}"]
                if sqz_mom > 0:            score += 1; rl.append("Sqz+")
                if adx >= adx_thresh + 10: score += 1; rl.append("ADX++")
                long_fired = True

            elif sqz_bull and macro_bull and di_long and rsi_l:
                # Pattern B: squeeze released bullish with DI confirmation
                score = 4
                rl = ["Sqz Release LONG", f"+DI {plus_di:.1f}", f"Mom {sqz_mom:.4f}"]
                if adx >= adx_thresh:  score += 1; rl.append(f"ADX {adx:.1f}")
                if st_bull:            score += 1; rl.append("ST Bull")
                long_fired = True

            elif st_bull and macro_bull and di_long and near_ema50 and (close > open_p) and rsi_l:
                # Pattern C: bullish candle bouncing off EMA50 in confirmed uptrend
                score = 4
                rl = ["EMA50 Support LONG", "ST Bull", f"+DI {plus_di:.1f}"]
                if macd_hist > mh_prev:    score += 1; rl.append("MACD↑")
                if sqz_mom > 0:            score += 1; rl.append("Sqz+")
                if adx >= adx_thresh + 5:  score += 1; rl.append(f"ADX {adx:.1f}")
                long_fired = True

            if long_fired:
                signals[i]   = 1
                strengths[i] = score
                reasons[i]   = " LONG: " + " | ".join(rl)
                continue

            if not self.config.get("allow_short", True):
                continue

            # ── SHORT patterns ───────────────────────────────────────────────
            score = 0
            rl = []

            if st_flip_short and macro_bear and di_short and adx >= adx_thresh and rsi_s:
                # Pattern A: first bearish ST bar confirmed by -DI dominance
                score = 4
                rl = ["ST Flip SHORT", f"-DI {minus_di:.1f}>{plus_di:.1f}", f"ADX {adx:.1f}"]
                if sqz_mom < 0:            score += 1; rl.append("Sqz-")
                if adx >= adx_thresh + 10: score += 1; rl.append("ADX++")

            elif sqz_bear and macro_bear and di_short and rsi_s:
                # Pattern B: squeeze released bearish with DI confirmation
                score = 4
                rl = ["Sqz Release SHORT", f"-DI {minus_di:.1f}", f"Mom {sqz_mom:.4f}"]
                if adx >= adx_thresh:  score += 1; rl.append(f"ADX {adx:.1f}")
                if st_bear:            score += 1; rl.append("ST Bear")

            elif st_bear and macro_bear and di_short and near_ema50 and (close < open_p) and rsi_s:
                # Pattern C: bearish candle rejected at EMA50 in confirmed downtrend
                score = 4
                rl = ["EMA50 Resist SHORT", "ST Bear", f"-DI {minus_di:.1f}"]
                if macd_hist < mh_prev:   score += 1; rl.append("MACD↓")
                if sqz_mom < 0:           score += 1; rl.append("Sqz-")
                if adx >= adx_thresh + 5: score += 1; rl.append(f"ADX {adx:.1f}")

            if score >= 4:
                signals[i]   = -1
                strengths[i] = score
                reasons[i]   = " SHORT: " + " | ".join(rl)

        df["signal"]          = signals
        df["signal_strength"] = strengths
        df["reason"]          = reasons
        return df
