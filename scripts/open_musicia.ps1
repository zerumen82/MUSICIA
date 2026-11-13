<#
Abre Musicia como aplicación de ventana (Electron):
  1. Arranca la API (:8000) con el motor ACE-Step (:8001) activo
  2. Abre Electron inmediatamente; la UI queda disponible
  3. El motor carga modelos al recibir el primer trabajo

SALIR apaga la API y el motor. La X conserva la ventana según el contrato.
No queda nada arrancado en segundo plano.
#>
$ErrorActionPreference = 'Continue'
$raiz = Split-Path -Parent $PSScriptRoot
$logs = Join-Path $raiz 'logs'
New-Item -ItemType Directory -Force -Path $logs | Out-Null

# Quitar posible marca de parada previa y de reposo para que el arranque no se bloquee
Remove-Item (Join-Path $logs 'stop.flag') -Force -ErrorAction SilentlyContinue
Remove-Item (Join-Path $logs 'engine.idle') -Force -ErrorAction SilentlyContinue

# El supervisor conserva los procesos ajenos y comprueba identidad antes de
# cualquier rearme. Un patrón como backend/main.py también coincide con otros
# proyectos: el lanzador nunca debe terminar esos procesos por su nombre.

# 1. Arrancar stack local (API arriba, motor ACTIVO: cargará modelos al primer trabajo)
Write-Host "[app] arrancando servidor de Musicia..."
$ensure = Join-Path $PSScriptRoot 'ensure_local.ps1'
& $ensure | Out-Null

$apiArriba = $false
for ($i = 0; $i -lt 30; $i++) {
    try {
        $null = Invoke-WebRequest -Uri "http://127.0.0.1:8000/health" -TimeoutSec 2 -UseBasicParsing
        $apiArriba = $true
        break
    } catch { Start-Sleep -Seconds 1 }
}
if (-not $apiArriba) {
    Write-Warning "[app] la API no respondio; revisa logs\musicia-api.err.log"
}

# 2. Abrir la ventana de Electron
Write-Host "[app] abriendo la ventana de Musicia..."
$electronExe = Join-Path $raiz 'frontend\node_modules\electron\dist\electron.exe'
if (-not (Test-Path $electronExe)) {
    throw "No existe electron.exe: $electronExe (ejecuta 'npm install' en frontend)"
}
$electronProc = Start-Process -FilePath $electronExe `
    -ArgumentList (Join-Path $raiz 'frontend') `
    -WorkingDirectory (Join-Path $raiz 'frontend') -PassThru
Write-Host "Musicia abierta (Electron PID $($electronProc.Id)). Usa SALIR para apagar la ventana y sus servicios."

# 3. Esperar a que el usuario cierre la ventana de Musicia.
#    Se espera SOLO al proceso de Electron que lanzó este lanzador (y sus
#    hijos directos): si queda otra aplicación Electron abierta (VS Code,
#    Discord...), SALIR de Musicia sigue terminando y apagando los servicios.
#    Fallos de consulta o identidad ambigua no autorizan parar nada ajeno.
Start-Sleep -Seconds 5
Write-Host "[app] esperando a que cierres la ventana de Musicia..."
try {
    while ($true) {
        $propio = Get-CimInstance Win32_Process -Filter "ProcessId = $($electronProc.Id)" -ErrorAction SilentlyContinue
        $hijos = @(Get-CimInstance Win32_Process -Filter "ParentProcessId = $($electronProc.Id)" -ErrorAction SilentlyContinue)
        if (-not $propio -and $hijos.Count -eq 0) { break }
        Start-Sleep -Seconds 2
    }
} catch {
    # Interrumpido por el usuario o consola cerrada: no se toca ningún proceso ajeno.
}

# 4. Apagar motor y API al salir
Write-Host "[app] cerrando Musicia y liberando puertos..."
$stop = Join-Path $PSScriptRoot 'stop_local.ps1'
& $stop | Out-Null
Write-Host "Musicia cerrada. Nada queda arrancado."
