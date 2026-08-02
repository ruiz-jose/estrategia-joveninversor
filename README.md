# Trading Bot Quant — Estrategia Joven Inversor

Bot de trading algorítmico (Binance, Spot) con backtesting, paper trading en Testnet, dashboard web y notificaciones por Telegram.

## 🚀 Ejecución rápida (un solo comando)

Requisito previo: tener [Python 3.10+](https://www.python.org/downloads/) instalado y en el PATH.

Desde la raíz del proyecto, en Windows (`cmd` o PowerShell):

```bat
run.bat
```

Ese único comando hace todo lo necesario:

1. Crea el entorno virtual `.venv` (si no existe).
2. Instala/actualiza las dependencias de `requirements.txt`.
3. Crea `.env` a partir de `.env.example` (si no existe) — por defecto en modo `TESTNET=true`, sin riesgo.
4. Arranca el servidor y el dashboard en **http://localhost:5000**.

Para detenerlo, `Ctrl+C` en la misma ventana.

Para volver a ejecutarlo más adelante, basta con correr `run.bat` de nuevo (no vuelve a crear el entorno ni reinstala dependencias si ya están listas).

### Alternativa manual (equivalente a `run.bat`)

```bat
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
copy .env.example .env
.venv\Scripts\python trading_bot\server.py
```

## ⚙️ Configuración antes de operar

Edita `.env` (nunca lo subas a git) con tus credenciales reales:

| Variable | Descripción |
| :--- | :--- |
| `BINANCE_API_KEY` / `BINANCE_API_SECRET` | Claves de API de Binance (con retiros **deshabilitados**) |
| `TESTNET` | `true` = paper trading en Binance Testnet · `false` = dinero real |
| `INITIAL_CAPITAL` | Capital base en USDT para el cálculo de riesgo |
| `SYMBOL` / `TIMEFRAME` | Par y temporalidad por defecto |
| `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` | Notificaciones automáticas de aperturas/cierres y reporte diario |

Detalle completo de todos los parámetros (indicadores, riesgo, etc.) en [GUIA_CONFIGURACION_PARAMETROS.md](GUIA_CONFIGURACION_PARAMETROS.md).

## 📋 Antes de operar con dinero real

Sigue la lista de verificación en [CHECKLIST_PRE_VUELO.md](CHECKLIST_PRE_VUELO.md) (permisos de API, período en Testnet, gestión de riesgo, notificaciones, fail-safes).

## ☁️ Despliegue 24/7 en un servidor (VPS)

Para dejar el bot corriendo permanentemente en la nube (no en tu propia máquina), sigue [GUIA_DESPLIEGUE_247.md](GUIA_DESPLIEGUE_247.md).

## 🧪 Otros scripts útiles

Todos se ejecutan con el Python del entorno virtual, por ejemplo: `.venv\Scripts\python trading_bot\run_comprehensive_backtest.py`

| Script | Uso |
| :--- | :--- |
| `trading_bot/run_comprehensive_backtest.py` | Backtest completo de la estrategia por defecto |
| `trading_bot/optimize_profitable.py` | Búsqueda de parámetros óptimos |
| `trading_bot/run_quant_audit.py` | Auditoría cuantitativa / robustez |
| `trading_bot/scan_timeframes.py` | Escaneo de señales en múltiples temporalidades |
| `trading_bot/test_*.py` | Pruebas puntuales (Telegram, balance en vivo, estrategias individuales) |

## 📂 Estructura del proyecto

```
trading_bot/
├── server.py          # Servidor Flask + dashboard + schedulers (punto de entrada)
├── config.py           # Parámetros por defecto de la estrategia
├── core/                # Indicadores, estrategia de señales, gestión de riesgo
├── engine/              # Backtester, fetch de datos, trader de Testnet, Telegram
└── web/                 # Dashboard (HTML/CSS/JS)
```
