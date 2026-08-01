# 🚀 Guía de Despliegue en la Nube 24/7 - Bot de Trading Algorítmico

Esta guía contiene el paso a paso completo para desplegar y mantener ejecutando tu bot de trading algorítmico **conectado 24/7 a internet** en temporalidad diaria (`1d`), con una gestión de capital de **100 USDT** y notificaciones integradas a **Telegram**.

---

## 📌 Requisitos Previos

1. **Cuenta en Binance** (Spot o Futures) con saldo disponible (ej. 100 USDT).
2. **Bot Token y Chat ID de Telegram** (ya incluidos en tu archivo `.env`).
3. **Servidor Virtual en la Nube (VPS)** o servicio de PaaS (Railway, Render, Hetzner, DigitalOcean, AWS Lightsail).

---

## 🔑 Paso 1: Configuración de Claves API en Binance

1. Ingresa a Binance → **Gestión de API** (*API Management*).
2. Haz clic en **Crear API** (*System Generated*).
3. **Configuración de Permisos (¡CRÍTICO!):**
   - ✅ Habilitar **Lectura** (*Enable Reading*).
   - ✅ Habilitar **Trading Spot / Futures** (*Enable Spot & Margin Trading / Futures*).
   - ❌ **DESHABILITAR Retiros (*Enable Withdrawals*)**. Jamás otorgues este permiso a ningún bot por razones de seguridad.
4. Copia tu `API Key` y `Secret Key` en un lugar seguro.

---

## ☁️ Paso 2: Elección del Servidor VPS Nube

Recomendamos utilizar un servidor Linux con sistema operativo **Ubuntu 22.04 LTS o 24.04 LTS**.

* **Opciones recomendadas ($4 - $6 USD/mes):**
  - **Hetzner Cloud:** CX22 (~€4/mes) - *Excelente rendimiento en Europa/EEUU*.
  - **DigitalOcean:** Droplet básico ($6/mes).
  - **AWS Lightsail:** Instancia de $3.50 a $5/mes.
  - **Railway.app / Render.com:** Opciones PaaS serverless de bajo consumo.

---

## 💻 Paso 3: Configuración Inicial del Servidor por SSH

Conéctate a tu servidor VPS mediante la terminal (o PuTTY en Windows):

```bash
ssh ubuntu@IP_DE_TU_SERVIDOR
```

Una vez dentro, ejecuta los siguientes comandos para actualizar el sistema e instalar Python:

```bash
# 1. Actualizar repositorios del sistema
sudo apt update && sudo apt upgrade -y

# 2. Instalar Python 3, Pip y Git
sudo apt install python3-pip python3-venv git -y

# 3. Clonar el repositorio de tu proyecto
git clone https://github.com/TU_USUARIO/estrategia-joveninversor.git
cd estrategia-joveninversor

# 4. Crear el entorno virtual e instalar dependencias
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

---

## ⚙️ Paso 4: Crear el Archivo de Variables de Entorno (`.env`)

En la carpeta raíz del proyecto en el VPS, crea el archivo `.env`:

```bash
nano .env
```

Pega el siguiente contenido adaptado a tus datos:

```env
# ── Credenciales de Binance ─────────────────────────────────────────
BINANCE_API_KEY=tu_api_key_aqui
BINANCE_API_SECRET=tu_api_secret_aqui

# false = OPERAR CON DINERO REAL | true = TESTNET (Modo Prueba)
TESTNET=false

# Capital inicial asignado
INITIAL_CAPITAL=100

# Par y Temporalidad por defecto
SYMBOL=BTCUSDT
TIMEFRAME=1d

# ── Notificaciones de Telegram ──────────────────────────────────────
TELEGRAM_BOT_TOKEN=***REDACTED_TELEGRAM_BOT_TOKEN***
TELEGRAM_CHAT_ID=***REDACTED_TELEGRAM_CHAT_ID***
```

*(Para guardar en `nano`: Presiona `Ctrl + O`, luego `Enter` y sal con `Ctrl + X`)*.

---

## 🔄 Paso 5: Autoejecución 24/7 con `systemd` (Linux Service)

Para garantizar que el bot se mantenga encendido todo el tiempo y **se reinicie automáticamente** en caso de fallos de red o reinicios del servidor, crearemos un servicio `systemd`.

1. Crea el archivo de servicio:
   ```bash
   sudo nano /etc/systemd/system/tradingbot.service
   ```

2. Pega esta configuración (asegúrate de que las rutas coincidan con tu usuario de Linux):
   ```ini
   [Unit]
   Description=Trading Bot Algoritmico Quant - Estrategia 24/7
   After=network.target

   [Service]
   User=ubuntu
   WorkingDirectory=/home/ubuntu/estrategia-joveninversor
   ExecStart=/home/ubuntu/estrategia-joveninversor/venv/bin/python trading_bot/server.py
   Restart=always
   RestartSec=10
   Environment=PYTHONUNBUFFERED=1

   [Install]
   WantedBy=multi-user.target
   ```

3. Recarga los demonios y activa el servicio:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable tradingbot
   sudo systemctl start tradingbot
   ```

---

## 📊 Paso 6: Comandos de Monitoreo y Verificación

- **Verificar que el bot esté funcionando:**
  ```bash
  sudo systemctl status tradingbot
  ```

- **Ver los registros (logs) en tiempo real:**
  ```bash
  sudo journalctl -u tradingbot -f
  ```

- **Acceso a la Interfaz Web:**
  Abre cualquier navegador web e ingresa a:
  `http://IP_DE_TU_SERVIDOR:5000`

---

## 📲 Notificaciones Automáticas en Telegram

Una vez activo, recibirás sin necesidad de configurar nada adicional:

1. 🚀 **Alerta Instantánea de Apertura:** Se enviará al abrir cualquier posición LONG/SHORT (con precio de entrada, Stop Loss y Take Profit).
2. 🎯 / 🛑 **Alerta Instantánea de Cierre:** Se enviará al cerrarse una posición (con el resultado en $ USDT, % de ganancia/pérdida y nuevo balance).
3. ☀️ **Reporte Diario a las 12:00 PM:** Cada mediodía recibirás el estado de la cuenta, balance actualizado, retorno acumulado y posición activa flotante.
