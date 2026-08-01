import pandas as pd
import urllib.request
import json
import time

class DataFetcher:
    """
    Fetches real-time and historical OHLCV candlestick data from Binance API.
    Supports multi-page fetching for large historical datasets.
    """
    
    TF_MAP = {
        "1m": "1m",
        "5m": "5m",
        "15m": "15m",
        "30m": "30m",
        "1h": "1h",
        "4h": "4h",
        "1d": "1d"
    }

    # Candle duration in milliseconds, used to detect and drop a still-forming last candle
    TF_DURATION_MS = {
        "1m": 60_000,
        "5m": 300_000,
        "15m": 900_000,
        "30m": 1_800_000,
        "1h": 3_600_000,
        "4h": 14_400_000,
        "1d": 86_400_000
    }

    @staticmethod
    def format_symbol(symbol: str) -> str:
        """Convert BTC/USDT to BTCUSDT for Binance API."""
        return symbol.replace("/", "").replace("-", "").upper()

    def fetch_ohlcv(self, symbol: str = "BTC/USDT", timeframe: str = "1h", limit: int = 500) -> pd.DataFrame:
        """
        Fetch OHLCV candlestick data from Binance public API.
        Handles pagination for limit > 1000.
        """
        binance_symbol = self.format_symbol(symbol)
        interval = self.TF_MAP.get(timeframe, "1h")
        
        all_klines = []
        fetch_limit = min(limit, 1000)
        end_time = None
        
        needed = limit
        
        while needed > 0:
            current_batch_limit = min(needed, 1000)
            url = f"https://api.binance.com/api/v3/klines?symbol={binance_symbol}&interval={interval}&limit={current_batch_limit}"
            if end_time is not None:
                url += f"&endTime={end_time}"
                
            req = urllib.request.Request(url, headers={"User-Agent": "TradingBot/1.0"})
            try:
                with urllib.request.urlopen(req, timeout=10) as response:
                    data = json.loads(response.read().decode("utf-8"))
                    if not data:
                        break
                    
                    # Prepend data since pagination goes backwards in time
                    all_klines = data + all_klines
                    first_candle_ts = data[0][0]
                    end_time = first_candle_ts - 1
                    needed -= len(data)
                    
                    if len(data) < current_batch_limit:
                        break # No more historical candles available
                    
                    time.sleep(0.1) # Respect Binance rate limit
            except Exception as e:
                print(f"Error fetching batch from Binance for {symbol}: {e}")
                if not all_klines:
                    raise RuntimeError(f"Binance API unavailable for {symbol}. Cannot operate on real exchange without live data.") from e
                break

        if not all_klines:
            raise RuntimeError(f"No data returned from Binance for {symbol}. Cannot operate on real exchange without live data.")

        df = pd.DataFrame(all_klines, columns=[
            "timestamp", "open", "high", "low", "close", "volume",
            "close_time", "quote_asset_volume", "number_of_trades",
            "taker_buy_base_asset_volume", "taker_buy_quote_asset_volume", "ignore"
        ])
        
        # Deduplicate and sort by timestamp
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        df = df.drop_duplicates(subset=["timestamp"]).sort_values(by="timestamp").reset_index(drop=True)

        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = df[col].astype(float)

        df = df[["timestamp", "open", "high", "low", "close", "volume"]]

        # Drop the last candle if it hasn't closed yet, so every caller (backtest,
        # live trader, scanner) only ever sees fully closed candles - avoids repainting.
        duration_ms = self.TF_DURATION_MS.get(interval)
        if duration_ms is not None and not df.empty:
            last_open_ms = int(df.iloc[-1]["timestamp"].value // 1_000_000)
            now_ms = int(pd.Timestamp.utcnow().value // 1_000_000)
            if last_open_ms + duration_ms > now_ms:
                df = df.iloc[:-1].reset_index(drop=True)

        return df

    def _generate_synthetic_ohlcv(self, symbol: str, limit: int = 300) -> pd.DataFrame:
        """Fallback synthetic candle generator for offline/sandbox testing."""
        import numpy as np
        dates = pd.date_range(end=pd.Timestamp.now(), periods=limit, freq="1h")
        np.random.seed(42)
        price = 65000.0 if "BTC" in symbol else 3500.0
        returns = np.random.normal(0.0002, 0.008, limit)
        close_prices = price * np.exp(np.cumsum(returns))
        
        opens = close_prices * (1 + np.random.normal(0, 0.002, limit))
        highs = np.maximum(opens, close_prices) * (1 + np.abs(np.random.normal(0, 0.003, limit)))
        lows = np.minimum(opens, close_prices) * (1 - np.abs(np.random.normal(0, 0.003, limit)))
        volumes = np.random.uniform(100, 1500, limit)
        
        return pd.DataFrame({
            "timestamp": dates,
            "open": opens,
            "high": highs,
            "low": lows,
            "close": close_prices,
            "volume": volumes
        })
