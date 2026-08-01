"""
Comprehensive backtest scan across symbols, timeframes, and config presets.

Previously this file hand-rolled 3 separate strategy implementations (default,
"adaptive dual regime", "structural ADX") that diverged from core/strategy.py and
from what the live bot (engine/testnet_trader.py) actually runs - any tuning found
here never reached production. Now every preset below runs through the same
Strategy/Backtester classes the bot uses; presets only vary config values, not logic.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from engine.data_fetcher import DataFetcher
from engine.backtester import Backtester
from config import DEFAULT_CONFIG

fetcher = DataFetcher()

SYMBOLS = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT']
TIMEFRAMES = ['15m', '1h', '4h', '1d']

PRESETS = {
    "Default": {},
    "Conservador (ADX 25, RR 2.0)": {"adx_threshold": 25, "risk_reward_ratio": 2.0, "atr_sl_multiplier": 2.2},
    "Agresivo (ADX 18, RR 3.0)": {"adx_threshold": 18, "risk_reward_ratio": 3.0, "atr_sl_multiplier": 1.8},
}


def run_preset(preset_name, overrides):
    print("=" * 90)
    print(f" PRESET: {preset_name}")
    print("=" * 90)
    print(f"{'SYMBOL':10s} | {'TF':4s} | {'TRADES':6s} | {'WIN RATE':8s} | {'NET PnL ($)':12s} | {'RETURN %':9s} | {'PROFIT FACTOR':13s} | {'MAX DD %':8s}")
    print("-" * 90)

    results = []
    for sym in SYMBOLS:
        for tf in TIMEFRAMES:
            try:
                config = DEFAULT_CONFIG.copy()
                config.update(overrides)
                config["symbol"] = sym
                config["timeframe"] = tf

                df = fetcher.fetch_ohlcv(sym, tf, limit=500)
                res = Backtester(config).run(df)
                s = res["summary"]
                results.append((sym, tf, s))
                print(f"{sym:10s} | {tf:4s} | {s['total_trades']:6d} | {s['win_rate']:7.1f}% | ${s['total_net_pnl']:11.2f} | {s['total_return_pct']:8.2f}% | {s['profit_factor']:13.2f} | {s['max_drawdown']:7.2f}%")
            except Exception as e:
                print(f"Error {sym} {tf}: {e}")
    print()
    return results


if __name__ == "__main__":
    for name, overrides in PRESETS.items():
        run_preset(name, overrides)
