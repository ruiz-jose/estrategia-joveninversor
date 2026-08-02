"""
Walk-forward parameter search for the Quant Profitable Strategy.

Unlike a plain grid search over the full dataset (which just curve-fits to history),
this splits each symbol/timeframe history into chronological folds, tunes parameters
on the train portion of each fold, and reports performance on the held-out test
portion only. The out-of-sample numbers are the ones that matter - if they diverge
a lot from in-sample, the strategy is likely overfit to that fold.

Uses the same Strategy/Backtester classes as the live bot (core/strategy.py,
engine/backtester.py), so any config found here is directly usable in config.py -
no manual porting of hand-rolled duplicate logic.
"""
import itertools
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from engine.data_fetcher import DataFetcher
from engine.backtester import Backtester
from engine.walk_forward import split_walk_forward
from config import DEFAULT_CONFIG

fetcher = DataFetcher()

PARAM_GRID = {
    "adx_threshold": [18, 25],
    "risk_reward_ratio": [2.0, 2.5],
    "atr_sl_multiplier": [1.8, 2.2],
}

MIN_TRADES_FOR_SELECTION = 5


def grid_search(train_df, base_config):
    """Pick the param combo with the best in-sample profit factor, requiring a minimum trade count."""
    best = None
    for adx_t, rr, atr_mult in itertools.product(
        PARAM_GRID["adx_threshold"], PARAM_GRID["risk_reward_ratio"], PARAM_GRID["atr_sl_multiplier"]
    ):
        config = base_config.copy()
        config.update({"adx_threshold": adx_t, "risk_reward_ratio": rr, "atr_sl_multiplier": atr_mult})
        summary = Backtester(config).run(train_df)["summary"]

        if summary["total_trades"] < MIN_TRADES_FOR_SELECTION:
            continue
        if best is None or summary["profit_factor"] > best["summary"]["profit_factor"]:
            best = {"config": config, "summary": summary}
    return best


def run_walk_forward(symbol, timeframe, limit=1500, n_folds=3, train_ratio=0.7, reoptimize=True):
    """Run the walk-forward split and backtest each fold's out-of-sample segment.

    ``reoptimize=True`` (this module's own parameter-search use case) grid-searches
    PARAM_GRID on each fold's train segment and evaluates the best in-sample combo
    out-of-sample - useful to explore which parameters generalize, but it means the
    OOS numbers validate a different config per fold, never the fixed config.py that
    actually runs in production.

    ``reoptimize=False`` skips the grid search entirely and evaluates the fixed
    DEFAULT_CONFIG (config.py) parameters on every fold, so the OOS numbers certify
    the exact configuration that would be deployed. Use this for robustness/reliability
    verdicts (see robustness_report.py); reserve reoptimize=True for parameter
    exploration only.
    """
    df = fetcher.fetch_ohlcv(symbol, timeframe, limit=limit)
    base_config = DEFAULT_CONFIG.copy()
    base_config["symbol"] = symbol
    base_config["timeframe"] = timeframe

    fold_results = []
    for fold_idx, (train_df, test_df, test_warmup_df) in enumerate(split_walk_forward(df, n_folds=n_folds, train_ratio=train_ratio), start=1):
        if len(train_df) < 100 or len(test_df) < 30:
            continue

        if reoptimize:
            best = grid_search(train_df, base_config)
            if best is None:
                print(f"  Fold {fold_idx}: ninguna combinación alcanzó el mínimo de {MIN_TRADES_FOR_SELECTION} trades in-sample, se omite.")
                continue
            fold_config = best["config"]
            in_sample_summary = best["summary"]
        else:
            fold_config = base_config
            in_sample_summary = Backtester(fold_config).run(train_df)["summary"]

        test_summary = Backtester(fold_config).run(test_df, indicator_warmup_df=test_warmup_df)["summary"]
        fold_results.append({
            "fold": fold_idx,
            "params": {k: fold_config[k] for k in PARAM_GRID},
            "in_sample": in_sample_summary,
            "out_of_sample": test_summary,
        })

    return fold_results


def print_fold_results(symbol, timeframe, fold_results):
    print(f"\n=== {symbol} | {timeframe} ===")
    if not fold_results:
        print("  Sin folds válidos (datos insuficientes).")
        return

    for fr in fold_results:
        p, ins, oos = fr["params"], fr["in_sample"], fr["out_of_sample"]
        print(f"  Fold {fr['fold']} | params: adx>={p['adx_threshold']} rr={p['risk_reward_ratio']} atr_mult={p['atr_sl_multiplier']}")
        print(f"    IN-SAMPLE  | Trades: {ins['total_trades']:3d} | WinRate: {ins['win_rate']:5.1f}% | PF: {ins['profit_factor']:5.2f} | Return: {ins['total_return_pct']:6.2f}% | MaxDD: {ins['max_drawdown']:5.2f}%")
        print(f"    OUT-SAMPLE | Trades: {oos['total_trades']:3d} | WinRate: {oos['win_rate']:5.1f}% | PF: {oos['profit_factor']:5.2f} | Return: {oos['total_return_pct']:6.2f}% | MaxDD: {oos['max_drawdown']:5.2f}%")

    oos_trades = sum(fr["out_of_sample"]["total_trades"] for fr in fold_results)
    avg_oos_return = sum(fr["out_of_sample"]["total_return_pct"] for fr in fold_results) / len(fold_results)
    print(f"  --- OUT-OF-SAMPLE agregado: {oos_trades} trades totales | Return medio por fold: {avg_oos_return:+.2f}% ---")


if __name__ == "__main__":
    print("=== OPTIMIZACION WALK-FORWARD (in-sample vs out-of-sample) ===")
    targets = [
        ("BTC/USDT", "4h"),
        ("ETH/USDT", "4h"),
        ("SOL/USDT", "4h"),
        ("BNB/USDT", "4h"),
        ("SOL/USDT", "1d"),
        ("BTC/USDT", "1d"),
    ]
    for symbol, timeframe in targets:
        try:
            fold_results = run_walk_forward(symbol, timeframe)
            print_fold_results(symbol, timeframe, fold_results)
        except Exception as e:
            print(f"Error {symbol} {timeframe}: {e}")
