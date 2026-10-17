<#
Deja el motor ACE-Step (:8001) y la API (:8000) en marcha.

No mata un motor que ya existe: un motor cargado no se reinicia en frío.
La excepción es la API de Musicia: si el proceso sigue vivo y el puerto no
acepta conexiones pasada la espera de config, se repone solo esa API.
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

        # Siempre libera la VRAM al arrancar: mata el motor existente para que
        # la GPU quede libre antes de arrancar uno limpio. Evita que se quede
        # sin memoria entre trabajos largos.
        if ($motorPresente) {
            Write-Output 'MOTOR=liberando-vram'
            foreach ($proc in (Find-Python 'acestep.api_server')) {
                & taskkill.exe /F /T /PID $proc.ProcessId | Out-Null
                Write-Output "MOTOR=detenido (PID $($proc.ProcessId))"
            }
            # Esperar a que suelte el puerto y la VRAM
            $limite = (Get-Date).AddSeconds(15)
            do {
                Start-Sleep -Milliseconds 400
            } while ((Test-Port 8001) -and (Get-Date) -lt $limite)
            if (Test-Port 8001) {
                Write-Output 'MOTOR=vram-no-liberada'
                exit 1
            }
            Write-Output 'MOTOR=vram-liberada'
            $motorArriba = $false
            $motorPresente = $false
        }

        if ($motorArriba) {
            Write-Output 'MOTOR=up'
        } elseif ($motorPresente) {
            Write-Output 'MOTOR=starting'
        } else {
            # vendor no se versiona: aplicar la corrección revisada antes de
            # importar el motor, nunca editar un motor que ya está ejecutándose.
            & (Join-Path $raiz 'backend\venv\Scripts\python.exe') (Join-Path $PSScriptRoot 'apply_acestep_patches.py')
            if ($LASTEXITCODE -ne 0) {
                Write-Output 'MOTOR=patch-failed'
                exit 1
            }
            $env:ACESTEP_LM_BACKEND = 'pt'
            # Cambio de modelo por trabajo (spec/02 [M1]): sin esto el motor
            # ignora en silencio el modelo pedido y usa el primario.
            $env:ACESTEP_ON_DEMAND_MODEL_LOAD = 'true'
            # Sin esto el motor corta a los 600 s y la UI dice que no hubo audio.
            $backend = Join-Path $raiz 'backend'
            $topeLineas = & (Join-Path $backend 'venv\Scripts\python.exe') -c "import sys; sys.path.insert(0, r'$backend'); from config import engine_launch_timeout_seconds; print(engine_launch_timeout_seconds())"
            $tope = @($topeLineas) | Where-Object { "$_" -match '^\d+$' } | Select-Object -Last 1
            if (-not $tope) {
                Write-Output 'MOTOR=timeout-unread'
            } else {
                $env:ACESTEP_GENERATION_TIMEOUT = "$tope"
                Start-Servicio 'MOTOR' `
                    (Join-Path $raiz 'vendor\ACE-Step-1.5\.venv\Scripts\python.exe') `
                    @('-m', 'acestep.api_server') `
                    (Join-Path $raiz 'vendor\ACE-Step-1.5') `
                    (Join-Path $logs 'acestep-api.log') `
                    (Join-Path $logs 'acestep-api.err.log')
            }
        }
    }

    $apiArriba = Test-Endpoint 'http://127.0.0.1:8000/health'
    # «main.py» a secas también es ComfyUI. Solo cuenta el backend de Musicia.
    $apiProcs = @(Find-Python 'backend\main.py') + @(Find-Python 'backend/main.py')
    $apiProcs = @($apiProcs | Where-Object { $_ })
    $apiPort = Test-Port 8000
    $apiPy = Join-Path $raiz 'backend\venv\Scripts\python.exe'
    $apiArgs = @('backend\main.py')
    $apiOut = Join-Path $logs 'musicia-api.log'
    $apiErr = Join-Path $logs 'musicia-api.err.log'
    if ($apiArriba) {
        Write-Output 'API=up'
    } elseif ($apiProcs.Count -gt 0 -and -not $apiPort) {
        # El proceso existe y el puerto no acepta. Si ya pasó la espera, está
        # colgado: se repone solo la API. El motor no se toca.
        $oldest = 0.0
        foreach ($proc in $apiProcs) {
            $created = $proc.CreationDate
            if ($created -is [string]) {
                $created = [System.Management.ManagementDateTimeConverter]::ToDateTime($created)
            }
            $age = ((Get-Date) - [datetime]$created).TotalSeconds
            if ($age -gt $oldest) { $oldest = $age }
        }
        $backend = Join-Path $raiz 'backend'
        $ageText = $oldest.ToString([System.Globalization.CultureInfo]::InvariantCulture)
        & $apiPy -c "import sys; sys.path.insert(0, r'$backend'); from config import get_settings; from api_supervisor import api_is_wedged; raise SystemExit(0 if api_is_wedged(health_ok=False, port_accepts=False, age_seconds=float(sys.argv[1]), grace_seconds=get_settings().api_listen_grace_seconds) else 1)" $ageText
        if ($LASTEXITCODE -eq 0) {
            foreach ($proc in $apiProcs) {
                & taskkill.exe /PID $proc.ProcessId /T /F | Out-Null
            }
            $apiExitWaitSeconds = 15
            $apiExitPollMs = 300
            $deadline = (Get-Date).AddSeconds($apiExitWaitSeconds)
            do {
                Start-Sleep -Milliseconds $apiExitPollMs
            } while (((Find-Python 'backend\main.py').Count + (Find-Python 'backend/main.py').Count) -gt 0 -and (Get-Date) -lt $deadline)
            Start-Servicio 'API' $apiPy $apiArgs $raiz $apiOut $apiErr
            Write-Output 'API=revived'
        } else {
            Write-Output 'API=starting'
        }
    } elseif ($apiProcs.Count -gt 0 -or $apiPort) {
        Write-Output 'API=starting'
    } else {
        Start-Servicio 'API' $apiPy $apiArgs $raiz $apiOut $apiErr
    }
} finally {
    if ($owned) { [void]$mutex.ReleaseMutex() }
    $mutex.Dispose()
}
