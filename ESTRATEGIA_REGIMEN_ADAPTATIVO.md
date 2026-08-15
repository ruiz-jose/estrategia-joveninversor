# 🧭 Estrategias Disponibles: Confluencia vs. Régimen Adaptativo

El bot ahora soporta dos estrategias de generación de señales intercambiables. Esta guía explica qué hace cada una, la evidencia detrás de la nueva, y cómo elegir cuál correr **antes** de ejecutar el bot (backtest o en vivo).

---

## 1. Resumen

| | `confluence` (original) | `adaptive_regime` (nueva) |
| :--- | :--- | :--- |
| Lógica | Un único modelo de confluencia (Supertrend + EMA200 + EMA20/50 + MACD + RSI + ADX/DI + Squeeze) aplicado siempre igual | Cambia de lógica según el régimen de mercado: sigue tendencia cuando el ADX es alto, revierte a la media cuando el ADX es bajo |
| Archivo | [`trading_bot/core/strategy.py`](trading_bot/core/strategy.py) | [`trading_bot/core/strategy_adaptive.py`](trading_bot/core/strategy_adaptive.py) |
| Validación | Walk-forward de 5.5 años (`robustness_report.py`), pero **negativa en BTC en los últimos 6-8 meses** | Búsqueda con partición train/test dentro de los últimos 6 meses únicamente — ver evidencia abajo |
| Resultado 6 meses (portafolio $300, BTC+ETH) | PnL -$47.03 (-15.68%), win rate 23.9%, PF 0.52 | PnL +$10.07, win rate 52.0%, PF 1.18 |

**Ninguna de las dos tiene una validación robusta y suficiente como para operar con confianza plena.** La de confluencia tiene más años de historia probada pero viene deteriorada recientemente; la adaptativa mejora los últimos 6 meses pero se apoya en muy pocas operaciones (25 en el test de portafolio) y no pasó una validación fuera de muestra tan exigente. Tratalas como dos hipótesis en evaluación, no como una solución cerrada.

---

## 2. Cómo funciona `adaptive_regime`

Por cada vela cierra, mide el ADX (fuerza de tendencia) y decide qué "modo" usar:

### Régimen de Tendencia (ADX ≥ `adx_regime_threshold`, default 26)
Busca un retroceso a favor de la tendencia:
- **LONG**: precio por encima de EMA200, EMA20 > EMA50 (alineación alcista), la vela tocó la EMA20 y cerró en verde, RSI ≥ 45.
- **SHORT**: el espejo bajista (precio bajo EMA200, EMA20 < EMA50, toca EMA20 y cierra en rojo, RSI ≤ 55).

### Régimen de Rango (ADX < `adx_regime_threshold`)
Busca un rebote en los extremos de las Bandas de Bollinger (20, 2σ):
- **LONG**: la mínima tocó la banda inferior, cierre en verde, RSI ≤ `rsi_range_long` (default 35).
- **SHORT**: la máxima tocó la banda superior, cierre en rojo, RSI ≥ `rsi_range_short` (default 65).

El sizing, SL/TP (ATR + risk/reward), comisiones, slippage y funding son **los mismos** que usa la estrategia de confluencia (`core/risk_manager.py`) — solo cambia qué dispara la señal de entrada.

---

## 3. De dónde sale la evidencia (y sus límites)

1. **Grid search sobre la estrategia de confluencia** (96 combinaciones de ADX/RR/ATR/LONG-SHORT, partiendo los últimos 6 meses en 4 meses de entrenamiento + 2 de validación): **ninguna combinación sobrevivió fuera de muestra** (Profit Factor cayendo a 0.0-0.01 en los últimos 2 meses). Confirma que ajustar números de esa misma estrategia no la arregla.
2. **Diseño de `adaptive_regime`**, inspirado en experimentos previos ya presentes en el repo (`test_adaptive_strategy.py`, `test_mean_reversion.py`) pero reimplementado sobre el motor de backtest real (comisiones, slippage, funding, sizing idéntico a producción).
3. **Grid search de `adaptive_regime`** (48 combinaciones) con la misma partición train/test: encontró configuraciones con mejor comportamiento en el período completo de 6 meses, aunque **la mayoría también se debilita en el tramo de validación de los últimos 2 meses** — el régimen de tendencia pura (`allow_short=False`) fue el único que se mantuvo estable (0 operaciones en el tramo de test, ni gana ni pierde).
4. **Validación final a nivel portafolio** ($300 compartidos entre BTC/ETH, igual que corre el bot real) con `adx_regime_threshold=26, risk_reward_ratio=2.5, atr_sl_multiplier=2.5, allow_short=True`: 25 operaciones en 6 meses, win rate 52%, PF 1.18, PnL +$10.07 — comparado con -$47.03 de la estrategia actual en la misma ventana.

**Limitaciones honestas:**
- Muestra chica (25 operaciones) — no alcanza para confianza estadística.
- Es la mejor de solo 3 configuraciones de portafolio probadas, no una grid search exhaustiva a ese nivel.
- No tiene un walk-forward de varios años como la de confluencia — todo lo que se sabe de ella es de los últimos 6 meses.
- Un Profit Factor de 1.18 es un edge marginal, no una garantía de rentabilidad futura.

---

## 4. Cómo elegir la estrategia

### Backtests / simulación
El dashboard web **ya no tiene simulador** (se sacó a propósito: ese panel solo debe reflejar trading real/testnet contra Binance). Los backtests se corren localmente en Python, por ejemplo:

```python
from engine.backtester import Backtester
from config import DEFAULT_CONFIG

config = DEFAULT_CONFIG.copy()
config["strategy_type"] = "adaptive_regime"  # o "confluence"
config["symbol"] = "BTC/USDT"
config["timeframe"] = "4h"

df = fetcher.fetch_ohlcv(config["symbol"], config["timeframe"], limit=1500)
resultado = Backtester(config).run(df)
print(resultado["summary"])
```

`Backtester`/`PortfolioBacktester` eligen la estrategia automáticamente vía `core/strategy_factory.py` según `config["strategy_type"]`.

### En el bot en vivo / testnet
El bot en vivo no tiene un botón de "iniciar" en el dashboard (corre automáticamente al levantar `server.py`), así que la estrategia se elige **antes de arrancarlo**, con la variable de entorno `STRATEGY_TYPE` en [`.env`](.env):

```env
# "confluence" (default) o "adaptive_regime"
STRATEGY_TYPE=adaptive_regime
```

Si no se define, usa el default de [`trading_bot/config.py`](trading_bot/config.py) (`strategy_type`, actualmente `"confluence"`).

### Parámetros de `adaptive_regime`
Ajustables en `config.py` (sección "core/strategy_adaptive.py params"):

```python
"adx_regime_threshold": 26,  # ADX >= esto: modo tendencia. Menor: modo rango.
"bb_len": 20,                # período de las Bandas de Bollinger
"bb_mult": 2.0,               # multiplicador de desvío estándar
"rsi_range_long": 35,         # RSI <= esto confirma LONG de reversión
"rsi_range_short": 65,        # RSI >= esto confirma SHORT de reversión
```

---

## 5. Recomendación

Ninguna de las dos estrategias tiene evidencia suficiente para operar con capital real todavía. Sugerencia concreta:
1. Correr `adaptive_regime` en Futures Testnet en paralelo (o en lugar de) `confluence` durante al menos 1-2 meses más de datos reales, acumulando operaciones genuinamente fuera de muestra (no backtesteadas).
2. Repetir esta misma comparación cuando haya más historial — si `adaptive_regime` sigue sosteniendo un PF > 1 con una muestra más grande, recién ahí consideralo más confiable que la actual.
3. No usar ninguna de las dos como base para aumentar el tamaño de las operaciones o el capital hasta tener esa validación adicional.
