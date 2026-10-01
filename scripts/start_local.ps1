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

$pythonMotor = Join-Path $raiz 'vendor\ACE-Step-1.5\.venv\Scripts\python.exe'
$pythonApi = Join-Path $raiz 'backend\venv\Scripts\python.exe'
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

if (-not $SinMotor) {
    if (Test-Puerto $puertoMotor) {
        Write-Host "[motor] ya estaba levantado en $puertoMotor"
    } elseif (-not (Test-Path $pythonMotor)) {
        throw "No existe el entorno del motor: $pythonMotor (ejecuta 'uv sync' en vendor\ACE-Step-1.5)"
    } else {
        Write-Host "[motor] arrancando ACE-Step 1.5..."
        $env:ACESTEP_LM_BACKEND = 'pt'
        Start-Process -FilePath $pythonMotor `
            -ArgumentList '-m', 'acestep.api_server' `
            -WorkingDirectory (Join-Path $raiz 'vendor\ACE-Step-1.5') `
            -RedirectStandardOutput (Join-Path $logs 'acestep-api.log') `
            -RedirectStandardError (Join-Path $logs 'acestep-api.err.log') `
            -WindowStyle Hidden | Out-Null

        $esperado = (Get-Date).AddMinutes(3)
        while ((Get-Date) -lt $esperado) {
            Start-Sleep -Seconds 5
            if (Test-Puerto $puertoMotor) { break }
        }
        if (Test-Puerto $puertoMotor) {
            Write-Host "[motor] listo en http://127.0.0.1:$puertoMotor"
        } else {
            Write-Warning "[motor] no responde todavia; revisa logs\acestep-api.err.log (la 1a vez descarga ~10 GB de pesos)"
        }
    }
}

if (Test-Puerto $puertoApi) {
    Write-Host "[api] ya estaba levantada en $puertoApi"
} else {
    Write-Host "[api] arrancando Musicia API..."
    Start-Process -FilePath $pythonApi `
        -ArgumentList 'backend\main.py' `
        -WorkingDirectory $raiz `
        -RedirectStandardOutput (Join-Path $logs 'musicia-api.log') `
        -RedirectStandardError (Join-Path $logs 'musicia-api.err.log') `
        -WindowStyle Hidden | Out-Null
    Start-Sleep -Seconds 4
    Write-Host "[api] http://127.0.0.1:$puertoApi  (salud: http://127.0.0.1:$puertoApi/health)"
}

Write-Host "Listo. Frontend: cd frontend; npm run dev"