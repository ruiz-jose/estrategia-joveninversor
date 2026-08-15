import threading
import time


class TelegramCommandHandler:
    """
    Long-polls Telegram for inbound messages and replies to a small set of
    read-only commands (/balance, /abiertas, /cerradas) with the live bot's
    current state. Complements TelegramNotifier, which only sends outbound
    notifications - this is the inbound half.

    Only replies to messages from the configured TELEGRAM_CHAT_ID (the
    notifier's own chat_id); anything else is ignored so a stranger who
    somehow messages the bot can't pull account/trading data out of it.
    """

    COMMANDS = {
        "/balance": "_reply_balance",
        "/abiertas": "_reply_open_orders",
        "/ordenes_abiertas": "_reply_open_orders",
        "/cerradas": "_reply_closed_orders",
        "/ordenes_cerradas": "_reply_closed_orders",
        "/historial": "_reply_closed_orders",
        "/start": "_reply_help",
        "/help": "_reply_help",
        "/ayuda": "_reply_help",
    }

    def __init__(self, trader, notifier, poll_timeout: int = 25):
        self.trader = trader
        self.notifier = notifier
        self.poll_timeout = poll_timeout
        self._offset = None

    def start(self):
        if not self.notifier.is_configured():
            print("[TelegramCommands] Sin credenciales de Telegram configuradas - listener no iniciado.")
            return
        t = threading.Thread(target=self._loop, daemon=True)
        t.start()
        print("[TelegramCommands] Listener de comandos Telegram iniciado (/balance, /abiertas, /cerradas).")

    def _loop(self):
        while True:
            try:
                updates = self.notifier.get_updates(offset=self._offset, timeout=self.poll_timeout)
                for update in updates:
                    self._offset = update["update_id"] + 1
                    self._handle_update(update)
            except Exception as e:
                print(f"[TelegramCommands] Error en el loop de polling: {e}")
                time.sleep(5)

    def _handle_update(self, update: dict):
        message = update.get("message") or update.get("edited_message")
        if not message or "text" not in message:
            return

        chat_id = str(message.get("chat", {}).get("id", ""))
        if not self.notifier.chat_id or chat_id != str(self.notifier.chat_id):
            print(f"[TelegramCommands] Mensaje ignorado de chat no autorizado: {chat_id}")
            return

        command = message["text"].strip().split()[0].split("@")[0].lower()
        handler_name = self.COMMANDS.get(command)
        if handler_name:
            getattr(self, handler_name)()

    def _reply_help(self):
        self.notifier.send_message(
            "🤖 <b>Comandos disponibles</b>\n\n"
            "/balance — balance actual, capital inicial y rendimiento\n"
            "/abiertas — posiciones abiertas ahora mismo\n"
            "/cerradas — últimas operaciones cerradas"
        )

    def _reply_balance(self):
        state = self.trader.load_active_trades()
        self.notifier.send_message(self.notifier.format_balance_message(state))

    def _reply_open_orders(self):
        state = self.trader.load_active_trades()
        active_positions = state.get("active_positions") or {}

        current_prices = {}
        for symbol in active_positions:
            try:
                current_prices[symbol] = float(self.trader.exchange.fetch_ticker(symbol)["last"])
            except Exception as e:
                print(f"[TelegramCommands] No se pudo obtener precio actual de {symbol}: {e}")

        self.notifier.send_message(self.notifier.format_open_orders_message(active_positions, current_prices))

    def _reply_closed_orders(self):
        state = self.trader.load_active_trades()
        trades = state.get("completed_trades", [])
        self.notifier.send_message(self.notifier.format_closed_orders_message(trades, limit=10))
