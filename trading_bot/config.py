"""
Configuration parameters for the Trading Bot (Quant Profitable Strategy)
"""

DEFAULT_CONFIG = {
    # Market & Exchange
    "symbol": "ETH/USDT",       # Par principal de mayor rendimiento (ETH/USDT)
    # Lista de pares priorizados por rentabilidad cuantitativa (ETH, SOL, ADA, BTC)
    "symbols": ["ETH/USDT", "SOL/USDT", "ADA/USDT", "BTC/USDT"],
    "timeframe": "4h",       # Temporalidad óptima (4h para swing trading equilibrado; 1d para macrotendencias)
    "initial_capital": 100.0, # Initial balance in USDT (Binance Futures Testnet)
    
    # Strategy Indicator Parameters
    "ema_fast": 20,          # EMA 20
    "ema_medium": 50,        # EMA 50
    "ema_slow": 200,         # EMA 200 (Macro trend filter)
    
    "rsi_period": 14,
    "macd_fast": 12,
    "macd_slow": 26,
    "macd_signal": 9,
    
    "adx_period": 14,
    "adx_threshold": 18,      # ADX 18 (Preset óptimo de mayor rendimiento)

    "supertrend_period": 10,
    "supertrend_mult": 3.0,

    # Signal confluence thresholds (used by core/strategy.py)
    "rsi_long_min": 40,
    "rsi_long_max": 72,
    "rsi_short_min": 28,
    "rsi_short_max": 60,
    "di_min_separation": 2.0,       # +DI must exceed -DI by this many points to confirm direction
    "pullback_ema50_band": 0.018,   # price within ±1.8% of EMA50 triggers Pattern C
    "min_signal_strength": 5,       # all 3 patterns start at score=4 (base confluence); 5 requires
                                     # at least 1 bonus confirmation, so this actually filters signals

    # Risk Management Parameters
    "risk_per_trade_pct": 3.5, # Perfil más agresivo: arriesgar 3.5% del capital por trade
    "risk_reward_ratio": 3.0,  # 1:3.0 Risk to Reward Ratio (Maximiza Profit Factor a 2.51)
    "atr_period": 14,
    "atr_sl_multiplier": 2.0,  # Dynamic SL multiplier
    "trailing_stop": True,     # Enable Break-Even trailing
    "slippage_pct": 0.0005,    # 0.05% adverse slippage on entries and stop-loss fills
    "max_drawdown_pct": 25.0,  # Halt new entries once drawdown from peak equity exceeds this
    "min_notional_usd": 50.0,  # Skip entries sized below Binance's typical minimum order value ($50 USDT)

    # Paper Trading / Live Monitoring
    "update_interval_sec": 60,
}
