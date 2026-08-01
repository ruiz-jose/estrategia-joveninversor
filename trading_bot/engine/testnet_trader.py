import ccxt
import time
import json
import os
import sys

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
    Binance Testnet Live Trader Engine.
    Executes real-time paper trading on Binance Spot/Futures Testnet with 1,000 USDT virtual balance.
    """
    
    def __init__(self, api_key: str = None, api_secret: str = None, testnet: bool = True):
        self.testnet = testnet
        self.config = DEFAULT_CONFIG.copy()
        self.fetcher = DataFetcher()
        self.strategy = Strategy(self.config)
        self.risk_manager = RiskManager(self.config)
        self.notifier = TelegramNotifier()
        self.trade_log_file = r"C:\Users\Pc\.gemini\antigravity\scratch\trading_bot\live_testnet_trades.json"
        
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
            # Set Binance Spot Testnet URLs
            self.exchange.urls["api"] = {
                "public": "https://testnet.binance.vision/api",
                "private": "https://testnet.binance.vision/api",
            }
            
    def load_active_trades(self):
        """Load live trades log from JSON file."""
        if os.path.exists(self.trade_log_file):
            try:
                with open(self.trade_log_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error loading trades log: {e}")
        return {"account_balance": float(self.config.get("initial_capital", 100.0)), "active_position": None, "completed_trades": []}

    def save_active_trades(self, data):
        """Save trades log to JSON file."""
        try:
            with open(self.trade_log_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Error saving trades log: {e}")

    def check_market_and_execute(self):
        """
        Main execution loop step:
        1. Download latest candles for configured symbol & timeframe.
        2. Calculate indicators & signals.
        3. Check active position (SL / TP / Trailing Stop).
        4. Execute new signal if no active position.
        """
        symbol = self.config.get("symbol", "SOL/USDT")
        timeframe = self.config.get("timeframe", "1d")
        
        # 1. Fetch OHLCV data
        df = self.fetcher.fetch_ohlcv(symbol, timeframe, limit=300)
        df_ind = add_all_indicators(df, self.config)
        df_sig = self.strategy.generate_signals(df_ind)
        
        latest_candle = df_sig.iloc[-1]
        curr_price = float(latest_candle["close"])
        timestamp = str(latest_candle["timestamp"])
        
        data = self.load_active_trades()
        balance = float(data.get("account_balance", 1000.0))
        active_pos = data.get("active_position")
        
        print(f"[{timestamp}] Checking {symbol} ({timeframe}) - Current Price: ${curr_price:,.2f} | Balance: ${balance:,.2f}")
        
        # 2. Check Active Position
        if active_pos is not None:
            pos_type = active_pos["type"]
            entry_price = float(active_pos["entry_price"])
            sl = float(active_pos["stop_loss"])
            tp = float(active_pos["take_profit"])
            sl_dist = float(active_pos["sl_distance"])
            qty = float(active_pos["position_size_asset"])
            
            # Check Break-Even Trailing Stop
            new_sl = self.risk_manager.update_trailing_stop(curr_price, entry_price, sl, 1 if pos_type == "LONG" else -1, sl_dist)
            active_pos["stop_loss"] = float(new_sl)
            sl = new_sl
            
            exit_price = None
            exit_reason = None
            
            if pos_type == "LONG":
                if curr_price <= sl:
                    exit_price = sl
                    exit_reason = "Break-Even / Stop Loss" if sl >= entry_price else "Stop Loss"
                elif curr_price >= tp:
                    exit_price = tp
                    exit_reason = "Take Profit"
            else: # SHORT
                if curr_price >= sl:
                    exit_price = sl
                    exit_reason = "Break-Even / Stop Loss" if sl <= entry_price else "Stop Loss"
                elif curr_price <= tp:
                    exit_price = tp
                    exit_reason = "Take Profit"
                    
            if exit_price is not None:
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
                    "exit_reason": exit_reason
                }
                
                data["completed_trades"].append(trade_record)
                data["account_balance"] = round(new_balance, 2)
                data["active_position"] = None
                self.save_active_trades(data)
                print(f"CLOSED POSITION {pos_type} @ ${exit_price:,.2f} | Reason: {exit_reason} | PnL: ${net_pnl:+.2f}")
                
                # Send Telegram Notification on Trade Close
                self.notifier.send_trade_closed(trade_record, round(new_balance, 2))
                return data

        # 3. Check for New Entry Signal
        if active_pos is None and latest_candle["signal"] != 0 and latest_candle["signal_strength"] >= 3:
            signal_type = int(latest_candle["signal"])
            levels = self.risk_manager.calculate_trade_levels(
                entry_price=curr_price,
                atr=float(latest_candle["atr"]),
                signal_type=signal_type,
                current_balance=balance,
                ema50=float(latest_candle["ema_50"])
            )
            
            new_pos = {
                "type": "LONG" if signal_type == 1 else "SHORT",
                "symbol": symbol,
                "entry_time": timestamp,
                "entry_price": curr_price,
                "stop_loss": levels["stop_loss"],
                "take_profit": levels["take_profit"],
                "sl_distance": levels["sl_distance"],
                "position_size_asset": levels["position_size_asset"],
                "position_size_usd": levels["position_size_usd"],
                "strength": int(latest_candle["signal_strength"]),
                "reason": str(latest_candle["reason"])
            }
            
            data["active_position"] = new_pos
            self.save_active_trades(data)
            print(f"OPENED NEW POSITION {'LONG' if signal_type == 1 else 'SHORT'} @ ${curr_price:,.2f} | SL: ${levels['stop_loss']:,.2f} | TP: ${levels['take_profit']:,.2f}")
            
            # Send Telegram Notification on Trade Open
            self.notifier.send_trade_opened(new_pos)
            
        return data

    def send_midday_report(self):
        """Sends midday (12:00 PM) status report to Telegram."""
        data = self.load_active_trades()
        symbol = self.config.get("symbol", "SOL/USDT")
        curr_price = None
        try:
            df = self.fetcher.fetch_ohlcv(symbol, "1d", limit=2)
            if not df.empty:
                curr_price = float(df.iloc[-1]["close"])
        except Exception as e:
            print(f"Error fetching price for daily report: {e}")
            
        return self.notifier.send_daily_report(data, current_price=curr_price)

if __name__ == "__main__":
    trader = BinanceTestnetTrader()
    print("Testing Binance Testnet execution loop...")
    result = trader.check_market_and_execute()
    print("Testnet State:", result)
