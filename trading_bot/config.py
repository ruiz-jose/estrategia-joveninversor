"""
Configuration parameters for the Trading Bot (Quant Profitable Strategy)
"""

DEFAULT_CONFIG = {
    # Market & Exchange
    "symbol": "SOL/USDT",
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
    "adx_threshold": 18,      # Minimum ADX value
    
    "supertrend_period": 10,
    "supertrend_mult": 3.0,
    
    # Risk Management Parameters
    "risk_per_trade_pct": 2.0, # Risk 2% of total capital per trade
    "risk_reward_ratio": 2.5,  # 1:2.5 Risk to Reward Ratio
    "atr_period": 14,
    "atr_sl_multiplier": 2.0,  # Dynamic SL multiplier
    "trailing_stop": True,     # Enable Break-Even trailing
    
    # Paper Trading / Live Monitoring
    "update_interval_sec": 60,
}
