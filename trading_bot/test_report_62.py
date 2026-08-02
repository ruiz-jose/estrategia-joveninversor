import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from engine.testnet_trader import BinanceTestnetTrader

trader = BinanceTestnetTrader()
data = trader.load_active_trades()

print("Current Account Balance in Engine:", data.get("account_balance"))

res = trader.send_midday_report()
print("Send Telegram report result:", res)
