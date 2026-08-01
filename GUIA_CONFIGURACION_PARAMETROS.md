# ⚙️ Guía de Dónde y Cómo Configurar Todos los Parámetros del Bot

Esta guía detalla **exactamente en qué archivos y pantallas** se configura cada parámetro del bot de trading (credenciales, riesgo, estrategia cuantitativa y Telegram).

---

## 📂 mapa de Archivos de Configuración

| Qué deseas cambiar | Dónde se configura | Archivo / Pantalla |
| :--- | :--- | :--- |
| **API Keys de Binance, Telegram y Capital** | Variables de Entorno | [`.env`](file:///c:/temp/2026/antigravity/estrategia-joveninversor/.env) |
| **Indicadores (EMA, MACD, RSI, ADX, Riesgo %)** | Estrategia por Defecto | [`trading_bot/config.py`](file:///c:/temp/2026/antigravity/estrategia-joveninversor/trading_bot/config.py) |
| **Simulación y Prueba Visual** | Dashboard Web | [http://localhost:5000](http://localhost:5000) |
| **Permisos de Seguridad y Retiros** | Web de Binance | Binance.com → *Gestión de API* |

---

## 1. 📄 Archivo 1: `.env` (Credenciales y Entorno)

Ubicación: [`estrategia-joveninversor/.env`](file:///c:/temp/2026/antigravity/estrategia-joveninversor/.env)

Este archivo almacena tus llaves privadas y credenciales secretas.

```env
# ── 1. CREDENCIALES BINANCE ──────────────────────────────────────────
# Reemplaza con tus llaves reales o de Testnet
BINANCE_API_KEY=tu_api_key_aqui
BINANCE_API_SECRET=tu_api_secret_aqui

# ── 2. ENTORNO DE OPERACIÓN ──────────────────────────────────────────
# true  = Opera en modo TESTNET (dinero ficticio de prueba)
# false = Opera en la cuenta REAL de Binance con dinero real
TESTNET=false

# ── 3. CAPITAL INICIAL ───────────────────────────────────────────────
# Capital asignado para cálculo de riesgo (ej. 100 USDT)
INITIAL_CAPITAL=100

# ── 4. PAR DE TRADING Y TEMPORALIDAD ──────────────────────────────────
SYMBOL=BTCUSDT
TIMEFRAME=1d

# ── 5. NOTIFICACIONES TELEGRAM ───────────────────────────────────────
# Token obtenido con @BotFather
TELEGRAM_BOT_TOKEN=tu_telegram_bot_token_aqui

# Tu Chat ID personal obtenido con @userinfobot
TELEGRAM_CHAT_ID=tu_telegram_chat_id_aqui
```

---

## 2. 🐍 Archivo 2: `trading_bot/config.py` (Estrategia y Riesgo)

Ubicación: [`trading_bot/config.py`](file:///c:/temp/2026/antigravity/estrategia-joveninversor/trading_bot/config.py)

Aquí se definen los valores cuantitativos por defecto para el cálculo de señales y la gestión de riesgo.

```python
DEFAULT_CONFIG = {
    # ── MERCADO Y CAPITAL ──
    "symbol": "BTC/USDT",       # Par a monitorear
    "timeframe": "1d",          # Temporalidad recomendada: 1d (Diario)
    "initial_capital": 100.0,   # Capital inicial ($100 USDT)

    # ── INDICADORES TÉCNICOS ──
    "ema_fast": 20,             # EMA Rápida (Corta)
    "ema_medium": 50,           # EMA Media
    "ema_slow": 200,            # EMA Lenta (Filtro de Tendencia Macro)
    "rsi_period": 14,           # Período RSI
    "adx_period": 14,           # Período ADX
    "adx_threshold": 18,        # Fuerza mínima de tendencia ADX

    # ── GESTIÓN DE RIESGO ──
    "risk_per_trade_pct": 2.0,  # Riesgo Máximo % por Operación (2% = $2 USDT para $100 capital)
    "risk_reward_ratio": 2.5,   # Ratio Riesgo / Beneficio (1 : 2.5)
    "atr_period": 14,           # Período para volatilidad ATR
    "atr_sl_multiplier": 2.0,   # Multiplicador ATR para Stop Loss dinámico
    "trailing_stop": True,      # Mueve Stop Loss a Break-Even al alcanzar 1.2x riesgo
}
```

---

## 3. 🌐 Pantalla 3: Dashboard Web (Interactivo)

Ubicación: **[http://localhost:5000](http://localhost:5000)** (o la IP de tu servidor VPS)

En el panel lateral izquierdo (*Configuración de Estrategia*), puedes ajustar los parámetros dinámicamente y presionar **"Ejecutar Modelo Rentable"** para simular cambios instantáneamente sin reiniciar el servidor:

- **Activo / Par:** Selecciona SOL/USDT, BTC/USDT, ETH/USDT, BNB/USDT.
- **Temporalidad:** Cambia entre 1d, 4h, 1h, 15m.
- **Capital Inicial ($):** Ingresa 100 (o cualquier monto deseado).
- **Riesgo / Trade (%):** Define el % a arriesgar (ej. 2.0%).
- **Ratio R/R:** Modifica el objetivo de ganancia vs pérdida (ej. 2.5).

---

## 4. 🔑 Pantalla 4: Consola de Binance (Seguridad)

Ubicación: Web de Binance → Perfil de Usuario → **Gestión de API**

Doble verificación recomendada antes de conectar:

1. **Editar Permisos (*Edit Restrictions*):**
   - ✅ Marca: *Enable Reading* (Lectura).
   - ✅ Marca: *Enable Spot & Margin Trading* (Trading Spot) o *Enable Futures* (Trading Futuros).
   - ❌ **DESMARCA:** *Enable Withdrawals* (Retiros).
2. **Restricción por IP:**
   - Selecciona *"Restrict access to trusted IPs only"* y pega la IP pública de tu servidor VPS para bloquear accesos no autorizados.
