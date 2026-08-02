"""
Robustness report: aggregates walk-forward out-of-sample results across a symbol/timeframe
universe to answer one question - is this strategy reliable and profitable, or is any
apparent edge just noise/overfitting on a single dataset?

Reuses run_walk_forward from optimize_profitable.py (same Strategy/Backtester/walk-forward
split as the live bot) with reoptimize=False, so every fold is evaluated with the exact
DEFAULT_CONFIG (config.py) parameters that would actually run in production - never a
different best-of-grid combo per fold, which would validate a family of configs instead
of the one being deployed. Verdict is computed from the aggregated OUT-OF-SAMPLE numbers
only - in-sample results are not the story here.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from optimize_profitable import run_walk_forward

# (symbol, timeframe, candle limit to fetch)
# ~12000 4h candles / ~2000 1d candles cover roughly 5.5 years, reaching back
# past the 2021 bull peak and the full 2022 bear market instead of only the
# most recent ~14 months - a strategy that only "works" in one regime isn't
# validated by a sample that never contains a different one.
UNIVERSE = [
    ("BTC/USDT", "4h", 12000),
    ("ETH/USDT", "4h", 12000),
    ("SOL/USDT", "4h", 12000),
    ("BNB/USDT", "4h", 12000),
    ("BTC/USDT", "1d", 2000),
    ("ETH/USDT", "1d", 2000),
    ("SOL/USDT", "1d", 2000),
    ("BNB/USDT", "1d", 2000),
]
N_FOLDS = 5
MIN_OOS_TRADES_FOR_VERDICT = 10


def aggregate(fold_results):
    oos = [fr["out_of_sample"] for fr in fold_results]
    n = len(oos)
    total_trades = sum(o["total_trades"] for o in oos)
    total_wins = sum(o["winning_trades"] for o in oos)
    profitable_folds = sum(1 for o in oos if o["total_return_pct"] > 0)
    avg_return = sum(o["total_return_pct"] for o in oos) / n if n else 0.0
    worst_dd = max((o["max_drawdown"] for o in oos), default=0.0)

    # Pool gross profit/loss across every OOS trade instead of averaging each
    # fold's profit factor - averaging ratios lets a 4-trade fold (e.g. PF 5.14)
    # weigh as much as a 9-trade fold (PF 0.06), which misrepresents the
    # aggregate edge when fold sizes are this uneven.
    gross_profit = sum(o.get("gross_profit", 0.0) for o in oos)
    gross_loss = sum(o.get("gross_loss", 0.0) for o in oos)
    pooled_pf = (gross_profit / gross_loss) if gross_loss > 0 else (gross_profit if gross_profit > 0 else 0.0)
    pooled_win_rate = (total_wins / total_trades * 100.0) if total_trades > 0 else 0.0

    return {
        "folds": n,
        "profitable_folds": profitable_folds,
        "total_trades": total_trades,
        "avg_return_pct": avg_return,
        "win_rate": pooled_win_rate,
        "profit_factor": pooled_pf,
        "worst_drawdown": worst_dd,
    }


def verdict(agg):
    if agg["folds"] == 0 or agg["total_trades"] < MIN_OOS_TRADES_FOR_VERDICT:
        return "DATOS INSUFICIENTES"
    consistency = agg["profitable_folds"] / agg["folds"]
    if agg["avg_return_pct"] > 0 and agg["profit_factor"] >= 1.2 and consistency >= 0.6:
        return "CONFIABLE"
    if agg["avg_return_pct"] > 0 and agg["profit_factor"] >= 1.0:
        return "MARGINAL - vigilar"
    return "NO CONFIABLE"


def main():
    print("=== REPORTE DE ROBUSTEZ (walk-forward, solo out-of-sample) ===\n")
    all_results = []
    for symbol, timeframe, limit in UNIVERSE:
        try:
            fold_results = run_walk_forward(symbol, timeframe, limit=limit, n_folds=N_FOLDS, reoptimize=False)
            agg = aggregate(fold_results)
            v = verdict(agg)
            all_results.append((symbol, timeframe, agg, v))
            print(
                f"{symbol:10s} {timeframe:4s} | folds: {agg['folds']} ({agg['profitable_folds']} rentables) | "
                f"trades OOS: {agg['total_trades']:3d} | return medio/fold: {agg['avg_return_pct']:+6.2f}% | "
                f"win rate: {agg['win_rate']:5.1f}% | PF (agregado): {agg['profit_factor']:5.2f} | "
                f"peor DD: {agg['worst_drawdown']:5.2f}% | veredicto: {v}"
            )
        except Exception as e:
            print(f"Error {symbol} {timeframe}: {e}")

    print("\n--- RESUMEN GLOBAL ---")
    total_trades = sum(a["total_trades"] for _, _, a, _ in all_results)
    total_profitable_folds = sum(a["profitable_folds"] for _, _, a, _ in all_results)
    total_folds = sum(a["folds"] for _, _, a, _ in all_results)
    confiables = [f"{s} {tf}" for s, tf, a, v in all_results if v == "CONFIABLE"]
    marginales = [f"{s} {tf}" for s, tf, a, v in all_results if v == "MARGINAL - vigilar"]
    no_confiables = [f"{s} {tf}" for s, tf, a, v in all_results if v == "NO CONFIABLE"]

    fold_pct = (total_profitable_folds / total_folds * 100) if total_folds else 0.0
    print(f"Trades OOS totales: {total_trades} | Folds rentables: {total_profitable_folds}/{total_folds} ({fold_pct:.0f}%)")
    print(f"CONFIABLE: {confiables or 'ninguno'}")
    print(f"MARGINAL: {marginales or 'ninguno'}")
    print(f"NO CONFIABLE: {no_confiables or 'ninguno'}")


if __name__ == "__main__":
    main()
