import sys, os
sys.path.insert(0, r'C:\Users\Pc\.gemini\antigravity\scratch\trading_bot')

from config import DEFAULT_CONFIG
from engine.data_fetcher import DataFetcher
from engine.backtester import Backtester

fetcher = DataFetcher()

print(f"{'SYMBOL':10s} | {'TF':3s} | {'TRADES':6s} | {'WIN RATE':8s} | {'NET PnL ($)':12s} | {'PROFIT FACTOR':13s}")
print("-" * 65)

for sym in ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT']:
    for tf in ['15m', '1h', '4h', '1d']:
        try:
            df = fetcher.fetch_ohlcv(sym, tf, limit=500)
            bt = Backtester(DEFAULT_CONFIG)
            res = bt.run(df)
            s = res['summary']
            print(f"{sym:10s} | {tf:3s} | {s['total_trades']:6d} | {s['win_rate']:7.1f}% | ${s['total_net_pnl']:11.2f} | {s['profit_factor']:13.2f}")
        except Exception as e:
            print(f"Error {sym} {tf}: {e}")
