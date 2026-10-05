<#
Arranca el stack local de Musicia:
  1. Motor de música ACE-Step 1.5 (puerto 8001) en vendor/ACE-Step-1.5
  2. API de Musicia (puerto 8000) al detectarse el motor

Los procesos se lanzan con Start-Process para que sobrevivan a la sesión que
los invoca. Los registros quedan en logs/.
#>
param(
    [switch]$SinMotor
)

$ErrorActionPreference = 'Stop'
$raiz = Split-Path -Parent $PSScriptRoot
$logs = Join-Path $raiz 'logs'
New-Item -ItemType Directory -Force -Path $logs | Out-Null

$puertoMotor = 8001
$puertoApi = 8000

function Test-Puerto([int]$puerto) {
    try {
        $null = Invoke-WebRequest -Uri "http://127.0.0.1:$puerto/health" -TimeoutSec 3 -UseBasicParsing
        return $true
    } catch {
        return $false
    }
}

$ensure = Join-Path $PSScriptRoot 'ensure_local.ps1'
if ($SinMotor) {
    & $ensure -SinMotor -Rearme
} else {
    & $ensure -Rearme
    $esperado = (Get-Date).AddMinutes(3)
    while ((Get-Date) -lt $esperado -and -not (Test-Puerto $puertoMotor)) { Start-Sleep -Seconds 5 }
    if (Test-Puerto $puertoMotor) { Write-Host "[motor] listo en http://127.0.0.1:$puertoMotor" }
    else { Write-Warning "[motor] no responde todavia; revisa logs\acestep-api.err.log" }
}
if (Test-Puerto $puertoApi) { Write-Host "[api] http://127.0.0.1:$puertoApi" }
else { Write-Warning "[api] no responde; revisa logs\musicia-api.err.log" }

Write-Host "Listo. Frontend: cd frontend; npm run dev"