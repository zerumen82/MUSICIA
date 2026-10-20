<#
Abre Musicia como aplicación de ventana (Electron):
  1. Arranca la API (:8000) con el motor ACE-Step (:8001) activo
  2. Abre Electron inmediatamente; la UI queda disponible
  3. El motor carga modelos al recibir el primer trabajo

Al cerrar la ventana / salir de Musicia, se apagan la API y el motor.
No queda nada arrancado en segundo plano.
#>
$ErrorActionPreference = 'Continue'
$raiz = Split-Path -Parent $PSScriptRoot
$logs = Join-Path $raiz 'logs'
New-Item -ItemType Directory -Force -Path $logs | Out-Null

# Quitar posible marca de parada previa y de reposo para que el arranque no se bloquee
Remove-Item (Join-Path $logs 'stop.flag') -Force -ErrorAction SilentlyContinue
Remove-Item (Join-Path $logs 'engine.idle') -Force -ErrorAction SilentlyContinue

# Limpiar procesos residuales de Musicia para evitar conflictos de puerto
# o procesos huérfanos que bloqueen el wake del motor. Solo afecta procesos
# de Musicia (backend o motor ACE-Step), no otras apps del usuario.
try {
    # WQL exige OR (no el -or de PowerShell): con -or la consulta es inválida,
    # Silencioso la traga y no se mataba NADA (problema del 2026-10-19).
    $musiciaProcs = Get-CimInstance Win32_Process -Filter "Name = 'python.exe' OR Name = 'uv.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -like '*backend\main.py*' -or $_.CommandLine -like '*backend/main.py*' -or $_.CommandLine -like '*-m acestep.api_server*' }
    foreach ($p in $musiciaProcs) {
        & taskkill.exe /F /T /PID $p.ProcessId 2>$null | Out-Null
    }
} catch {}
Start-Sleep -Seconds 3

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
Start-Process -FilePath $electronExe `
    -ArgumentList (Join-Path $raiz 'frontend') `
    -WorkingDirectory (Join-Path $raiz 'frontend') | Out-Null
Write-Host "Musicia abierta. Al cerrar la ventana se apaga el servidor."

# 3. Esperar a que el usuario cierre Electron.
#    Electron lanza varios procesos (main + renderer). Damos tiempo de arranque
#    y luego monitoreamos cualquier proceso electron.exe. Cuando ya no quede
#    ninguno, se entiende que el usuario cerro la ventana.
Start-Sleep -Seconds 5
Write-Host "[app] esperando a que cierres la ventana de Musicia..."
try {
    while ($true) {
        $electronProcs = @(Get-CimInstance Win32_Process -Filter "Name = 'electron.exe'" -ErrorAction SilentlyContinue)
        if ($electronProcs.Count -eq 0) { break }
        Start-Sleep -Seconds 2
    }
} catch {
    # Interrumpido por el usuario o consola cerrada
}

# 4. Apagar motor y API al salir
Write-Host "[app] cerrando Musicia y liberando puertos..."
$stop = Join-Path $PSScriptRoot 'stop_local.ps1'
& $stop | Out-Null
Write-Host "Musicia cerrada. Nada queda arrancado."
