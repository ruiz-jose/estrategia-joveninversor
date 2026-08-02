@echo off
REM --- Lanzador de un solo comando para el Trading Bot ---
REM Uso:  run.bat            (doble clic o desde cmd/PowerShell)
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo ============================================
echo   Trading Bot Quant - Inicio Automatico
echo ============================================

REM 1. Crear entorno virtual si no existe
if not exist ".venv\Scripts\python.exe" (
    echo [1/4] Creando entorno virtual en .venv ...
    python -m venv .venv
    if errorlevel 1 (
        echo ERROR: No se pudo crear el entorno virtual. Verifica que Python este instalado y en el PATH.
        pause
        exit /b 1
    )
) else (
    echo [1/4] Entorno virtual ya existe.
)

REM 2. Instalar/actualizar dependencias
echo [2/4] Instalando dependencias de requirements.txt ...
".venv\Scripts\python.exe" -m pip install -q --disable-pip-version-check -r requirements.txt
if errorlevel 1 (
    echo ERROR: Fallo la instalacion de dependencias.
    pause
    exit /b 1
)

REM 3. Preparar archivo .env si falta
if not exist ".env" (
    echo [3/4] No se encontro .env, copiando desde .env.example ...
    copy /y ".env.example" ".env" >nul
    echo.
    echo   ADVERTENCIA: Edita el archivo .env con tus claves reales de Binance/Telegram
    echo   antes de operar. Por defecto TESTNET=true ^(modo prueba, sin riesgo^).
    echo.
) else (
    echo [3/4] Archivo .env encontrado.
)

REM 4. Arrancar el servidor del bot
echo [4/4] Iniciando el bot...
echo Dashboard disponible en http://localhost:5000
echo Presiona Ctrl+C para detener.
echo.
".venv\Scripts\python.exe" trading_bot\server.py

endlocal
