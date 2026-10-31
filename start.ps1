Set-Location -LiteralPath $PSScriptRoot
Write-Host "Iniciando Asistente Comunal..." -ForegroundColor Green

# Verificar venv
if (-not (Test-Path "venv\Scripts\python.exe")) {
    Write-Host "Creando entorno virtual..." -ForegroundColor Yellow
    python -m venv venv
    & "venv\Scripts\pip.exe" install -r requirements.txt
}

$host_addr = if ($env:SERVER_HOST) { $env:SERVER_HOST } else { "127.0.0.1" }
$port = if ($env:SERVER_PORT) { $env:SERVER_PORT } else { "8000" }

# Matar proceso previo en puerto especificado si existe
$process = netstat -ano | Select-String ":$port " | Select-String "LISTENING"
if ($process) {
    $pid_num = $process.Line -replace '.*\s+(\d+)\s*$', '$1'
    taskkill /F /PID $pid_num 2>$null
    Start-Sleep -Seconds 1
}

# Abrir navegador
Start-Process "http://$host_addr`:$port/"

Write-Host "Servidor en http://$host_addr`:$port/ - Presiona Ctrl+C para detener" -ForegroundColor Cyan
& "venv\Scripts\python.exe" -m uvicorn backend.main:app --host $host_addr --port $port

Read-Host "Servidor detenido. Presiona Enter para salir"
