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
- [ ] **Riesgo por Operación (`risk_per_trade_pct`):** Verifica que esté configurado entre **1.0% y 2.0%** máximo del capital total ($1 a $2 USDT por trade para un capital de $100 USDT).
- [ ] **Mínimo de Orden Binance (*Min Notional*):** Para $100 USDT, verifica que la posición resultante sea de al menos **$10 USDT** para cumplir con las reglas del exchange.
- [ ] **Stop Loss y Take Profit:** Asegúrate de que todas las operaciones tengan un Stop Loss bien definido (ej. trazado por ATR o estructura) y una relación riesgo/beneficio de al menos **1:2** o **1:2.5**.

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
