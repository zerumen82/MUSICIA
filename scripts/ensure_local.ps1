<#
Deja el motor ACE-Step (:8001) y la API (:8000) en marcha.

No mata un proceso que ya existe: un motor cargado no se reinicia en frío.
Si el proceso no está, lo arranca. Si SALIR escribió logs\stop.flag, no arranca
nada, salvo que se llame con -Rearme (la siguiente apertura de la ventana).

No es un segundo supervisor que tire de la GPU. Solo cubre el hueco.
#>
param(
    [switch]$SinMotor,
    [switch]$Rearme
)

$ErrorActionPreference = 'Continue'
$raiz = Split-Path -Parent $PSScriptRoot
$logs = Join-Path $raiz 'logs'
New-Item -ItemType Directory -Force -Path $logs | Out-Null
$flag = Join-Path $logs 'stop.flag'

if ($Rearme) {
    Remove-Item $flag -Force -ErrorAction SilentlyContinue
} elseif (Test-Path $flag) {
    Write-Output 'HOLD'
    exit 0
}

$mutex = New-Object System.Threading.Mutex($false, 'Local\MusiciaEnsure')
$owned = $false
try {
    $owned = $mutex.WaitOne(8000)
} catch [System.Threading.AbandonedMutexException] {
    $owned = $true
}
if (-not $owned) {
    Write-Output 'BUSY'
    exit 0
}

function Test-Endpoint([string]$url) {
    try {
        $null = Invoke-WebRequest -Uri $url -TimeoutSec 3 -UseBasicParsing
        return $true
    } catch {
        return $false
    }
}

function Test-Port([int]$puerto) {
    $cliente = New-Object System.Net.Sockets.TcpClient
    try {
        $espera = $cliente.BeginConnect('127.0.0.1', $puerto, $null, $null)
        $abierto = $espera.AsyncWaitHandle.WaitOne(400)
        if (-not $abierto) { return $false }
        $cliente.EndConnect($espera)
        return $true
    } catch {
        return $false
    } finally {
        $cliente.Close()
    }
}

function Find-Python([string]$filtro) {
    @(Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -like "*$filtro*" })
}

function Start-Servicio([string]$etiqueta, [string]$python, [string[]]$argumentos, [string]$cwd, [string]$salida, [string]$errorLog) {
    if (Test-Path $flag) {
        Write-Output "$etiqueta=hold"
        return
    }
    if (-not (Test-Path $python)) {
        Write-Output "$etiqueta=missing"
        return
    }
    foreach ($log in @($salida, $errorLog)) {
        if ((Test-Path $log) -and (Get-Item $log).Length -gt 0) {
            Copy-Item $log "$log.bak" -Force
        }
    }
    Start-Process -FilePath $python `
        -ArgumentList $argumentos `
        -WorkingDirectory $cwd `
        -RedirectStandardOutput $salida `
        -RedirectStandardError $errorLog `
        -WindowStyle Hidden | Out-Null
    Write-Output "$etiqueta=started"
}

try {
    if (-not $SinMotor) {
        $motorArriba = Test-Endpoint 'http://127.0.0.1:8001/health'
        $motorPresente = (Find-Python 'acestep.api_server').Count -gt 0 -or (Test-Port 8001)
        if ($motorArriba) {
            Write-Output 'MOTOR=up'
        } elseif ($motorPresente) {
            Write-Output 'MOTOR=starting'
        } else {
            $env:ACESTEP_LM_BACKEND = 'pt'
            # Cambio de modelo por trabajo (spec/02 [M1]): sin esto el motor
            # ignora en silencio el modelo pedido y usa el primario.
            $env:ACESTEP_ON_DEMAND_MODEL_LOAD = 'true'
            Start-Servicio 'MOTOR' `
                (Join-Path $raiz 'vendor\ACE-Step-1.5\.venv\Scripts\python.exe') `
                @('-m', 'acestep.api_server') `
                (Join-Path $raiz 'vendor\ACE-Step-1.5') `
                (Join-Path $logs 'acestep-api.log') `
                (Join-Path $logs 'acestep-api.err.log')
        }
    }

    $apiArriba = Test-Endpoint 'http://127.0.0.1:8000/health'
    # «main.py» a secas también es ComfyUI. Solo cuenta el backend de Musicia.
    $apiPresente = (Find-Python 'backend\main.py').Count -gt 0 -or (Find-Python 'backend/main.py').Count -gt 0 -or (Test-Port 8000)
    if ($apiArriba) {
        Write-Output 'API=up'
    } elseif ($apiPresente) {
        Write-Output 'API=starting'
    } else {
        Start-Servicio 'API' `
            (Join-Path $raiz 'backend\venv\Scripts\python.exe') `
            @('backend\main.py') `
            $raiz `
            (Join-Path $logs 'musicia-api.log') `
            (Join-Path $logs 'musicia-api.err.log')
    }
} finally {
    if ($owned) { [void]$mutex.ReleaseMutex() }
    $mutex.Dispose()
}
