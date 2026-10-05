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

# 1 y 2. Motor y API. Si ya están, no se tocan. Si no están, se arrancan.
# -Rearme borra la marca de SALIR: abrir la ventana siempre los vuelve a dejar en marcha.
Write-Host "[stack] comprobando motor y API..."
& (Join-Path $PSScriptRoot 'ensure_local.ps1') -Rearme

$limite = (Get-Date).AddMinutes(4)
while (-not (Test-Endpoint 'http://127.0.0.1:8001/health') -and (Get-Date) -lt $limite) { Start-Sleep -Seconds 5 }
if (Test-Endpoint 'http://127.0.0.1:8001/health') { Write-Host "[motor] listo" }
else { Write-Warning "el motor no responde; la app abrira pero no podra generar" }

$limite = (Get-Date).AddSeconds(45)
while (-not (Test-Endpoint 'http://127.0.0.1:8000/') -and (Get-Date) -lt $limite) { Start-Sleep -Seconds 2 }
if (Test-Endpoint 'http://127.0.0.1:8000/') { Write-Host "[api] listo" }
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
Write-Host "Musicia abierta. La X deja la ventana en la bandeja. SALIR apaga motor y API."