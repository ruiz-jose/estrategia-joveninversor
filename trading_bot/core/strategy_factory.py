from core.strategy import Strategy
from core.strategy_adaptive import AdaptiveRegimeStrategy

STRATEGIES = {
    "confluence": Strategy,
    "adaptive_regime": AdaptiveRegimeStrategy,
}


def build_strategy(config: dict):
    """
    Instantiates the strategy named by config["strategy_type"] (default
    "confluence", the original Supertrend/EMA/MACD/RSI/ADX/Squeeze multi-
    confluence model). "adaptive_regime" switches between trend-following and
    mean-reversion signal logic based on ADX - see
    ESTRATEGIA_REGIMEN_ADAPTATIVO.md for what each one does and the backtest
    evidence behind them.

    Single choke point so Backtester, PortfolioBacktester and the live/testnet
    trader all pick the same strategy for a given config instead of each
    hardcoding Strategy(config) separately.
    """
    strategy_type = config.get("strategy_type", "confluence")
    cls = STRATEGIES.get(strategy_type)
    if cls is None:
        raise ValueError(f"Unknown strategy_type '{strategy_type}'. Valid options: {list(STRATEGIES.keys())}")
    return cls(config)
