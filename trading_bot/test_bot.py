import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import DEFAULT_CONFIG
from engine.data_fetcher import DataFetcher
from engine.backtester import Backtester
from core.indicators import add_all_indicators
from core.strategy import Strategy
from core.risk_manager import RiskManager

def test_all():
    print("=== Testing Data Fetcher ===")
    fetcher = DataFetcher()
    df = fetcher.fetch_ohlcv("BTC/USDT", "1h", limit=300)
    print(f"Fetched {len(df)} candles for BTC/USDT")
    print(df.head(2))

    print("\n=== Testing Indicators ===")
    df_ind = add_all_indicators(df, DEFAULT_CONFIG)
    print("Indicators added successfully. Columns:", list(df_ind.columns))

    print("\n=== Testing Strategy ===")
    strat = Strategy(DEFAULT_CONFIG)
    df_sig = strat.generate_signals(df_ind)
    signals_count = (df_sig["signal"] != 0).sum()
    print(f"Total trading signals generated: {signals_count}")

    print("\n=== Testing Backtester ===")
    backtester = Backtester(DEFAULT_CONFIG)
    res = backtester.run(df)
    summary = res["summary"]
    print("Backtest Summary:", summary)
    print(f"Total trades: {len(res['trades'])}")
    if len(res['trades']) > 0:
        print("Sample Trade 1:", res['trades'][0])

    print("\nALL VERIFICATION TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    test_all()
