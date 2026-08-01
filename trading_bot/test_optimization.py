"""
Quick parameter-variation check for a single symbol/timeframe.

Previously this reimplemented the strategy and backtest loop from scratch, diverging
from core/strategy.py and engine/backtester.py (the code the live bot actually runs).
Now it just runs config variants through the real Strategy/Backtester classes, on a
single in-sample dataset - this is a fast sanity check, not a substitute for the
walk-forward out-of-sample search in optimize_profitable.py.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import DEFAULT_CONFIG
from engine.data_fetcher import DataFetcher
from engine.backtester import Backtester

fetcher = DataFetcher()
df = fetcher.fetch_ohlcv('BTC/USDT', '1h', limit=500)

VARIANTS = [
    {"risk_reward_ratio": 1.5, "adx_threshold": 20},
    {"risk_reward_ratio": 1.8, "adx_threshold": 20},
    {"risk_reward_ratio": 2.0, "adx_threshold": 20},
    {"risk_reward_ratio": 1.8, "adx_threshold": 25},
]

print("=== TESTING STRATEGY VARIATIONS (in-sample, BTC/USDT 1h) ===")
for overrides in VARIANTS:
    config = DEFAULT_CONFIG.copy()
    config.update(overrides)
    summary = Backtester(config).run(df)["summary"]
    print(
        f"RR: {config['risk_reward_ratio']} | ADX>=: {config['adx_threshold']} | "
        f"Trades: {summary['total_trades']} | Win Rate: {summary['win_rate']:.1f}% | "
        f"Net PnL: ${summary['total_net_pnl']:.2f} | PF: {summary['profit_factor']:.2f} | MaxDD: {summary['max_drawdown']:.2f}%"
    )
