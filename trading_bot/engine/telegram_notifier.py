import os
import requests
import datetime
import html

class TelegramNotifier:
    """
    Telegram Notifier Module for Trading Bot.
    Handles automated real-time trade notifications and daily status reports.
    """
    def __init__(self, bot_token: str = None, chat_id: str = None):
        self._load_env_file()
        self.bot_token = bot_token or os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID")
        self.api_url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage" if self.bot_token else None

    def _load_env_file(self):
        """Helper to load .env file if environment variables are not set."""
        if not os.getenv("TELEGRAM_BOT_TOKEN"):
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            env_path = os.path.join(base_dir, ".env")
            if os.path.exists(env_path):
                try:
                    with open(env_path, "r", encoding="utf-8") as f:
                        for line in f:
                            line = line.strip()
                            if line and not line.startswith("#") and "=" in line:
                                k, v = line.split("=", 1)
                                os.environ[k.strip()] = v.strip()
                except Exception as e:
                    print(f"[TelegramNotifier] Error loading .env: {e}")

    def is_configured(self) -> bool:
        return bool(self.bot_token and self.chat_id)

    def send_message(self, text: str, parse_mode: str = "HTML") -> bool:
        """Sends a text message to the configured Telegram chat."""
        if not self.is_configured():
            print("[TelegramNotifier] Warning: Telegram credentials not configured.")
            return False
            
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": parse_mode
        }
        
        try:
            resp = requests.post(self.api_url, json=payload, timeout=8)
            if resp.status_code == 200:
                return True
            else:
                print(f"[TelegramNotifier] API Error {resp.status_code}: {resp.text}")
                return False
        except Exception as e:
            print(f"[TelegramNotifier] Connection Exception: {e}")
            return False

    def send_trade_opened(self, trade_info: dict) -> bool:
        """Notifies when a new trade is opened."""
        pos_type = trade_info.get("type", "LONG")
        emoji_type = "🟢 LONG (Compra)" if pos_type == "LONG" else "🔴 SHORT (Venta)"
        symbol = trade_info.get("symbol", "N/A")
        entry = float(trade_info.get("entry_price", 0))
        sl = float(trade_info.get("stop_loss", 0))
        tp = float(trade_info.get("take_profit", 0))
        size_usd = float(trade_info.get("position_size_usd", 0))
        reason = html.escape(str(trade_info.get("reason", "Señal técnica detectada")))
        time_str = trade_info.get("entry_time", datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

        sl_pct = ((sl - entry) / entry * 100) if entry > 0 else 0
        tp_pct = ((tp - entry) / entry * 100) if entry > 0 else 0

        is_testnet = os.getenv("TESTNET", "false").lower() == "true"
        mode_badge = " [TESTNET]" if is_testnet else " [TRADING REAL]"

        msg = (
            f"🚀 <b>NUEVA OPERACIÓN ABIERTA</b>{mode_badge}\n\n"
            f"• <b>Símbolo:</b> <code>{symbol}</code>\n"
            f"• <b>Dirección:</b> {emoji_type}\n"
            f"• <b>Precio Entrada:</b> ${entry:,.2f}\n"
            f"• <b>Stop Loss:</b> ${sl:,.2f} ({sl_pct:+.2f}%)\n"
            f"• <b>Take Profit:</b> ${tp:,.2f} ({tp_pct:+.2f}%)\n"
            f"• <b>Monto Operado:</b> ${size_usd:,.2f} USDT\n"
            f"• <b>Estrategia / Confluencia:</b> {reason}\n"
            f"• <b>Fecha:</b> {time_str}\n"
        )
        return self.send_message(msg)

    def send_trade_closed(self, trade_record: dict, new_balance: float) -> bool:
        """Notifies when a trade is closed."""
        pos_type = trade_record.get("type", "LONG")
        symbol = trade_record.get("symbol", "N/A")
        entry = float(trade_record.get("entry_price", 0))
        exit_p = float(trade_record.get("exit_price", 0))
        pnl_usd = float(trade_record.get("pnl_usd", 0))
        pnl_pct = float(trade_record.get("pnl_pct", 0))
        reason = html.escape(str(trade_record.get("exit_reason", "Cierre de posición")))
        time_str = trade_record.get("exit_time", datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

        is_win = pnl_usd >= 0
        header_emoji = "🎯" if is_win else "🛑"
        pnl_emoji = "🟢" if is_win else "🔴"

        is_testnet = os.getenv("TESTNET", "false").lower() == "true"
        mode_badge = " (Testnet)" if is_testnet else ""

        msg = (
            f"{header_emoji} <b>OPERACIÓN CERRADA - {reason.upper()}</b>{mode_badge}\n\n"
            f"• <b>Símbolo:</b> <code>{symbol}</code> ({pos_type})\n"
            f"• <b>Precio Entrada:</b> ${entry:,.2f}\n"
            f"• <b>Precio Salida:</b> ${exit_p:,.2f}\n"
            f"• <b>PnL Neto:</b> {pnl_emoji} <b>${pnl_usd:+,.2f} USDT ({pnl_pct:+.2f}%)</b>\n"
            f"• <b>Motivo Salida:</b> {reason}\n"
            f"• <b>Nuevo Balance:</b> <b>${new_balance:,.2f} USDT</b>\n"
            f"• <b>Fecha Cierre:</b> {time_str}\n"
        )
        return self.send_message(msg)

    def send_daily_report(self, state: dict, current_price: float = None, current_prices: dict = None) -> bool:
        """Sends midday (12:00 PM) report with account balance and state.

        `current_prices` maps symbol -> latest price, used to compute floating
        PnL per open position. `current_price` (single value) is kept as a
        fallback for callers that only track one symbol.
        """
        env_capital = float(os.getenv("INITIAL_CAPITAL", 60.0))
        initial_capital = float(state.get("initial_capital", env_capital))
        balance = float(state.get("account_balance", initial_capital))
        completed_trades = state.get("completed_trades", [])
        active_positions = state.get("active_positions") or {}
        if not active_positions and state.get("active_position"):
            legacy_pos = state["active_position"]
            active_positions = {legacy_pos.get("symbol", "N/A"): legacy_pos}
        current_prices = current_prices or {}

        net_return_usd = balance - initial_capital
        net_return_pct = (net_return_usd / initial_capital * 100.0) if initial_capital > 0 else 0.0

        tot_trades = len(completed_trades)
        wins = len([t for t in completed_trades if t.get("pnl_usd", 0) > 0])
        losses = tot_trades - wins
        win_rate = (wins / tot_trades * 100.0) if tot_trades > 0 else 0.0

        pnl_emoji = "📈" if net_return_usd >= 0 else "📉"

        pos_text = "<i>Sin posiciones abiertas en este momento.</i>"
        if active_positions:
            blocks = []
            for a_sym, active_pos in active_positions.items():
                a_type = active_pos.get("type", "LONG")
                a_entry = float(active_pos.get("entry_price", 0))
                a_sl = float(active_pos.get("stop_loss", 0))
                a_tp = float(active_pos.get("take_profit", 0))

                price_for_symbol = current_prices.get(a_sym, current_price)
                floating_pnl_str = ""
                if price_for_symbol and a_entry > 0:
                    qty = float(active_pos.get("position_size_asset", 0))
                    float_pnl = (price_for_symbol - a_entry) * qty if a_type == "LONG" else (a_entry - price_for_symbol) * qty
                    floating_pnl_str = f"\n  └ <b>PnL Flotante:</b> ${float_pnl:+,.2f} USDT"

                blocks.append(
                    f"• <b>{a_sym} ({a_type})</b>\n"
                    f"  └ <b>Entrada:</b> ${a_entry:,.2f}\n"
                    f"  └ <b>Stop Loss:</b> ${a_sl:,.2f} | <b>Take Profit:</b> ${a_tp:,.2f}"
                    f"{floating_pnl_str}"
                )
            pos_text = "\n\n".join(blocks)

        now_str = datetime.datetime.now().strftime("%d/%m/%Y - %H:%M")
        is_testnet = os.getenv("TESTNET", "false").lower() == "true"
        mode_str = "Binance Testnet (Simulado)" if is_testnet else "Binance Spot (Trading Real)"

        msg = (
            f"☀️ <b>REPORTE DIARIO DE ESTADO (12:00 PM)</b>\n"
            f"<i>{now_str}</i>\n\n"
            f"💰 <b>Balance y Capital:</b>\n"
            f"• <b>Balance Actual:</b> <b>${balance:,.2f} USDT</b>\n"
            f"• <b>Capital Inicial:</b> ${initial_capital:,.2f} USDT\n"
            f"• <b>Rendimiento Neto:</b> {pnl_emoji} <b>${net_return_usd:+,.2f} USDT ({net_return_pct:+.2f}%)</b>\n\n"
            f"📊 <b>Estadísticas de Operaciones:</b>\n"
            f"• <b>Total Operaciones:</b> {tot_trades}\n"
            f"• <b>Ganadas / Perdidas:</b> {wins} 🟢 / {losses} 🔴\n"
            f"• <b>Win Rate:</b> {win_rate:.1f}%\n\n"
            f"📍 <b>Posición Activa:</b>\n"
            f"{pos_text}\n\n"
            f"🤖 <b>Estado del Sistema:</b> Bot activo y monitoreando operaciones en <b>{mode_str}</b>."
        )
        return self.send_message(msg)
