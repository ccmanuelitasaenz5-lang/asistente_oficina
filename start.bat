@echo off
title Asistente Comunal
cd /d "%~dp0"
echo Iniciando Asistente Comunal...

if not exist "venv\Scripts\python.exe" (
    echo Creando entorno virtual...
    python -m venv venv
    "venv\Scripts\pip.exe" install -r requirements.txt
)

if "%SERVER_HOST%"=="" set SERVER_HOST=127.0.0.1
if "%SERVER_PORT%"=="" set SERVER_PORT=8000

echo.
echo Abriendo navegador...
start http://%SERVER_HOST%:%SERVER_PORT%/
echo Servidor corriendo en http://%SERVER_HOST%:%SERVER_PORT%/
echo Presiona Ctrl+C para detener.
echo.
"venv\Scripts\python.exe" -m uvicorn backend.main:app --host %SERVER_HOST% --port %SERVER_PORT%
echo.
pause
