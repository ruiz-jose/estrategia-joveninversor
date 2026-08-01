import os
import requests

def load_env():
    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ[k.strip()] = v.strip()

load_env()

token = os.getenv("TELEGRAM_BOT_TOKEN")
chat_id = os.getenv("TELEGRAM_CHAT_ID")

print(f"Token present: {bool(token)}")
print(f"Chat ID: {chat_id}")

if token and chat_id:
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": "🤖 *Trading Bot*: Prueba de integración de notificaciones Telegram completada exitosamente.",
        "parse_mode": "Markdown"
    }
    resp = requests.post(url, json=payload)
    print("Response status:", resp.status_code)
    print("Response body:", resp.text)
