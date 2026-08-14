# 🛡️ Lista de Chequeo Pre-Vuelo (Checklist de Validación antes de Operar en Vivo)

Antes de poner a rodar el bot de trading con capital real o en producción, es fundamental validar los siguientes **6 pilares de seguridad y confiabilidad**:

---

## 1. 🔑 Permisos de Seguridad de la API Key en Binance
- [ ] **DESHABILITAR RETIROS (*Withdrawals Disabled*):** Verifica que en la configuración de la API Key en Binance la casilla *"Enable Withdrawals"* esté **DESMARCADA**. El bot NUNCA debe tener permisos para retirar o mover fondos fuera del exchange.
- [ ] **Restricción de IP (*IP Whitelisting*):** Si tu VPS tiene una IP fija, activa *"Restrict access to trusted IPs only"* en Binance e ingresa la IP de tu servidor. Esto evita que alguien use tu API Key desde otra ubicación.

---

## 2. 🧪 Período de Prueba en Testnet / Paper Trading
- [ ] **Incubación de 7 a 14 días:** Ejecuta el bot en modo `TESTNET=true` durante al menos 1 o 2 semanas antes de usar dinero real.
- [ ] **Verificar Ejecución de Órdenes:** Confirma que el bot abra y cierre operaciones automáticamente cuando se generan las señales sin arrojar errores en la consola.

---

## 3. ⚖️ Parámetros de Gestión de Riesgo (Risk Management)
- [x] **Riesgo por Operación (`risk_per_trade_pct`):** Configurado en **1.5%** (`trading_bot/config.py`), dentro del rango 1.0%-2.0% exigido aquí.
- [ ] **Mínimo de Orden Binance (*Min Notional*):** Para $100 USDT, verifica que la posición resultante sea de al menos **$10 USDT** para cumplir con las reglas del exchange.
- [ ] **Capital mínimo recomendado (~$220-300 USDT):** Con `risk_per_trade_pct=1.5%`, el sizing basado en riesgo solo supera el mínimo de Binance ($50-55) por sí mismo (sin depender de `max_position_alloc_pct=0.60` como muleta) a partir de ~$220-300 USDT de capital, según la distancia del stop (típicamente 2%-6% en 4h). Por debajo de eso (los $100 USDT actuales), `max_position_alloc_pct` es lo que determina el tamaño real de la posición, no `risk_per_trade_pct` — es decir, la concentración por operación seguirá siendo alta hasta que se aumente el capital.
- [ ] **Stop Loss y Take Profit:** Asegúrate de que todas las operaciones tengan un Stop Loss bien definido (ej. trazado por ATR o estructura) y una relación riesgo/beneficio de al menos **1:2** o **1:2.5**.
- [x] **Stop Loss real en el exchange:** Desde la corrección de `engine/testnet_trader.py`/`engine/futures_trader.py`, cada posición en vivo coloca una orden real de protección (`STOP_MARKET`/`STOP_LOSS_LIMIT`) en Binance, no solo lógica interna del bot.
- [x] **Capital reservado por posición abierta:** `engine/testnet_trader.py` ahora descuenta el capital comprometido del balance libre al abrir una posición (y lo devuelve al cerrarla), y respeta `max_concurrent_positions` (`trading_bot/config.py` / `MAX_CONCURRENT_POSITIONS` en `.env`) como tope duro de posiciones simultáneas — antes cada símbolo se dimensionaba sobre el capital total como si fuera la única posición abierta.

---

## 4. ⏰ Sincronización de Hora del Servidor (NTP Clock Sync)
- [ ] **Sincronización de Tiempo:** La API de Binance rechaza órdenes si el reloj de tu servidor tiene una diferencia mayor a 5000 ms respecto a los servidores de Binance (`recvWindow` error).
- [ ] En servidores Ubuntu, ejecuta:
  ```bash
  sudo timedatectl set-ntp on
  ```

---

## 5. 📲 Notificaciones y Sistema de Alertas
- [ ] **Prueba de Telegram:** Haz clic en el botón de prueba o ingresa a `http://localhost:5000/api/telegram/daily_report` para confirmar que las alertas lleguen correctamente a tu teléfono.
- [ ] **Alertas de Apertura y Cierre:** Verifica que al simular un trade recibas la notificación con el resultado en PnL ($ USDT y %).

---

## 6. 🔄 Autoreinicio y Manejo de Errores (*Fail-Safes*)
- [ ] **Manejo de Desconexiones:** Asegúrate de que el código maneje excepciones de red (`try/except`) para que no colapse ante caídas temporales de internet.
- [ ] **Servicio Linux Active (`systemd`):** Verifica que `systemd` esté configurado con `Restart=always` para reiniciar el bot si el proceso se llega a detener por cualquier motivo.
