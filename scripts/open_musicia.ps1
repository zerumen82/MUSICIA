<#
Abre Musicia como aplicación de ventana (Electron):
  1. Arranca el motor ACE-Step si no está
  2. Arranca la API (que además sirve la UI) si no está
  3. Abre la ventana de Musicia

Los procesos quedan vivos al cerrar este script. Para pararlos todo:
  powershell -ExecutionPolicy Bypass -File scripts\stop_local.ps1
#>
$ErrorActionPreference = 'Continue'
$raiz = Split-Path -Parent $PSScriptRoot
$logs = Join-Path $raiz 'logs'
New-Item -ItemType Directory -Force -Path $logs | Out-Null

function Test-Endpoint([string]$url) {
    try { $null = Invoke-WebRequest -Uri $url -TimeoutSec 3 -UseBasicParsing; return $true }
    catch { return $false }
}

# 1. Motor
if (-not (Test-Endpoint 'http://127.0.0.1:8001/health')) {
    Write-Host "[motor] arrancando ACE-Step..." -NoNewline
    Start-Process -FilePath (Join-Path $raiz 'vendor\ACE-Step-1.5\.venv\Scripts\python.exe') `
        -ArgumentList '-m', 'acestep.api_server' `
        -WorkingDirectory (Join-Path $raiz 'vendor\ACE-Step-1.5') `
        -RedirectStandardOutput (Join-Path $logs 'acestep-api.log') `
        -RedirectStandardError (Join-Path $logs 'acestep-api.err.log') `
        -WindowStyle Hidden | Out-Null
    $limite = (Get-Date).AddMinutes(4)
    while (-not (Test-Endpoint 'http://127.0.0.1:8001/health') -and (Get-Date) -lt $limite) { Start-Sleep -Seconds 5 }
}
if (Test-Endpoint 'http://127.0.0.1:8001/health') { Write-Host " listo" }
else { Write-Warning "el motor no responde; la app abrira pero no podra generar" }

# 2. API + UI
if (-not (Test-Endpoint 'http://127.0.0.1:8000/health')) {
    Write-Host "[api] arrancando Musicia..." -NoNewline
    Start-Process -FilePath (Join-Path $raiz 'backend\venv\Scripts\python.exe') `
        -ArgumentList 'backend\main.py' `
        -WorkingDirectory $raiz `
        -RedirectStandardOutput (Join-Path $logs 'musicia-api.log') `
        -RedirectStandardError (Join-Path $logs 'musicia-api.err.log') `
        -WindowStyle Hidden | Out-Null
    $limite = (Get-Date).AddSeconds(45)
    while (-not (Test-Endpoint 'http://127.0.0.1:8000/') -and (Get-Date) -lt $limite) { Start-Sleep -Seconds 2 }
}
if (Test-Endpoint 'http://127.0.0.1:8000/') { Write-Host " listo" }
else { Write-Warning "la API no responde; revisa logs\musicia-api.err.log" }

# 3. Ventana
# Lanzamos electron.exe directamente (no el .cmd): así la ventana no hereda
# el estado oculto del PowerShell, y el single-instance lock de main.cjs
# restaurará la ventana si ya había una instancia viva.
Write-Host "[app] abriendo la ventana de Musicia..."
$electronExe = Join-Path $raiz 'frontend\node_modules\electron\dist\electron.exe'
if (-not (Test-Path $electronExe)) {
    throw "No existe electron.exe: $electronExe (ejecuta 'npm install' en frontend)"
}
Start-Process -FilePath $electronExe `
    -ArgumentList (Join-Path $raiz 'frontend') `
    -WorkingDirectory (Join-Path $raiz 'frontend') | Out-Null
# Nota: frontend/main.cjs es el proceso principal de Electron (CommonJS,
# requerido por "type": "module" del package.json).
Write-Host "Musicia abierta. Cierra la ventana para salir (los servicios quedan en segundo plano)."