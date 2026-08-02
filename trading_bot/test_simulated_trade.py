import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from engine.telegram_notifier import TelegramNotifier

notifier = TelegramNotifier()

print("1. Enviando alerta simulada de APERTURA DE OPERACIÓN a Telegram...")
open_success = notifier.send_trade_opened({
    "type": "LONG",
    "symbol": "SOL/USDT",
    "entry_price": 142.50,
    "stop_loss": 138.20,
    "take_profit": 153.25,
    "position_size_usd": 45.0,
    "reason": "Cruze de EMA20/EMA50 + Confirmación de Tendencia Macro EMA200",
    "entry_time": "2026-08-02 08:55:00"
})
print("Resultado apertura:", "EXITO (ENVIADO)" if open_success else "ERROR")

print("\n2. Enviando alerta simulada de CIERRE DE OPERACION a Telegram...")
close_success = notifier.send_trade_closed({
    "type": "LONG",
    "symbol": "SOL/USDT",
    "entry_price": 142.50,
    "exit_price": 153.25,
    "pnl_usd": 3.39,
    "pnl_pct": 7.54,
    "exit_reason": "Take Profit",
    "exit_time": "2026-08-02 08:55:05"
}, new_balance=63.39)
print("Resultado cierre:", "EXITO (ENVIADO)" if close_success else "ERROR")

print("\n3. Enviando REPORTE DIARIO DE MEDIODIA (12:00 PM) a Telegram...")
report_success = notifier.send_daily_report({
    "account_balance": 63.39,
    "completed_trades": [
        {"pnl_usd": 3.39, "type": "LONG", "symbol": "SOL/USDT"}
    ],
    "active_position": None
}, current_price=145.00)
print("Resultado reporte diario:", "EXITO (ENVIADO)" if report_success else "ERROR")

print("\n--- PRUEBA COMPLETADA EXITOSAMENTE ---")
