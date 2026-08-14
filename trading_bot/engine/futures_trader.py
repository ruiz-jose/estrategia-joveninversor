import os

import ccxt

from engine.testnet_trader import BinanceTestnetTrader


class BinanceFuturesTrader(BinanceTestnetTrader):
    """
    Binance USD-M Futures variant of BinanceTestnetTrader.

    Reuses all position management, SL/TP, trailing stop, drawdown kill-switch
    and state persistence logic from the base class. Only what actually differs
    between Spot and Futures is overridden here: credentials/testnet flag,
    exchange construction (market type, leverage, margin mode), which
    directions can be traded for real per symbol, and the taker fee rate.
    """

    def _resolve_credentials(self):
        return (
            os.getenv("BINANCE_FUTURES_API_KEY"),
            os.getenv("BINANCE_FUTURES_API_SECRET"),
            os.getenv("FUTURES_TESTNET", "true").lower() == "true",
        )

    def _init_exchange(self, api_key: str, api_secret: str):
        self.exchange = ccxt.binance({
            "apiKey": api_key,
            "secret": api_secret,
            "enableRateLimit": True,
            "options": {
                "defaultType": "future",
                # ccxt >=4.5 blocks Futures Testnet requests by default, nudging users
                # toward Binance's newer "demo trading" feature - the classic Futures
                # Testnet REST API (testnet.binancefuture.com) still works, so opt back in.
                "disableFuturesSandboxWarning": True,
                # See the matching comment in testnet_trader.py::_init_exchange -
                # auto-corrects local clock skew instead of every authenticated
                # call failing with recvWindow errors.
                "adjustForTimeDifference": True,
            }
        })

        if self.testnet:
            try:
                self.exchange.set_sandbox_mode(True)
            except Exception:
                self.exchange.urls["api"] = {
                    "fapiPublic": "https://testnet.binancefuture.com/fapi/v1",
                    "fapiPrivate": "https://testnet.binancefuture.com/fapi/v1",
                }

        leverage = int(os.getenv("LEVERAGE", 2))
        margin_type = os.getenv("MARGIN_TYPE", "ISOLATED").upper()
        symbols = self.config.get("symbols") or [self.config.get("symbol", "BTC/USDT")]
        for symbol in symbols:
            try:
                self.exchange.set_margin_mode(margin_type.lower(), symbol)
            except Exception as e:
                # Binance returns an error if the margin mode is already set to this value.
                if "-4046" not in str(e) and "No need to change margin type" not in str(e):
                    print(f"[FuturesTrader] No se pudo fijar margin mode {margin_type} en {symbol}: {e}")
            try:
                self.exchange.set_leverage(leverage, symbol)
            except Exception as e:
                print(f"[FuturesTrader] No se pudo fijar leverage {leverage}x en {symbol}: {e}")

        raw_short_symbols = os.getenv("SHORT_ENABLED_SYMBOLS", "")
        if raw_short_symbols.strip():
            self.short_enabled_symbols = {
                self._normalize_symbol(s) for s in raw_short_symbols.split(",") if s.strip()
            }
        else:
            # By default, allow SHORT on all symbols configured for the futures bot.
            self.short_enabled_symbols = {
                self._normalize_symbol(s) for s in symbols
            }

        # Debug log: show which symbols are allowed for SHORT on this trader
        try:
            print(f"[FuturesTrader] short_enabled_symbols = {sorted(self.short_enabled_symbols)}")
        except Exception:
            pass

        # Futures USD-M taker fee (~0.04% per side, both sides of a round trip) is
        # lower than Spot's 0.075% - reflect that in the live PnL bookkeeping.
        self.config["fee_pct"] = 0.0008

        # Binance USD-M Futures enforces a $50 minimum order notional (confirmed via
        # error -4164 on live orders) - never trade below it.
        self.min_notional_usd = max(self.min_notional_usd, 50.0)

    @staticmethod
    def _normalize_symbol(symbol: str) -> str:
        """"ETHUSDT" or "eth/usdt" -> "ETH/USDT", to compare against config's slash format."""
        symbol = symbol.strip().upper().replace("/", "")
        if symbol.endswith("USDT"):
            return f"{symbol[:-4]}/USDT"
        return symbol

    def _direction_tradable(self, symbol: str, signal_type: int) -> bool:
        if signal_type == 1:
            return True
        return symbol in self.short_enabled_symbols

    def _place_stop_order(self, symbol: str, position_type: str, amount: float, stop_price: float):
        """Futures protective stop: a real STOP_MARKET, reduce-only so it can only
        close the existing position (never flip or add to it) and closes fully at
        the trigger price without needing a limit price like Spot's STOP_LOSS_LIMIT.

        ccxt/Binance route any order carrying a stopPrice through the newer
        "algo/conditional order" system on USD-M Futures (distinct algoId, separate
        endpoints) rather than the classic order book - fetch_order/cancel_order
        need params={"trigger": True} to find it there, see the overrides below.
        """
        try:
            amount = float(self.exchange.amount_to_precision(symbol, amount))
            stop_price = float(self.exchange.price_to_precision(symbol, stop_price))
            close_side = self._close_side(position_type)
            order = self.exchange.create_order(
                symbol, "STOP_MARKET", close_side, amount, None,
                {"stopPrice": stop_price, "reduceOnly": True}
            )
            return order.get("id")
        except Exception as e:
            print(f"[LiveTrading] Error colocando stop order en {symbol}: {e}")
            return None

    def _cancel_order(self, symbol: str, order_id):
        if not order_id:
            return
        try:
            self.exchange.cancel_order(order_id, symbol, {"trigger": True})
        except Exception as e:
            print(f"[LiveTrading] No se pudo cancelar orden {order_id} en {symbol} (probablemente ya ejecutada/cancelada): {e}")

    def _fetch_stop_order_status(self, symbol: str, order_id):
        return self.exchange.fetch_order(order_id, symbol, {"trigger": True})


if __name__ == "__main__":
    trader = BinanceFuturesTrader()
    print("Testing Binance Futures Testnet execution loop...")
    result = trader.check_market_and_execute()
    print("Futures Testnet State:", result)
