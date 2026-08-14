"""
Configuration parameters for the Trading Bot (Quant Profitable Strategy)
"""

DEFAULT_CONFIG = {
    # Market & Exchange
    "symbol": "ETH/USDT",       # Par principal de mayor rendimiento (ETH/USDT)
    # SOL/USDT y ADA/USDT retirados de producción (2026-08-14): SOL disparó su
    # propio kill-switch de drawdown en la auditoria reciente (DD 25.16% > limite
    # 25%) y ADA no genero ni una sola señal en 4h en los ultimos 90 dias, ademas
    # de evidencia OOS insuficiente/negativa en el walk-forward y en la auditoria
    # de 8 meses. BNB ya estaba excluido (veredicto NO CONFIABLE en las 3 fuentes).
    # BTC se mantiene con vigilancia: solo "MARGINAL" en el walk-forward de 5.5
    # años y negativo en las dos ventanas recientes independientes - revisar si
    # el deterioro continua. Ver trading_bot/robustness_report.py y CHECKLIST.
    "symbols": ["ETH/USDT", "BTC/USDT"],
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
    "risk_per_trade_pct": 1.5, # 1.5% del capital por trade (dentro del 1.0%-2.0% exigido por CHECKLIST_PRE_VUELO.md)
    "risk_reward_ratio": 3.0,  # 1:3.0 Risk to Reward Ratio (Maximiza Profit Factor a 2.51)
    "atr_period": 14,
    "atr_sl_multiplier": 2.0,  # Dynamic SL multiplier
    "trailing_stop": True,     # Enable Break-Even trailing
    "slippage_pct": 0.0005,    # 0.05% adverse slippage on entries and stop-loss fills
    "max_drawdown_pct": 25.0,  # Halt new entries once drawdown from peak equity exceeds this
    # Hard cap on positions open at once across every symbol in `symbols` (mirrors
    # MAX_CONCURRENT_POSITIONS in .env, used by engine/testnet_trader.py in production
    # and by engine/portfolio_backtester.py here) - bounds worst-case correlated
    # exposure on top of the balance-reservation accounting below.
    "max_concurrent_positions": 3,
    # With ~100 USDT capital, Binance's $50 minimum notional forces large position
    # sizing regardless of risk_per_trade_pct: max_position_alloc_pct must clear it
    # with room to spare, and min_notional_usd needs a buffer above the real $50 floor
    # so borderline sizes are skipped locally instead of bouncing off Binance at
    # execution time (price drift + lot-size rounding can shave a few USD off the estimate).
    # NOTE: at risk_per_trade_pct=1.5%, the risk-based size only reaches min_notional_usd
    # on its own (without leaning on max_position_alloc_pct) once balance exceeds roughly
    # $220-300 USDT (depends on the ATR-driven stop distance at entry time, typically
    # 2%-6% on 4h). Below that, max_position_alloc_pct=0.60 is what makes trades clear
    # the exchange minimum at all - i.e. with $100 capital, position sizing is dominated
    # by this cap rather than by risk_per_trade_pct, so per-trade concentration stays high
    # until capital is increased toward that ~$220-300 range.
    "max_position_alloc_pct": 0.60, # Allow up to 60% of capital per trade (was defaulting to 35%, which caps at $35 < $50 min)
    "min_notional_usd": 55.0,  # Binance's real minimum is $50; skip below $55 to leave a rounding/slippage buffer

    # Paper Trading / Live Monitoring
    "update_interval_sec": 60,
}
