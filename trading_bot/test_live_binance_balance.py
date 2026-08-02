import os
import ccxt

def load_env():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env_path = os.path.join(base_dir, ".env")
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ[k.strip()] = v.strip()

load_env()

api_key = os.getenv("BINANCE_API_KEY")
api_secret = os.getenv("BINANCE_API_SECRET")
testnet = os.getenv("TESTNET", "true").lower() == "true"

print("Checking Binance API Connection...")
print("API Key present:", bool(api_key))
print("TESTNET mode:", testnet)

if api_key and api_secret:
    try:
        ex = ccxt.binance({
            "apiKey": api_key,
            "secret": api_secret,
            "enableRateLimit": True,
            "options": {"defaultType": "spot"}
        })
        if testnet:
            try:
                ex.set_sandbox_mode(True)
            except Exception:
                ex.urls["api"] = {
                    "public": "https://testnet.binance.vision/api",
                    "private": "https://testnet.binance.vision/api",
                }

        balance = ex.fetch_balance()
        usdt_info = balance.get("USDT", {})
        print("\n--- BINANCE SPOT BALANCE RESULT ---")
        print("Free USDT:", usdt_info.get("free", 0.0))
        print("Used USDT:", usdt_info.get("used", 0.0))
        print("Total USDT:", usdt_info.get("total", 0.0))

        totals = balance.get("total", {}) or {}
        non_zero = {
            asset: amount
            for asset, amount in totals.items()
            if isinstance(amount, (int, float)) and amount > 0
        }

        print("All Non-Zero Assets in Spot:")
        for asset, val in non_zero.items():
            print(f"  - {asset}: {val}")

    except Exception as e:
        print("Error connecting to Binance API:", e)
else:
    print("No API Key or Secret found in .env")
