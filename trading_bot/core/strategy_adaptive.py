import pandas as pd
import numpy as np


class AdaptiveRegimeStrategy:
    """
    Regime-switching strategy: trend-following pullback when ADX shows a strong
    trend, mean-reversion (Bollinger Bands + RSI extremes) when ADX shows a
    ranging/choppy market. Alternative to Strategy (core/strategy.py)'s fixed
    multi-confluence approach - see ESTRATEGIA_REGIMEN_ADAPTATIVO.md for the
    backtest evidence this was selected from.

    Shares the same SL/TP/position-sizing pipeline (core/risk_manager.py) and the
    same Backtester/PortfolioBacktester/live trader as Strategy - only signal
    generation differs, so it's a drop-in replacement via core/strategy_factory.py.
    """

    def __init__(self, config: dict):
        self.config = config
        self.adx_regime_threshold = float(config.get("adx_regime_threshold", 26))
        self.bb_len = int(config.get("bb_len", 20))
        self.bb_mult = float(config.get("bb_mult", 2.0))
        self.rsi_range_long = float(config.get("rsi_range_long", 35))
        self.rsi_range_short = float(config.get("rsi_range_short", 65))

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()

        bb_sma = df["close"].rolling(window=self.bb_len).mean()
        bb_std = df["close"].rolling(window=self.bb_len).std()
        bb_upper = bb_sma + self.bb_mult * bb_std
        bb_lower = bb_sma - self.bb_mult * bb_std

        signals = np.zeros(len(df))
        strengths = np.zeros(len(df))
        reasons = [""] * len(df)

        allow_short = self.config.get("allow_short", True)

        for i in range(30, len(df)):
            curr = df.iloc[i]

            ub = bb_upper.iloc[i]
            lb = bb_lower.iloc[i]
            if np.isnan(ub) or np.isnan(lb):
                continue

            close = float(curr["close"])
            open_p = float(curr["open"])
            low = float(curr["low"])
            high = float(curr["high"])
            adx = float(curr["adx"]) if not np.isnan(curr["adx"]) else 0.0
            rsi = float(curr["rsi"])
            ema20 = float(curr["ema_20"])
            ema50 = float(curr["ema_50"])
            ema200 = float(curr["ema_200"])

            if adx >= self.adx_regime_threshold:
                # Trending regime: pull back to EMA20 in the direction of the
                # EMA20/50/200 stack, confirmed by a same-direction candle and RSI
                # not already at the opposite extreme.
                long_c = close > ema200 and ema20 > ema50 and low <= ema20 * 1.004 and close > open_p and rsi >= 45
                short_c = close < ema200 and ema20 < ema50 and high >= ema20 * 0.996 and close < open_p and rsi <= 55
                if long_c:
                    signals[i] = 1
                    strengths[i] = 5
                    reasons[i] = f" LONG: Trend Pullback (ADX {adx:.1f} >= {self.adx_regime_threshold:.0f}) | EMA20 bounce | RSI {rsi:.1f}"
                elif short_c and allow_short:
                    signals[i] = -1
                    strengths[i] = 5
                    reasons[i] = f" SHORT: Trend Pullback (ADX {adx:.1f} >= {self.adx_regime_threshold:.0f}) | EMA20 rejection | RSI {rsi:.1f}"
            else:
                # Ranging regime: fade a Bollinger Band touch with RSI confirming
                # the extreme, regardless of the EMA200 macro trend.
                long_c = low <= lb and close > open_p and rsi <= self.rsi_range_long
                short_c = high >= ub and close < open_p and rsi >= self.rsi_range_short
                if long_c:
                    signals[i] = 1
                    strengths[i] = 5
                    reasons[i] = f" LONG: Mean Reversion (ADX {adx:.1f} < {self.adx_regime_threshold:.0f}) | BB lower touch | RSI {rsi:.1f}"
                elif short_c and allow_short:
                    signals[i] = -1
                    strengths[i] = 5
                    reasons[i] = f" SHORT: Mean Reversion (ADX {adx:.1f} < {self.adx_regime_threshold:.0f}) | BB upper touch | RSI {rsi:.1f}"

        df["signal"] = signals
        df["signal_strength"] = strengths
        df["reason"] = reasons
        return df
