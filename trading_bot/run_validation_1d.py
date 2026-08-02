import sys
sys.path.insert(0, r'c:\temp\2026\antigravity\estrategia-joveninversor\trading_bot')
from engine.data_fetcher import DataFetcher
from engine.backtester import Backtester
from config import DEFAULT_CONFIG

fetcher = DataFetcher()
for sym in ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT']:
    config = DEFAULT_CONFIG.copy()
    config['symbol'] = sym
    config['timeframe'] = '1d'
    config['initial_capital'] = 100.0
    try:
        df = fetcher.fetch_ohlcv(sym, '1d', limit=1500)
        res = Backtester(config).run(df)
        s = res['summary']
        print(
            f"{sym}: trades={s['total_trades']}, "
            f"wr={s['win_rate']:.1f}%, "
            f"pnl={s['total_net_pnl']:+.2f}, "
            f"ret={s['total_return_pct']:+.2f}%, "
            f"pf={s['profit_factor']:.2f}, "
            f"dd={s['max_drawdown']:.2f}%, "
            f"wins={s['winning_trades']}, "
            f"losses={s['losing_trades']}"
        )
    except Exception as e:
        print(f"{sym}: ERROR - {e}")
