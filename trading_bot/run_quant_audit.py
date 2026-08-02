import sys
import os
import json
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from engine.data_fetcher import DataFetcher
from engine.backtester import Backtester
from config import DEFAULT_CONFIG

SYMBOLS = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT', 'ADA/USDT']
TIMEFRAMES = ['15m', '1h', '4h', '1d']
CANDLE_LIMIT = 1500

def run_audit():
    fetcher = DataFetcher()
    results = []
    
    print("=" * 120, flush=True)
    print("                      AUDITORIA INTEGRAL Y ESCANEO DE VALIDACION CUANTITATIVA                      ", flush=True)
    print("=" * 120, flush=True)
    print(f"{'SYMBOL':10s} | {'TF':4s} | {'TRADES':6s} | {'WIN RATE':8s} | {'NET PnL ($)':12s} | {'RETURN %':9s} | {'PROFIT FACT':11s} | {'MAX DD %':8s} | {'SHARPE':7s}", flush=True)
    print("-" * 120, flush=True)

    for sym in SYMBOLS:
        for tf in TIMEFRAMES:
            try:
                config = DEFAULT_CONFIG.copy()
                config["symbol"] = sym
                config["timeframe"] = tf

                df = fetcher.fetch_ohlcv(sym, tf, limit=CANDLE_LIMIT)
                res = Backtester(config).run(df)
                s = res["summary"]
                
                row = {
                    "symbol": sym,
                    "timeframe": tf,
                    "candles_analyzed": len(df),
                    "start_date": str(df["timestamp"].iloc[0]),
                    "end_date": str(df["timestamp"].iloc[-1]),
                    "total_trades": s["total_trades"],
                    "winning_trades": s["winning_trades"],
                    "losing_trades": s["losing_trades"],
                    "win_rate": s["win_rate"],
                    "total_net_pnl": s["total_net_pnl"],
                    "total_return_pct": s["total_return_pct"],
                    "profit_factor": s["profit_factor"],
                    "max_drawdown": s["max_drawdown"],
                    "sharpe_ratio": s["sharpe_ratio"],
                    "kill_switch_triggered": s["kill_switch_triggered"]
                }
                results.append(row)
                
                print(f"{sym:10s} | {tf:4s} | {s['total_trades']:6d} | {s['win_rate']:7.1f}% | ${s['total_net_pnl']:11.2f} | {s['total_return_pct']:8.2f}% | {s['profit_factor']:11.2f} | {s['max_drawdown']:7.2f}% | {s['sharpe_ratio']:7.2f}", flush=True)
            except Exception as e:
                print(f"Error procesando {sym} {tf}: {e}", flush=True)

    print("=" * 120, flush=True)
    
    # Save raw results as json for analysis / reporting
    out_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "quant_audit_results.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
        
    print(f"\nResultados guardados exitosamente en {out_file}", flush=True)

if __name__ == "__main__":
    run_audit()
