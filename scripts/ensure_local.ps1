<#
Deja el motor ACE-Step (:8001) y la API (:8000) en marcha.

El watchdog conserva cualquier motor presente aunque /health tarde: puede
estar cargando o generando. -IdleEngine pausa solo el PID que el supervisor
registró y verificó; -WakeEngine quita el reposo, garantiza una sola instancia
y espera /health real. -Rearme solo reinicia el PID propio verificable.
Un proceso presente o puerto abierto se preserva aunque /health tarde:
puede estar cargando o generando. Un bloqueo real requiere rearme explícito.
La API solo se repone si el proceso sigue vivo y el puerto no acepta
conexiones pasada la espera de config (colgada de verdad).
En el arranque de la app (-Rearme) también se reemplaza una API que
responde pero corre un proceso anterior al último cambio de backend/*.py:
relanzar no puede conservar el código viejo. El vigilante de la ventana
(sin -Rearme) no decide eso: una API en marcha se preserva.
Si el proceso no está, lo arranca. Si SALIR escribió logs\stop.flag, no arranca
nada; los lanzadores limpian una marca anterior antes de abrir la ventana o
iniciar explícitamente el stack.

Sin controles explícitos es el watchdog de la ventana y la recuperación del
backend: respeta logs\engine.idle y nunca mata un proceso desconocido.
#>
param(
    [switch]$SinMotor,
    [switch]$Rearme,
    [switch]$IdleEngine,
    [switch]$WakeEngine,
    [switch]$InspectEngine,
    [int]$StartTimeoutSeconds = 600,
    [int]$StopTimeoutSeconds = 15
)

$ErrorActionPreference = 'Continue'
$raiz = Split-Path -Parent $PSScriptRoot
. (Join-Path $PSScriptRoot 'engine_identity.ps1')
$logs = Join-Path $raiz 'logs'
New-Item -ItemType Directory -Force -Path $logs | Out-Null
$flag = Join-Path $logs 'stop.flag'
$idleFlag = Join-Path $logs 'engine.idle'
$lifecycleErrorFile = Join-Path $logs 'engine.lifecycle-error'
$engineOwnerFile = Join-Path $logs 'engine.pid.json'
$motorIniciado = $false
$motorProcesoId = $null
$engineControlError = $false

if ($InspectEngine -and ($IdleEngine -or $WakeEngine -or $Rearme)) {
    Write-Output 'MOTOR=control-conflict'
    exit 2
}
if ($IdleEngine -and $WakeEngine) {
    Write-Output 'MOTOR=control-conflict'
    exit 2
}
if ($Rearme -and -not $SinMotor -and -not $IdleEngine -and -not $WakeEngine) {
    $WakeEngine = $true
}
if ($IdleEngine) {
    [System.IO.File]::WriteAllText($idleFlag, (Get-Date).ToUniversalTime().ToString('o'))
}
if (Test-Path -LiteralPath $flag) {
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
    if ($InspectEngine) {
        Write-Output '{"state":"reconciling"}'
        exit 0
    }
    Write-Output 'BUSY'
    if ($IdleEngine -or $WakeEngine) { exit 1 }
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

function Get-OldestApiAgeSeconds([object[]]$procs) {
    $oldest = 0.0
    foreach ($proc in $procs) {
        $created = $proc.CreationDate
        if ($created -is [string]) {
            $created = [System.Management.ManagementDateTimeConverter]::ToDateTime($created)
        }
        $age = ((Get-Date) - [datetime]$created).TotalSeconds
        if ($age -gt $oldest) { $oldest = $age }
    }
    return $oldest
}

function Get-NewestApiSourceAgeSeconds([string]$backendDir) {
    $newest = $null
    foreach ($file in @(Get-ChildItem -LiteralPath $backendDir -Filter '*.py' -File -ErrorAction SilentlyContinue)) {
        if ($null -eq $newest -or $file.LastWriteTime -gt $newest) { $newest = $file.LastWriteTime }
    }
    if ($null -eq $newest) { return $null }
    return ((Get-Date) - $newest).TotalSeconds
}

function Get-VerifiedEngineOwner {
    if (-not (Test-Path -LiteralPath $engineOwnerFile -PathType Leaf)) {
        if ((Find-Python 'acestep.api_server').Count -gt 0 -or (Test-Port 8001)) {
            throw 'No hay PID de motor Musicia verificable; se preserva el proceso.'
        }
        return $null
    }
    try {
        $owner = Get-Content -LiteralPath $engineOwnerFile -Raw | ConvertFrom-Json -ErrorAction Stop
        $enginePid = [int]$owner.pid
    } catch {
        throw "No se pudo validar $engineOwnerFile; se preserva el motor."
    }
    if ($enginePid -le 0 -or -not $owner.creation_date -or -not $owner.executable_path -or -not $owner.command_line) {
        throw "El PID registrado en $engineOwnerFile está incompleto; se preserva el motor."
    }
    $proc = Get-CimInstance Win32_Process -Filter "ProcessId = $enginePid" -ErrorAction SilentlyContinue
    if (-not $proc) {
        Remove-Item -LiteralPath $engineOwnerFile -Force -ErrorAction SilentlyContinue
        if (Test-Port 8001) {
            throw 'El PID registrado terminó, pero el puerto 8001 sigue ocupado; se preserva el proceso ajeno.'
        }
        return $null
    }
    $actualExe = [string]$proc.ExecutablePath
    $expectedExe = [string]$owner.executable_path
    $actualLine = [string]$proc.CommandLine
    if (-not (Test-EngineCreationDate $owner.creation_date $proc.CreationDate) -or
        -not $actualExe -or -not $expectedExe -or
        -not [string]::Equals($actualExe, $expectedExe, [StringComparison]::OrdinalIgnoreCase) -or
        $actualLine -ne [string]$owner.command_line -or
        $actualLine -notlike '*-m acestep.api_server*') {
        throw "La identidad del PID $enginePid no coincide con la propiedad registrada; se preserva el proceso."
    }
    return $proc
}

function Write-EngineOwner([int]$enginePid) {
    $limite = (Get-Date).AddSeconds(10)
    $proc = $null
    do {
        $proc = Get-CimInstance Win32_Process -Filter "ProcessId = $enginePid" -ErrorAction SilentlyContinue
        if ($proc -and $proc.ExecutablePath -and $proc.CommandLine -like '*-m acestep.api_server*') { break }
        Start-Sleep -Milliseconds 100
    } while ((Get-Date) -lt $limite)
    if (-not $proc -or -not $proc.ExecutablePath -or $proc.CommandLine -notlike '*-m acestep.api_server*') {
        throw "No se pudo acreditar el PID $enginePid del motor recién iniciado."
    }
    $owner = [ordered]@{
        pid = [int]$enginePid
        creation_date = Format-EngineCreationDate $proc.CreationDate
        executable_path = [string]$proc.ExecutablePath
        command_line = [string]$proc.CommandLine
    } | ConvertTo-Json
    $pending = "$engineOwnerFile.new"
    [System.IO.File]::WriteAllText($pending, $owner)
    Move-Item -LiteralPath $pending -Destination $engineOwnerFile -Force
}

function Stop-OwnedEngine([string]$motivo) {
    Write-Output "MOTOR=$motivo"
    $proc = Get-VerifiedEngineOwner
    if (-not $proc) {
        Write-Output 'MOTOR=detenido'
        return
    }
    $enginePid = [int]$proc.ProcessId
    try {
        Stop-Process -Id $enginePid -Force -ErrorAction Stop
    } catch {
        throw "No se pudo detener el PID Musicia verificado ${enginePid}: $_"
    }
    $limite = (Get-Date).AddSeconds([Math]::Max(1, $StopTimeoutSeconds))
    do {
        Start-Sleep -Milliseconds 250
        $current = Get-CimInstance Win32_Process -Filter "ProcessId = $enginePid" -ErrorAction SilentlyContinue
    } while ($current -and $current.CreationDate -eq $proc.CreationDate -and (Get-Date) -lt $limite)
    if ($current -and $current.CreationDate -eq $proc.CreationDate) {
        throw "Tiempo agotado esperando la salida del PID $enginePid."
    }
    Remove-Item -LiteralPath $engineOwnerFile -Force -ErrorAction SilentlyContinue
    if (Test-Port 8001) {
        throw 'El PID Musicia terminó, pero el puerto 8001 sigue ocupado; no se toca su propietario.'
    }
    Write-Output "MOTOR=detenido (PID $enginePid)"
}

function Stop-Started-Motor {
    Stop-OwnedEngine 'cancelando-arranque'
}

function Stop-Motor([string]$motivo) {
    Stop-OwnedEngine $motivo
}

function Get-EngineLifecycleStatus {
    $owner = Get-VerifiedEngineOwner -ErrorAction SilentlyContinue
    if ($owner) {
        $state = if (
            (Test-Port 8001) -and (Test-Endpoint 'http://127.0.0.1:8001/health')
        ) { 'awake' } else { 'starting' }
        return [pscustomobject]@{ state = $state; process_id = [int]$owner.ProcessId }
    }
    # Motor presente sin archivo de identidad: si responde al health, está activo.
    # No lanzar excepción: eso bloquearía el backend al hacer InspectEngine.
    if ((Find-Python 'acestep.api_server').Count -gt 0 -or (Test-Port 8001)) {
        $state = if (Test-Endpoint 'http://127.0.0.1:8001/health') { 'awake' } else { 'starting' }
        return [pscustomobject]@{ state = $state; process_id = $null }
    }
    if (Test-Path -LiteralPath $lifecycleErrorFile -PathType Leaf) {
        $detail = (Get-Content -LiteralPath $lifecycleErrorFile -Raw -ErrorAction Stop).Trim()
        return [pscustomobject]@{
            state = 'error'
            error = $(if ($detail) { $detail } else { 'El supervisor no pudo verificar el estado del motor.' })
        }
    }
    return [pscustomobject]@{ state = 'idle' }
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
    # Persistir logs: antes de sobrescribir, guardar copia con timestamp
    # para que nada se pierda entre arranques ni tras un corte del motor.
    $ts = (Get-Date).ToString('yyyyMMdd_HHmmss')
    foreach ($log in @($salida, $errorLog)) {
        if ((Test-Path $log) -and (Get-Item $log).Length -gt 0) {
            Copy-Item $log "$log.bak" -Force
            Copy-Item $log "$log.$ts" -Force
        }
    }
    $proceso = Start-Process -FilePath $python `
        -ArgumentList $argumentos `
        -WorkingDirectory $cwd `
        -RedirectStandardOutput $salida `
        -RedirectStandardError $errorLog `
        -WindowStyle Hidden -PassThru
    if ($etiqueta -eq 'MOTOR') {
        $script:motorProcesoId = $proceso.Id
        $script:motorIniciado = $true
        Write-EngineOwner -enginePid $proceso.Id
    }
    Write-Output "$etiqueta=started"
}

try {
    if (Test-Path -LiteralPath $flag) {
        Write-Output 'HOLD'
        exit 0
    }
    if ($InspectEngine) {
        try {
            $status = Get-EngineLifecycleStatus
        } catch {
            $status = [pscustomobject]@{ state = 'error'; error = ($_ | Out-String).Trim() }
        }
        $status | ConvertTo-Json -Compress
        exit 0
    }
    if ($WakeEngine) {
        Remove-Item -LiteralPath $idleFlag -Force -ErrorAction SilentlyContinue
    }
    if ($IdleEngine) {
        try {
            Stop-OwnedEngine 'reposo-solicitado'
            Remove-Item -LiteralPath $lifecycleErrorFile -Force -ErrorAction SilentlyContinue
        } catch {
            $detalle = ($_ | Out-String).Trim()
            if ($IdleEngine -or $WakeEngine) {
                [System.IO.File]::WriteAllText($lifecycleErrorFile, $detalle)
            }
            [Console]::Error.WriteLine($detalle)
            $engineControlError = $true
        }
    }

    if ($IdleEngine) {
        Write-Output 'MOTOR=idle'
    } elseif (Test-Path -LiteralPath $idleFlag) {
        Write-Output 'MOTOR=idle'
    } elseif (-not $SinMotor) {
        $motorArriba = Test-Endpoint 'http://127.0.0.1:8001/health'
        $motorPresente = (Find-Python 'acestep.api_server').Count -gt 0 -or (Test-Port 8001)
        if ($WakeEngine -and $motorPresente) {
            # Si el motor ya responde al health, está despierto: no requiere
            # identidad verificada para usarlo. La identidad solo importa para
            # detener un proceso concreto (stop_local).
            if (-not $motorArriba) {
                $verifiedOwner = Get-VerifiedEngineOwner -ErrorAction SilentlyContinue
                if (-not $verifiedOwner) {
                    Write-Host '[motor] presente sin identidad verificada; se usa tal cual.'
                }
            }
        }

        # -Rearme es el arranque de la app: libera la VRAM y arranca limpio
        # (decisión CLXXIII). Sin -Rearme (vigilante de la ventana cada 20 s
        # o recuperación del backend) se preserva todo motor presente:
        # /health puede tardar mientras carga o genera. Un timeout por sí
        # solo no acredita que esté muerto (regresión del 2026-10-18).
        if ($Rearme -and $motorPresente) {
            Stop-Motor 'liberando-vram'
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
            $backend = Join-Path $raiz 'backend'
            $backendPython = Join-Path $backend 'venv\Scripts\python.exe'
            $engineLaunchLines = & $backendPython -c "import sys,json; sys.path.insert(0, r'$backend'); from config import engine_launch_config; print(json.dumps(engine_launch_config()))"
            if ($LASTEXITCODE -ne 0 -or -not $engineLaunchLines) {
                Write-Output 'MOTOR=python-config-failed'
                exit 1
            }
            try {
                $engineLaunch = ([string](@($engineLaunchLines) | Select-Object -Last 1)) | ConvertFrom-Json -ErrorAction Stop
            } catch {
                Write-Output 'MOTOR=launch-config-invalid'
                exit 1
            }
            $enginePythonConfigured = ([string]$engineLaunch.python_path).Trim()
            if (-not $enginePythonConfigured -or -not $engineLaunch.environment) {
                Write-Output 'MOTOR=launch-config-invalid'
                exit 1
            }
            if (-not [System.IO.Path]::IsPathRooted($enginePythonConfigured)) {
                $enginePythonConfigured = Join-Path $raiz $enginePythonConfigured
            }
            if (-not (Test-Path -LiteralPath $enginePythonConfigured -PathType Leaf)) {
                Write-Output "MOTOR=python-missing path=$enginePythonConfigured"
                exit 1
            }
            & $backendPython (Join-Path $PSScriptRoot 'apply_acestep_patches.py')
            if ($LASTEXITCODE -ne 0) {
                Write-Output 'MOTOR=patch-failed'
                exit 1
            }
            # Modelo, LM, offload y timeout del mismo contrato que la API.
            # El default REST de ACE-Step cargaría Turbo y dejaría el DiT
            # persistente en CUDA incluso cuando el perfil de Musicia es SFT.
            foreach ($setting in $engineLaunch.environment.PSObject.Properties) {
                [Environment]::SetEnvironmentVariable($setting.Name, [string]$setting.Value, 'Process')
            }
            Start-Servicio 'MOTOR' `
                $enginePythonConfigured `
                @('-m', 'acestep.api_server') `
                (Join-Path $raiz 'vendor\ACE-Step-1.5') `
                (Join-Path $logs 'acestep-api.log') `
                (Join-Path $logs 'acestep-api.err.log')
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
        $apiStale = $false
        if ($Rearme -and $apiProcs.Count -gt 0) {
            # Arranque de la app: si el proceso responde pero arrancó antes
            # del último cambio de backend/*.py, sirve código viejo y se
            # reemplaza. El vigilante de la ventana (sin -Rearme) no entra
            # aquí: nunca mata una API en marcha ni trabajos en curso.
            $backend = Join-Path $raiz 'backend'
            $oldest = Get-OldestApiAgeSeconds $apiProcs
            $sourceAge = Get-NewestApiSourceAgeSeconds $backend
            # Sin python de la API no se evalúa ni se reemplaza: ante la duda
            # se conserva el proceso en vez de matarlo sin poder reponerlo.
            if ($null -ne $sourceAge -and (Test-Path -LiteralPath $apiPy -PathType Leaf)) {
                $oldestText = $oldest.ToString([System.Globalization.CultureInfo]::InvariantCulture)
                $sourceAgeText = $sourceAge.ToString([System.Globalization.CultureInfo]::InvariantCulture)
                & $apiPy -c "import sys; sys.path.insert(0, r'$backend'); from api_supervisor import api_is_stale; raise SystemExit(0 if api_is_stale(source_write_age_seconds=float(sys.argv[1]), process_age_seconds=float(sys.argv[2])) else 1)" $sourceAgeText $oldestText
                $apiStale = ($LASTEXITCODE -eq 0)
            }
        }
        if ($apiStale) {
            foreach ($proc in $apiProcs) {
                # Tras el árbol (/T) del padre, el hijo del venv ya murió: no
                # se repite la orden a un PID muerto («ERROR» de taskkill en
                # una operación que sí es correcta).
                if (Get-Process -Id $proc.ProcessId -ErrorAction SilentlyContinue) {
                    & taskkill.exe /PID $proc.ProcessId /T /F | Out-Null
                }
            }
            $apiExitWaitSeconds = 15
            $apiExitPollMs = 300
            $deadline = (Get-Date).AddSeconds($apiExitWaitSeconds)
            do {
                Start-Sleep -Milliseconds $apiExitPollMs
            } while (((Find-Python 'backend\main.py').Count + (Find-Python 'backend/main.py').Count) -gt 0 -and (Get-Date) -lt $deadline)
            Start-Servicio 'API' $apiPy $apiArgs $raiz $apiOut $apiErr
            Write-Output 'API=refreshed'
        } else {
            Write-Output 'API=up'
        }
    } elseif ($apiProcs.Count -gt 0 -and -not $apiPort) {
        # El proceso existe y el puerto no acepta. Si ya pasó la espera, está
        # colgado: se repone solo la API. El motor no se toca.
        $oldest = Get-OldestApiAgeSeconds $apiProcs
        $backend = Join-Path $raiz 'backend'
        $ageText = $oldest.ToString([System.Globalization.CultureInfo]::InvariantCulture)
        & $apiPy -c "import sys; sys.path.insert(0, r'$backend'); from config import get_settings; from api_supervisor import api_is_wedged; raise SystemExit(0 if api_is_wedged(health_ok=False, port_accepts=False, age_seconds=float(sys.argv[1]), grace_seconds=get_settings().api_listen_grace_seconds) else 1)" $ageText
        if ($LASTEXITCODE -eq 0) {
            foreach ($proc in $apiProcs) {
                # Mismo criterio que en la ruta obsoleta: el árbol (/T) ya
                # mató al hijo del venv, no se ordena matar a un PID muerto.
                if (Get-Process -Id $proc.ProcessId -ErrorAction SilentlyContinue) {
                    & taskkill.exe /PID $proc.ProcessId /T /F | Out-Null
                }
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

    if ($motorIniciado -or $WakeEngine) {
        # La API y la UI arrancan mientras ACE-Step carga los modelos. Mantener
        # este supervisor y el mutex activos hasta que /health responda evita
        # que el watchdog mate un motor que todavía está inicializando.
        $limiteMotor = (Get-Date).AddSeconds([Math]::Max(1, $StartTimeoutSeconds))
        $motorListo = $false
        while ((Get-Date) -lt $limiteMotor) {
            if (Test-Path -LiteralPath $flag) {
                Stop-Started-Motor
                Write-Output 'HOLD'
                exit 0
            }
            if (Test-Endpoint 'http://127.0.0.1:8001/health') {
                $motorListo = $true
                break
            }
            Start-Sleep -Seconds 5
        }
        if (Test-Path -LiteralPath $flag) {
            Stop-Started-Motor
            Write-Output 'HOLD'
            exit 0
        }
        if ($motorListo) {
            Remove-Item -LiteralPath $lifecycleErrorFile -Force -ErrorAction SilentlyContinue
            Write-Output 'MOTOR=listo'
        } else {
            Write-Output 'MOTOR=no-responde'
            exit 1
        }
    }
    if ($engineControlError) { exit 1 }
} catch {
    $detalle = ($_ | Out-String).Trim()
    [System.IO.File]::WriteAllText($lifecycleErrorFile, $detalle)
    [Console]::Error.WriteLine($detalle)
    exit 1
} finally {
    if ($owned) { [void]$mutex.ReleaseMutex() }
    $mutex.Dispose()
}
