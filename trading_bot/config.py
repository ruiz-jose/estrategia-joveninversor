"""
Configuration parameters for the Trading Bot (Quant Profitable Strategy)
"""

DEFAULT_CONFIG = {
    # Market & Exchange
    "symbol": "BTC/USDT",
    "timeframe": "1d",       # Options: 5m, 15m, 1h, 4h, 1d
    "initial_capital": 100.0, # Initial balance in USDT
    
    # Strategy Indicator Parameters
    "ema_fast": 20,          # EMA 20
    "ema_medium": 50,        # EMA 50
    "ema_slow": 200,         # EMA 200 (Macro trend filter)
    
    "rsi_period": 14,
    "macd_fast": 12,
    "macd_slow": 26,
    "macd_signal": 9,
    
    "adx_period": 14,
    "adx_threshold": 25,      # Minimum ADX value (< 25 = sideways market, no real trend)

    "supertrend_period": 10,
    "supertrend_mult": 3.0,

    # Signal confluence thresholds (used by core/strategy.py)
    "rsi_long_min": 40,
    "rsi_long_max": 68,
    "rsi_short_min": 32,
    "rsi_short_max": 60,
    "pullback_ema20_pct": 0.006,  # tolerance around EMA20 for pullback entry
    "pullback_ema50_pct": 0.008,  # tolerance around EMA50 for pullback entry
    "min_signal_strength": 4,     # require at least 1 extra confluence factor (MACD or RSI) beyond base

    # Risk Management Parameters
    "risk_per_trade_pct": 1.0, # Risk 1% of total capital per trade (protects 100 USDT base)
    "risk_reward_ratio": 2.5,  # 1:2.5 Risk to Reward Ratio
    "atr_period": 14,
    "atr_sl_multiplier": 2.0,  # Dynamic SL multiplier
    "trailing_stop": True,     # Enable Break-Even trailing
    "slippage_pct": 0.0005,    # 0.05% adverse slippage on entries and stop-loss fills
    "max_drawdown_pct": 25.0,  # Halt new entries once drawdown from peak equity exceeds this

    # Paper Trading / Live Monitoring
    "update_interval_sec": 60,
}
