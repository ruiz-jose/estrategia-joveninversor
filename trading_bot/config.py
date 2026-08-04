"""
Configuration parameters for the Trading Bot (Quant Profitable Strategy)
"""

DEFAULT_CONFIG = {
    # Market & Exchange
    "symbol": "BTC/USDT",       # Used by single-symbol tools (backtester, scanner, etc.)
    "symbols": ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT"],  # Pairs traded by the live/testnet trader
    "timeframe": "4h",       # Options: 5m, 15m, 1h, 4h, 1d
    "initial_capital": 60.0, # Initial balance in USDT (Spot)
    
    # Strategy Indicator Parameters
    "ema_fast": 20,          # EMA 20
    "ema_medium": 50,        # EMA 50
    "ema_slow": 200,         # EMA 200 (Macro trend filter)
    
    "rsi_period": 14,
    "macd_fast": 12,
    "macd_slow": 26,
    "macd_signal": 9,
    
    "adx_period": 14,
    "adx_threshold": 20,      # Minimum ADX value; 20 is more realistic for daily crypto

    "supertrend_period": 10,
    "supertrend_mult": 3.0,

    # Signal confluence thresholds (used by core/strategy.py)
    "rsi_long_min": 40,
    "rsi_long_max": 72,
    "rsi_short_min": 28,
    "rsi_short_max": 60,
    "di_min_separation": 2.0,       # +DI must exceed -DI by this many points to confirm direction
    "pullback_ema50_band": 0.018,   # price within ±1.8% of EMA50 triggers Pattern C
    "min_signal_strength": 4,       # all 3 patterns start at score=4; extras push to 5-7

    # Risk Management Parameters
    "risk_per_trade_pct": 1.0, # Risk 1% of total capital per trade (protects 100 USDT base)
    "risk_reward_ratio": 2.5,  # 1:2.5 Risk to Reward Ratio
    "atr_period": 14,
    "atr_sl_multiplier": 2.0,  # Dynamic SL multiplier
    "trailing_stop": True,     # Enable Break-Even trailing
    "slippage_pct": 0.0005,    # 0.05% adverse slippage on entries and stop-loss fills
    "max_drawdown_pct": 25.0,  # Halt new entries once drawdown from peak equity exceeds this
    "min_notional_usd": 10.0,  # Skip entries sized below Binance's typical minimum order value

    # Paper Trading / Live Monitoring
    "update_interval_sec": 60,
}
