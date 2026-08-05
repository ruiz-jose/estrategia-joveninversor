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

        raw_short_symbols = os.getenv("SHORT_ENABLED_SYMBOLS", "ETHUSDT,SOLUSDT")
        self.short_enabled_symbols = {
            self._normalize_symbol(s) for s in raw_short_symbols.split(",") if s.strip()
        }

        # Futures USD-M taker fee (~0.04% per side, both sides of a round trip) is
        # lower than Spot's 0.075% - reflect that in the live PnL bookkeeping.
        self.config["fee_pct"] = 0.0008

        # Binance USD-M Futures enforces a $20 minimum order notional (confirmed via
        # error -4164 on a live testnet order), higher than Spot's ~$10 - never trade
        # below it even if config.py's min_notional_usd (tuned for Spot) is lower.
        self.min_notional_usd = max(self.min_notional_usd, 20.0)

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


if __name__ == "__main__":
    trader = BinanceFuturesTrader()
    print("Testing Binance Futures Testnet execution loop...")
    result = trader.check_market_and_execute()
    print("Futures Testnet State:", result)
