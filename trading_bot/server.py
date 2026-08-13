from flask import Flask, jsonify, request, send_from_directory
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import DEFAULT_CONFIG
from engine.data_fetcher import DataFetcher
from engine.backtester import Backtester
from engine.testnet_trader import BinanceTestnetTrader
from engine.futures_trader import BinanceFuturesTrader
from engine.telegram_notifier import TelegramNotifier
from core.indicators import add_all_indicators
from core.strategy import Strategy

app = Flask(__name__, static_folder="web", static_url_path="")
fetcher = DataFetcher()
TelegramNotifier()  # loads .env into os.environ as a side effect, before MARKET_TYPE is read below
MARKET_TYPE = os.getenv("MARKET_TYPE", "spot").lower()
LEVERAGE = int(os.getenv("LEVERAGE", 2))
testnet_trader = BinanceFuturesTrader() if MARKET_TYPE == "futures" else BinanceTestnetTrader()
print(f"[Startup] MARKET_TYPE={MARKET_TYPE} | LEVERAGE={LEVERAGE} | Trader={testnet_trader.__class__.__name__}")

@app.route("/")
def index():
    return send_from_directory("web", "index.html")

@app.route("/<path:path>")
def static_proxy(path):
    return send_from_directory("web", path)

@app.route("/api/config", methods=["GET"])
def get_config():
    return jsonify({"status": "success", "config": DEFAULT_CONFIG})

@app.route("/api/backtest", methods=["POST"])
def run_backtest():
    try:
        user_params = request.get_json() or {}
        config = DEFAULT_CONFIG.copy()
        config.update(user_params)
        
        symbol = config.get("symbol", "SOL/USDT")
        timeframe = config.get("timeframe", "1d")
        
        # Fetch OHLCV data
        df = fetcher.fetch_ohlcv(symbol, timeframe, limit=500)
        
        # Run Backtest
        backtester = Backtester(config)
        result = backtester.run(df)
        
        return jsonify({
            "status": "success",
            "result": result
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/testnet", methods=["GET", "POST"])
def manage_testnet():
    try:
        if request.method == "POST":
            # Trigger Testnet execution check
            state = testnet_trader.check_market_and_execute()
            return jsonify({"status": "success", "state": state})
        else:
            state = testnet_trader.load_active_trades()
            return jsonify({"status": "success", "state": state})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/scanner", methods=["GET"])
def scan_signals():
    try:
        symbols = ["SOL/USDT", "BTC/USDT", "ETH/USDT", "BNB/USDT", "ADA/USDT"]
        timeframe = request.args.get("timeframe", "1d")
        results = []
        
        for sym in symbols:
            df = fetcher.fetch_ohlcv(sym, timeframe, limit=200)
            df_ind = add_all_indicators(df, DEFAULT_CONFIG)
            strat = Strategy(DEFAULT_CONFIG)
            df_sig = strat.generate_signals(df_ind)
            
            latest = df_sig.iloc[-1]
            results.append({
                "symbol": sym,
                "price": float(latest["close"]),
                "signal": int(latest["signal"]),
                "strength": int(latest["signal_strength"]),
                "reason": str(latest["reason"])
            })
            
        return jsonify({"status": "success", "signals": results})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/telegram/daily_report", methods=["POST", "GET"])
def trigger_daily_report():
    try:
        success = testnet_trader.send_midday_report()
        return jsonify({
            "status": "success" if success else "error",
            "message": "Reporte diario enviado por Telegram exitosamente." if success else "No se pudo enviar el reporte por Telegram."
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/binance/account", methods=["GET"])
def get_binance_account():
    try:
        info = testnet_trader.get_real_binance_account_info()
        return jsonify({"status": "success", "account": info})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/debug", methods=["GET"])
def debug_info():
    try:
        info = {
            "market_type": MARKET_TYPE,
            "leverage": LEVERAGE,
            "trader_class": testnet_trader.__class__.__name__,
            "has_spot_keys": bool(os.getenv("BINANCE_API_KEY") and os.getenv("BINANCE_API_SECRET")),
            "has_futures_keys": bool(os.getenv("BINANCE_FUTURES_API_KEY") and os.getenv("BINANCE_FUTURES_API_SECRET")),
            "trader_live_trading_enabled": getattr(testnet_trader, "live_trading_enabled", False),
        }
        if hasattr(testnet_trader, "short_enabled_symbols"):
            info["short_enabled_symbols"] = list(getattr(testnet_trader, "short_enabled_symbols"))
        return jsonify({"status": "success", "debug": info})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

def start_midday_scheduler():
    """Daemon thread that checks for 12:00 PM local time every 30s and sends Telegram status report."""
    import threading
    import datetime
    import time
    
    def scheduler_loop():
        last_sent_date = None
        print("[Scheduler] Midday Telegram Report Scheduler initialized (Target: 12:00 PM daily)...")
        while True:
            try:
                now = datetime.datetime.now()
                today_str = now.strftime("%Y-%m-%d")
                if now.hour == 12 and now.minute == 0 and last_sent_date != today_str:
                    print(f"[{now.strftime('%H:%M:%S')}] Triggering 12:00 PM Midday Telegram Report...")
                    success = testnet_trader.send_midday_report()
                    if success:
                        last_sent_date = today_str
                        print(f"[{now.strftime('%H:%M:%S')}] Midday Telegram Report sent successfully.")
            except Exception as e:
                print(f"[Scheduler Error]: {e}")
            time.sleep(30)

    t = threading.Thread(target=scheduler_loop, daemon=True)
    t.start()

def start_market_check_scheduler(interval_sec: int = 3600):
    """Daemon thread that runs the trading engine's market check on a fixed interval."""
    import threading
    import datetime
    import time

    def scheduler_loop():
        print(f"[Scheduler] Market Check Scheduler initialized (every {interval_sec}s)...")
        while True:
            try:
                now = datetime.datetime.now()
                print(f"[{now.strftime('%H:%M:%S')}] Running scheduled market check...")
                testnet_trader.check_market_and_execute()
            except Exception as e:
                print(f"[Scheduler Error]: {e}")
            time.sleep(interval_sec)

    t = threading.Thread(target=scheduler_loop, daemon=True)
    t.start()

if __name__ == "__main__":
    start_midday_scheduler()
    start_market_check_scheduler(interval_sec=3600)
    port = int(os.environ.get("PORT", 5000))
    print(f"Starting Trading Bot Server on http://localhost:{port} ...")
    app.run(host="0.0.0.0", port=port, debug=False)
