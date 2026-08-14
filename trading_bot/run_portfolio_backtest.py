"""
Portfolio-level backtest: runs every symbol config["symbols"] concurrently against
a single shared balance, with a portfolio-wide drawdown kill-switch and a
max_concurrent_positions cap - the scenario engine/backtester.py's single-symbol
runs (run_quant_audit.py, robustness_report.py, etc.) cannot represent, but that
engine/testnet_trader.py actually runs in production. Existing single-symbol
backtests certify each pair in isolation with 100% of the capital available to it;
this script certifies what actually happens when all of them trade at once.
"""
import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from engine.data_fetcher import DataFetcher
from engine.portfolio_backtester import PortfolioBacktester
from config import DEFAULT_CONFIG

CANDLE_LIMIT = 3000


def run_portfolio_backtest():
    fetcher = DataFetcher()
    config = DEFAULT_CONFIG.copy()
    symbols = config.get("symbols") or [config.get("symbol", "BTC/USDT")]
    timeframe = config.get("timeframe", "4h")

    print(f"=== BACKTEST DE PORTAFOLIO (multi-simbolo, balance compartido) ===")
    print(f"Simbolos: {symbols} | Timeframe: {timeframe} | Capital inicial: ${config.get('initial_capital', 100.0):.2f}")
    print(f"max_concurrent_positions: {config.get('max_concurrent_positions', 3)} | max_drawdown_pct: {config.get('max_drawdown_pct', 25.0)}%\n")

    dfs_by_symbol = {}
    for symbol in symbols:
        try:
            dfs_by_symbol[symbol] = fetcher.fetch_ohlcv(symbol, timeframe, limit=CANDLE_LIMIT)
        except Exception as e:
            print(f"Error descargando {symbol}: {e}")

    if len(dfs_by_symbol) < 2:
        print("Se necesitan al menos 2 simbolos con datos para un backtest de portafolio.")
        return None

    result = PortfolioBacktester(config).run(dfs_by_symbol)
    s = result["summary"]

    print("--- RESULTADO AGREGADO DEL PORTAFOLIO ---")
    print(f"Balance final: ${s['final_balance']:.2f} (inicial ${s['initial_capital']:.2f}) | Return: {s['total_return_pct']:+.2f}%")
    print(f"Trades totales: {s['total_trades']} | Win rate: {s['win_rate']:.1f}% | Profit factor: {s['profit_factor']:.2f}")
    print(f"Max drawdown (portafolio): {s['max_drawdown']:.2f}% | Kill-switch disparado: {s['kill_switch_triggered']}")
    print(f"Sharpe (aprox): {s['sharpe_ratio']:.2f}")
    print(f"Trades por simbolo: {s['trades_per_symbol']}")

    out_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "portfolio_backtest_results.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    print(f"\nResultados guardados en {out_file}")

    return result


if __name__ == "__main__":
    run_portfolio_backtest()
