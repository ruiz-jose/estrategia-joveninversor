import ccxt
import time
import json
import os
import sys
import threading

# Add parent path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import DEFAULT_CONFIG
from engine.data_fetcher import DataFetcher
from engine.telegram_notifier import TelegramNotifier
from core.indicators import add_all_indicators
from core.strategy import Strategy
from core.risk_manager import RiskManager

class BinanceTestnetTrader:
    """
    Candle-based trading monitor using Binance market data.

    When valid API credentials are present (BINANCE_API_KEY/SECRET in .env), LONG
    entries/exits are submitted as real market orders (Testnet or real account,
    per TESTNET). SHORT signals are never sent for real: a Spot account cannot
    short-sell, so they are logged/notified and skipped. Without credentials it
    falls back to the original local-only paper-trading simulation.
    """

    def __init__(self, api_key: str = None, api_secret: str = None, testnet: bool = None):
        self._file_lock = threading.Lock()
        self.config = DEFAULT_CONFIG.copy()
        self.fetcher = DataFetcher()
        self.strategy = Strategy(self.config)
        self.risk_manager = RiskManager(self.config)
        self.notifier = TelegramNotifier()  # also loads .env into os.environ as a side effect

        self.testnet = testnet if testnet is not None else (os.getenv("TESTNET", "true").lower() == "true")
        api_key = api_key or os.getenv("BINANCE_API_KEY")
        api_secret = api_secret or os.getenv("BINANCE_API_SECRET")

        self.trade_log_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "live_testnet_trades.json")
        self.slippage_pct = float(self.config.get("slippage_pct", 0.0005))
        self.max_drawdown_pct = float(self.config.get("max_drawdown_pct", 25.0))
        self.min_signal_strength = float(self.config.get("min_signal_strength", 4))
        self.min_notional_usd = float(self.config.get("min_notional_usd", 10.0))

        # Initialize CCXT Binance Exchange
        self.exchange = ccxt.binance({
            "apiKey": api_key or "",
            "secret": api_secret or "",
            "enableRateLimit": True,
            "options": {
                "defaultType": "spot",
            }
        })

        if self.testnet:
            try:
                self.exchange.set_sandbox_mode(True)
            except Exception:
                # Fallback for ccxt versions without full Binance sandbox url mapping.
                self.exchange.urls["api"] = {
                    "public": "https://testnet.binance.vision/api",
                    "private": "https://testnet.binance.vision/api",
                }

        # Real order placement requires valid, correctly-scoped credentials (Testnet
        # keys only work against testnet.binance.vision; real-account keys only
        # work against the live API - they are never interchangeable).
        self.live_trading_enabled = bool(api_key and api_secret)
        if self.live_trading_enabled:
            try:
                self.exchange.load_markets()
                self.exchange.fetch_balance()  # validates the API key/secret actually authenticate here
                print(f"[LiveTrading] Ordenes reales HABILITADAS en {'Binance Testnet' if self.testnet else 'Binance REAL'} para {self.config.get('symbol')}.")
            except Exception as e:
                print(f"[LiveTrading] No se pudo autenticar contra Binance ({'Testnet' if self.testnet else 'Real'}): {e}. Se desactivan las ordenes reales, cae a simulacion local.")
                self.live_trading_enabled = False

    def _place_market_order(self, symbol: str, side: str, amount: float):
        """
        Submits a real market order to Binance (Testnet or real, per self.testnet).
        Returns (filled_amount, avg_fill_price).
        """
        amount = float(self.exchange.amount_to_precision(symbol, amount))
        if amount <= 0:
            raise ValueError(f"El monto de la orden redondea a 0 con la precision del exchange para {symbol}.")

        order = self.exchange.create_order(symbol, "market", side, amount)

        filled = order.get("filled") or order.get("amount") or amount
        avg_price = order.get("average") or order.get("price")
        if not avg_price:
            cost = order.get("cost")
            if cost and filled:
                avg_price = float(cost) / float(filled)

        return float(filled), (float(avg_price) if avg_price else None)

    def load_active_trades(self):
        """Load live trades log from JSON file and sync live Binance balance if available."""
        with self._file_lock:
            data = None
            if os.path.exists(self.trade_log_file):
                try:
                    with open(self.trade_log_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                except Exception as e:
                    print(f"Error loading trades log: {e}")
                    
            if not data:
                env_cap = float(os.getenv("INITIAL_CAPITAL", self.config.get("initial_capital", 60.0)))
                initial_balance = min(float(self.config.get("initial_capital", 60.0)), env_cap)

                # Seed the paper-trading balance from the real account on first run,
                # but never exceed the configured capital allocation.
                api_key = os.getenv("BINANCE_API_KEY")
                api_secret = os.getenv("BINANCE_API_SECRET")
                testnet = os.getenv("TESTNET", "true").lower() == "true"
                if api_key and api_secret and not testnet:
                    try:
                        ex = ccxt.binance({
                            "apiKey": api_key,
                            "secret": api_secret,
                            "enableRateLimit": True,
                            "options": {"defaultType": "spot"}
                        })
                        bal = ex.fetch_balance()
                        total_usdt = float(bal.get("USDT", {}).get("total", 0.0))
                        if total_usdt > 0:
                            initial_balance = min(initial_balance, total_usdt)
                    except Exception:
                        pass

                data = {
                    "initial_capital": round(initial_balance, 2),
                    "account_balance": round(initial_balance, 2),
                    "peak_balance": round(initial_balance, 2),
                    "trading_halted": False,
                    "active_positions": {},
                    "completed_trades": []
                }

            data.setdefault("initial_capital", float(os.getenv("INITIAL_CAPITAL", self.config.get("initial_capital", 60.0))))
            data.setdefault("peak_balance", data.get("account_balance", float(self.config.get("initial_capital", 60.0))))
            data.setdefault("trading_halted", False)

            # Migrate legacy single-position schema ({"active_position": {...} | None})
            # to the multi-symbol dict keyed by symbol.
            if "active_position" in data:
                legacy_pos = data.pop("active_position")
                active_positions = data.setdefault("active_positions", {})
                if legacy_pos:
                    active_positions[legacy_pos["symbol"]] = legacy_pos
            data.setdefault("active_positions", {})

            return data

    def save_active_trades(self, data):
        """Save trades log to JSON file."""
        with self._file_lock:
            try:
                with open(self.trade_log_file, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2)
            except Exception as e:
                print(f"Error saving trades log: {e}")

    def check_market_and_execute(self):
        """
        Main execution loop step, run once per configured symbol:
        1. Download latest candles for each symbol & the configured timeframe.
        2. Calculate indicators & signals.
        3. Check each symbol's active position (SL / TP / Trailing Stop).
        4. Execute a new signal per symbol if that symbol has no active position.

        All symbols share a single account balance/equity curve, so the
        drawdown kill-switch is evaluated once per call across every open
        position before any symbol's entries/exits are processed.
        """
        symbols = self.config.get("symbols") or [self.config.get("symbol", "BTC/USDT")]
        timeframe = self.config.get("timeframe", "4h")

        data = self.load_active_trades()
        balance = float(data.get("account_balance", 1000.0))
        peak_balance = float(data.get("peak_balance", balance))
        trading_halted = bool(data.get("trading_halted", False))
        active_positions = data.get("active_positions", {})

        # 1. Fetch OHLCV data & signals for every symbol up front, so the
        # drawdown/kill-switch check below sees this tick's price for every
        # open position before any symbol's entry/exit logic runs.
        latest_by_symbol = {}
        for symbol in symbols:
            try:
                df = self.fetcher.fetch_ohlcv(symbol, timeframe, limit=300)
                df_ind = add_all_indicators(df, self.config)
                df_sig = self.strategy.generate_signals(df_ind)
                latest_by_symbol[symbol] = df_sig.iloc[-1]
            except Exception as e:
                print(f"Error fetching/processing {symbol}: {e}")

        # Drawdown kill-switch: track peak equity (balance + floating PnL of
        # every open position) and halt new entries once exceeded.
        current_equity = balance
        for symbol, active_pos in active_positions.items():
            latest_candle = latest_by_symbol.get(symbol)
            price = float(latest_candle["close"]) if latest_candle is not None else float(active_pos["entry_price"])
            entry_price = float(active_pos["entry_price"])
            qty = float(active_pos["position_size_asset"])
            if active_pos["type"] == "LONG":
                current_equity += (price - entry_price) * qty
            else:
                current_equity += (entry_price - price) * qty

        if current_equity > peak_balance:
            peak_balance = current_equity
        drawdown_pct = (peak_balance - current_equity) / peak_balance * 100.0 if peak_balance > 0 else 0.0

        if not trading_halted and drawdown_pct >= self.max_drawdown_pct:
            trading_halted = True
            print(f"[KILL-SWITCH] Drawdown {drawdown_pct:.2f}% >= {self.max_drawdown_pct:.2f}% - pausing new entries.")
            self.notifier.send_message(
                f"🛑 <b>KILL-SWITCH ACTIVADO</b>\n\nDrawdown actual: {drawdown_pct:.2f}% (límite {self.max_drawdown_pct:.2f}%).\nSe pausa la apertura de nuevas operaciones hasta revisión manual."
            )

        data["peak_balance"] = round(float(peak_balance), 2)
        data["trading_halted"] = trading_halted

        # 2-4. Process each symbol's position management & entry signal in turn,
        # re-reading `balance` after every close/open so later symbols in the
        # loop size new trades off the up-to-date shared balance.
        for symbol, latest_candle in latest_by_symbol.items():
            balance = float(data.get("account_balance", balance))
            active_pos = active_positions.get(symbol)
            self._process_symbol(symbol, timeframe, latest_candle, data, active_positions, active_pos, balance, trading_halted)

        data["active_positions"] = active_positions
        self.save_active_trades(data)
        return data

    def _process_symbol(self, symbol, timeframe, latest_candle, data, active_positions, active_pos, balance, trading_halted):
        """Position management (SL/TP) and new-entry logic for a single symbol."""
        curr_price = float(latest_candle["close"])
        candle_high = float(latest_candle["high"])
        candle_low = float(latest_candle["low"])
        timestamp = str(latest_candle["timestamp"])

        print(f"[{timestamp}] Checking {symbol} ({timeframe}) - Current Price: ${curr_price:,.2f} | Balance: ${balance:,.2f}")

        # 2. Check Active Position
        if active_pos is not None:
            pos_type = active_pos["type"]
            entry_price = float(active_pos["entry_price"])
            sl = float(active_pos["stop_loss"])
            tp = float(active_pos["take_profit"])
            sl_dist = float(active_pos["sl_distance"])
            qty = float(active_pos["position_size_asset"])
            
            # Check SL/TP against the stop as it stood entering this candle,
            # before any break-even adjustment based on this candle's price.
            exit_price = None
            exit_reason = None

            if pos_type == "LONG":
                if candle_low <= sl:
                    exit_price = sl * (1 - self.slippage_pct)
                    exit_reason = "Break-Even / Stop Loss" if sl >= entry_price else "Stop Loss"
                elif candle_high >= tp:
                    exit_price = tp
                    exit_reason = "Take Profit"
            else: # SHORT
                if candle_high >= sl:
                    exit_price = sl * (1 + self.slippage_pct)
                    exit_reason = "Break-Even / Stop Loss" if sl <= entry_price else "Stop Loss"
                elif candle_low <= tp:
                    exit_price = tp
                    exit_reason = "Take Profit"

            if exit_price is None:
                # Not stopped/hit-target this check: tighten the stop for the
                # next check using the current price.
                new_sl = self.risk_manager.update_trailing_stop(curr_price, entry_price, sl, 1 if pos_type == "LONG" else -1, sl_dist)
                active_pos["stop_loss"] = float(new_sl)

            if exit_price is not None:
                if active_pos.get("live") and self.live_trading_enabled:
                    try:
                        # LONG-only: SHORT positions are never opened as real orders (see entry logic).
                        filled_qty, avg_price = self._place_market_order(symbol, "sell", qty)
                        if avg_price:
                            exit_price = avg_price
                        print(f"[LiveTrading] Orden REAL de venta ejecutada: {filled_qty} {symbol} @ ${exit_price:,.2f} ({exit_reason})")
                    except Exception as e:
                        print(f"[LiveTrading] Error al cerrar posicion real {pos_type} {symbol}: {e}")
                        self.notifier.send_message(
                            f"⚠️ <b>Error cerrando posicion REAL</b>\n{pos_type} {symbol} deberia cerrar por {exit_reason} pero la orden fallo: {e}\nRevisa manualmente en Binance."
                        )
                        # Keep the position open locally so the next check retries the close.
                        return

                pnl_gross = (exit_price - entry_price) * qty if pos_type == "LONG" else (entry_price - exit_price) * qty
                fee = (active_pos["position_size_usd"] + (qty * exit_price)) * 0.00075
                net_pnl = pnl_gross - fee
                new_balance = balance + net_pnl
                
                trade_record = {
                    "id": len(data["completed_trades"]) + 1,
                    "type": pos_type,
                    "symbol": symbol,
                    "entry_time": active_pos["entry_time"],
                    "entry_price": entry_price,
                    "exit_time": timestamp,
                    "exit_price": exit_price,
                    "pnl_usd": round(net_pnl, 2),
                    "pnl_pct": round((net_pnl / active_pos["position_size_usd"]) * 100.0, 2),
                    "exit_reason": exit_reason,
                    "live": bool(active_pos.get("live", False))
                }
                
                data["completed_trades"].append(trade_record)
                data["account_balance"] = round(new_balance, 2)
                active_positions.pop(symbol, None)
                print(f"CLOSED POSITION {pos_type} {symbol} @ ${exit_price:,.2f} | Reason: {exit_reason} | PnL: ${net_pnl:+.2f}")

                # Send Telegram Notification on Trade Close
                self.notifier.send_trade_closed(trade_record, round(new_balance, 2))
                return

        # 3. Check for New Entry Signal
        if (not trading_halted and active_pos is None and latest_candle["signal"] != 0
                and latest_candle["signal_strength"] >= self.min_signal_strength):
            signal_type = int(latest_candle["signal"])

            # Fill at the live market price, not the (by now stale) close of the
            # candle that generated the signal - closer to how the backtester
            # fills at the next candle's open instead of the signal candle's own close.
            try:
                ticker = self.exchange.fetch_ticker(symbol)
                market_price = float(ticker["last"])
            except Exception as e:
                print(f"Error fetching live ticker for {symbol}, falling back to last close: {e}")
                market_price = curr_price

            fill_price = market_price * (1 + self.slippage_pct) if signal_type == 1 else market_price * (1 - self.slippage_pct)
            levels = self.risk_manager.calculate_trade_levels(
                entry_price=fill_price,
                atr=float(latest_candle["atr"]),
                signal_type=signal_type,
                current_balance=balance,
                ema50=float(latest_candle["ema_50"])
            )

            # Skip entries too small to actually place on Binance.
            if levels["position_size_usd"] < self.min_notional_usd:
                print(f"Signal skipped: position size ${levels['position_size_usd']:.2f} below min notional ${self.min_notional_usd:.2f}")
                return

            # A Spot account cannot short-sell an asset it doesn't hold. Real order
            # placement is LONG-only; SHORT signals are logged/notified and skipped
            # rather than silently faked, so the local state never claims a real
            # position that doesn't exist on the exchange.
            if signal_type == -1 and self.live_trading_enabled:
                print(f"Signal SHORT ignorado en {symbol}: cuenta Spot no admite venta en corto (requiere Margin/Futures).")
                self.notifier.send_message(
                    f"ℹ️ Señal SHORT detectada en {symbol} (fuerza {int(latest_candle['signal_strength'])}) pero se ignora: cuenta Spot no permite abrir cortos reales."
                )
                return

            qty = levels["position_size_asset"]
            is_live_order = False

            if signal_type == 1 and self.live_trading_enabled:
                try:
                    filled_qty, avg_price = self._place_market_order(symbol, "buy", qty)
                    if avg_price:
                        # Shift SL/TP by the same absolute distance the real fill
                        # deviated from the pre-trade estimate, preserving the
                        # intended $ risk instead of re-deriving levels from scratch.
                        delta = avg_price - fill_price
                        levels["stop_loss"] += delta
                        levels["take_profit"] += delta
                        fill_price = avg_price
                    if filled_qty:
                        qty = filled_qty
                    levels["position_size_usd"] = qty * fill_price
                    is_live_order = True
                    print(f"[LiveTrading] Orden REAL de compra ejecutada: {qty} {symbol} @ ${fill_price:,.2f} ({'Testnet' if self.testnet else 'REAL'})")
                except Exception as e:
                    print(f"[LiveTrading] Error colocando orden real de compra en {symbol}: {e}")
                    self.notifier.send_message(f"⚠️ Error al abrir orden real BUY {symbol}: {e}")
                    return

            new_pos = {
                "type": "LONG" if signal_type == 1 else "SHORT",
                "symbol": symbol,
                "entry_time": timestamp,
                "entry_price": fill_price,
                "stop_loss": levels["stop_loss"],
                "take_profit": levels["take_profit"],
                "sl_distance": levels["sl_distance"],
                "position_size_asset": qty,
                "position_size_usd": levels["position_size_usd"],
                "strength": int(latest_candle["signal_strength"]),
                "reason": str(latest_candle["reason"]),
                "live": is_live_order,
            }

            active_positions[symbol] = new_pos
            print(f"OPENED NEW POSITION {'LONG' if signal_type == 1 else 'SHORT'} {symbol} @ ${fill_price:,.2f} | SL: ${levels['stop_loss']:,.2f} | TP: ${levels['take_profit']:,.2f}")

            # Send Telegram Notification on Trade Open
            self.notifier.send_trade_opened(new_pos)

    def send_midday_report(self):
        """Sends midday (12:00 PM) status report to Telegram."""
        data = self.load_active_trades()
        symbols = self.config.get("symbols") or [self.config.get("symbol", "BTC/USDT")]
        current_prices = {}
        for symbol in symbols:
            try:
                df = self.fetcher.fetch_ohlcv(symbol, "1d", limit=2)
                if not df.empty:
                    current_prices[symbol] = float(df.iloc[-1]["close"])
            except Exception as e:
                print(f"Error fetching price for daily report ({symbol}): {e}")

        return self.notifier.send_daily_report(data, current_prices=current_prices)

    def get_real_binance_account_info(self):
        """Fetches real balance and open orders directly from Binance API if API keys are provided."""
        api_key = os.getenv("BINANCE_API_KEY")
        api_secret = os.getenv("BINANCE_API_SECRET")
        testnet = os.getenv("TESTNET", "true").lower() == "true"
        
        if not api_key or not api_secret:
            return {"connected": False, "reason": "No hay API Keys configuradas en .env"}
            
        try:
            ex = ccxt.binance({
                "apiKey": api_key,
                "secret": api_secret,
                "enableRateLimit": True,
                "options": {"defaultType": "spot", "fetchBalance": {"type": "spot"}}
            })
            if testnet:
                try:
                    ex.set_sandbox_mode(True)
                except Exception:
                    ex.urls["api"] = {
                        "public": "https://testnet.binance.vision/api",
                        "private": "https://testnet.binance.vision/api",
                    }
            
            balance_info = ex.fetch_balance()
            free_usdt = balance_info.get("USDT", {}).get("free", 0.0)
            total_usdt = balance_info.get("USDT", {}).get("total", 0.0)
            
            symbols = self.config.get("symbols") or [self.config.get("symbol", "BTC/USDT")]
            open_orders = []
            for symbol in symbols:
                try:
                    raw_orders = ex.fetch_open_orders(symbol)
                    for o in raw_orders:
                        open_orders.append({
                            "id": o.get("id"),
                            "symbol": o.get("symbol"),
                            "type": o.get("type"),
                            "side": o.get("side"),
                            "price": o.get("price"),
                            "amount": o.get("amount")
                        })
                except Exception as oe:
                    print(f"Error fetching open orders for {symbol}: {oe}")
            
            active_assets = {k: v for k, v in balance_info.get("total", {}).items() if v and v > 0}
            
            return {
                "connected": True,
                "testnet": testnet,
                "free_usdt": round(free_usdt, 2),
                "total_usdt": round(total_usdt, 2),
                "open_orders": open_orders,
                "active_assets": active_assets
            }
        except Exception as e:
            return {"connected": False, "error": str(e)}

if __name__ == "__main__":
    trader = BinanceTestnetTrader()
    print("Testing Binance Testnet execution loop...")
    result = trader.check_market_and_execute()
    print("Testnet State:", result)
