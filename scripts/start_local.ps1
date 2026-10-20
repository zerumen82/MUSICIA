<#
Arranca el stack local de Musicia:
  1. API de Musicia (puerto 8000), con ACE-Step en reposo
  2. El motor ACE-Step (puerto 8001) se inicia al enviar una operación que lo use

Los procesos se lanzan con Start-Process para que sobrevivan a la sesión que
los invoca. Los registros quedan en logs/.
#>
param(
    [switch]$SinMotor,
    [switch]$ConMotor
)

$ErrorActionPreference = 'Stop'
if ($SinMotor -and $ConMotor) {
    throw 'Usa -SinMotor o -ConMotor, no ambos.'
}
$raiz = Split-Path -Parent $PSScriptRoot
$logs = Join-Path $raiz 'logs'
New-Item -ItemType Directory -Force -Path $logs | Out-Null
Remove-Item (Join-Path $logs 'stop.flag') -Force -ErrorAction SilentlyContinue

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
    & $ensure -SinMotor -IdleEngine
} elseif ($ConMotor) {
    & $ensure -WakeEngine
} else {
    & $ensure -IdleEngine
    Write-Host '[motor] en reposo; se iniciará al enviar un trabajo de Musicia'
}
if (Test-Puerto $puertoApi) { Write-Host "[api] http://127.0.0.1:$puertoApi" }
else { Write-Warning "[api] no responde; revisa logs\musicia-api.err.log" }

Write-Host "Listo. Frontend: cd frontend; npm run dev"