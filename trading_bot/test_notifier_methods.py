import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from engine.telegram_notifier import TelegramNotifier

notifier = TelegramNotifier()

print("Testing trade opened notification...")
notifier.send_trade_opened({
    "type": "LONG",
    "symbol": "BTC/USDT",
    "entry_price": 64500.0,
    "stop_loss": 63200.0,
    "take_profit": 67750.0,
    "position_size_usd": 150.0,
    "reason": "Cruze de EMA20/EMA50 + Confirmación MACD",
    "entry_time": "2026-08-01 09:15:00"
})

print("Testing trade closed notification...")
notifier.send_trade_closed({
    "type": "LONG",
    "symbol": "BTC/USDT",
    "entry_price": 64500.0,
    "exit_price": 67750.0,
    "pnl_usd": 7.55,
    "pnl_pct": 5.03,
    "exit_reason": "Take Profit",
    "exit_time": "2026-08-01 11:45:00"
}, new_balance=1007.55)

print("Testing daily report notification...")
notifier.send_daily_report({
    "account_balance": 1007.55,
    "completed_trades": [
        {"pnl_usd": 7.55, "type": "LONG", "symbol": "BTC/USDT"}
    ],
    "active_position": {
        "type": "LONG",
        "symbol": "SOL/USDT",
        "entry_price": 145.20,
        "stop_loss": 141.10,
        "take_profit": 155.45,
        "position_size_asset": 1.03
    }
}, current_price=147.50)

print("All telegram notification tests executed successfully!")
