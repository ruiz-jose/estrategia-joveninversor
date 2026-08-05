"""
Configuration parameters for the Trading Bot (Quant Profitable Strategy)
"""

DEFAULT_CONFIG = {
    # Market & Exchange
    "symbol": "BTC/USDT",       # Used by single-symbol tools (backtester, scanner, etc.)
    # Walk-forward OOS evidence (robustness_report.py, 5 folds, ~5.5y of 4h candles):
    # ETH, SOL, ADA, DOGE came back CONFIABLE (PF 1.35-1.64, >=3/5 folds profitable);
    # BTC only MARGINAL (PF 1.06); BNB and XRP came back NO CONFIABLE (PF 0.55/0.74)
    # and were dropped. Re-check this list whenever robustness_report.py is re-run.
    "symbols": ["ETH/USDT", "SOL/USDT", "BTC/USDT", "ADA/USDT", "DOGE/USDT"],  # Pairs traded by the live/testnet trader
    "timeframe": "4h",       # Options: 5m, 15m, 1h, 4h, 1d
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
    "min_signal_strength": 5,       # all 3 patterns start at score=4 (base confluence); 5 requires
                                     # at least 1 bonus confirmation, so this actually filters signals

    # Risk Management Parameters
    "risk_per_trade_pct": 2.0, # Risk 2% of total capital per trade; with a small account (e.g. 60
                               # USDT) 1% risks <$1, which frequently sizes below min_notional_usd
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
