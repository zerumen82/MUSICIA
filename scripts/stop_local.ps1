<#
Detiene los procesos identificados como propios de Musicia. El motor acredita
launcher e intérprete y los detiene individualmente; la API revalida su script
absoluto, PID, fecha, comando y ejecutable antes de taskkill /T.

No casa con un main.py suelto: ComfyUI también se llama así.
No borra logs/stop.flag y no arranca nada.
#>
$ErrorActionPreference = 'SilentlyContinue'
. (Join-Path $PSScriptRoot 'engine_identity.ps1')
. (Join-Path $PSScriptRoot 'api_identity.ps1')
$musiciaRoot = Split-Path -Parent $PSScriptRoot
$script:apiStopFailed = $false

function Test-MusiciaCommandLine {
    param($Line)
    return Test-MusiciaApiCommandLine $Line $musiciaRoot
}

function Get-MusiciaProcess {
    Get-CimInstance Win32_Process | Where-Object {
        $nombre = $_.Name
        if ($nombre -ne 'python.exe' -and $nombre -ne 'pythonw.exe') {
            return $false
        }
        Test-MusiciaApiProcess $_ $musiciaRoot
    }
}

function Stop-MusiciaTree {
    param($ProcessSnapshot)
    if (-not (Test-MusiciaApiProcess $ProcessSnapshot $musiciaRoot)) {
        $script:apiStopFailed = $true
        return $false
    }
    $targetId = [int]$ProcessSnapshot.ProcessId
    try {
        $actual = Get-CimInstance Win32_Process -Filter "ProcessId = $targetId" -ErrorAction Stop
    } catch {
        $script:apiStopFailed = $true
        Write-Host "[Musicia API] no se pudo verificar PID $targetId; proceso preservado"
        return $false
    }
    if (-not $actual) { return $true }
    if (-not (Test-MusiciaApiProcessSnapshot $ProcessSnapshot $actual $musiciaRoot)) {
        $script:apiStopFailed = $true
        Write-Host "[Musicia API] identidad del PID $targetId no acreditada; proceso preservado"
        return $false
    }
    & taskkill.exe /F /T /PID $targetId | Out-Null
    if ($LASTEXITCODE -ne 0) {
        $script:apiStopFailed = $true
        return $false
    }
    return $true
}

function Stop-OwnedEngine {
    $root = Split-Path -Parent $PSScriptRoot
    $ownerFile = Join-Path $root 'logs\engine.pid.json'
    if (-not (Test-Path -LiteralPath $ownerFile -PathType Leaf)) {
        $engineProcesses = @(Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" |
            Where-Object { $_.CommandLine -like '*-m acestep.api_server*' })
        $enginePort = @(Get-NetTCPConnection -LocalPort 8001 -State Listen -ErrorAction SilentlyContinue)
        if ($engineProcesses.Count -gt 0 -or $enginePort.Count -gt 0) {
            Write-Host '[ACE-Step] identidad no verificada; proceso preservado'
            return $false
        }
        Write-Host '[ACE-Step] no estaba corriendo'
        return $true
    }
    try {
        $owner = Get-Content -LiteralPath $ownerFile -Raw | ConvertFrom-Json -ErrorAction Stop
        $enginePid = [int]$owner.pid
    } catch {
        Write-Host '[ACE-Step] registro de propiedad ilegible; proceso preservado'
        return $false
    }
    if ($enginePid -le 0 -or -not $owner.creation_date -or -not $owner.executable_path -or -not $owner.command_line) {
        Write-Host '[ACE-Step] registro de propiedad incompleto; proceso preservado'
        return $false
    }
    $process = Get-CimInstance Win32_Process -Filter "ProcessId = $enginePid" -ErrorAction SilentlyContinue
    if (-not $process) {
        $engineProcesses = @(Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" |
            Where-Object { $_.CommandLine -like '*-m acestep.api_server*' })
        if ($engineProcesses.Count -gt 0 -or
            @(Get-NetTCPConnection -LocalPort 8001 -State Listen -ErrorAction SilentlyContinue).Count -gt 0) {
            Write-Host '[ACE-Step] PID ausente y motor/puerto presente; registro preservado'
            return $false
        }
        Remove-Item -LiteralPath $ownerFile -Force -ErrorAction Stop
        Write-Host '[ACE-Step] PID registrado ya terminó'
        return $true
    }
    if (-not (Test-EngineCreationDate $owner.creation_date $process.CreationDate) -or
        -not [string]::Equals([string]$process.ExecutablePath, [string]$owner.executable_path,
            [StringComparison]::OrdinalIgnoreCase) -or
        [string]$process.CommandLine -ne [string]$owner.command_line -or
        [string]$process.CommandLine -notlike '*-m acestep.api_server*') {
        Write-Host "[ACE-Step] identidad del PID $enginePid no coincide; proceso preservado"
        return $false
    }
    try {
        Stop-VerifiedEngineProcesses -RootProcess $process -TimeoutSeconds 15 -PortOpen {
            @(Get-NetTCPConnection -LocalPort 8001 -State Listen -ErrorAction SilentlyContinue).Count -gt 0
        }
        Remove-Item -LiteralPath $ownerFile -Force -ErrorAction Stop
    } catch {
        Write-Host "[ACE-Step] $($_.Exception.Message)"
        return $false
    }
    Write-Host "[ACE-Step] detenido (PID $enginePid)"
    return $true
}

$engineStopped = Stop-OwnedEngine
$iniciales = @(Get-MusiciaProcess)
$etiquetas = @{}
if ($iniciales.Count -eq 0) {
    Write-Host '[Musicia API] no estaba corriendo'
    Write-Host '[ACE-Step] no estaba corriendo'
} else {
    foreach ($proceso in $iniciales) {
        $idProc = [int]$proceso.ProcessId
        $linea = [string]$proceso.CommandLine
        $etiqueta = 'Musicia API'
        $etiquetas[$etiqueta] = $true
        if (Stop-MusiciaTree -ProcessSnapshot $proceso) {
            Write-Host "[$etiqueta] detenido (PID $idProc)"
        }
    }
    if (-not $etiquetas.ContainsKey('Musicia API')) {
        Write-Host '[Musicia API] no estaba corriendo'
    }
    if (-not $etiquetas.ContainsKey('ACE-Step')) {
        Write-Host '[ACE-Step] no estaba corriendo'
    }
}

$limite = (Get-Date).AddSeconds(12)
do {
    $vivos = @(Get-MusiciaProcess)
    foreach ($proceso in $vivos) {
        $null = Stop-MusiciaTree -ProcessSnapshot $proceso
    }
    $siguenEscuchando = @()
    $conexiones = @(Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue)
    foreach ($conexion in $conexiones) {
        $duenoId = [int]$conexion.OwningProcess
        $dueno = Get-CimInstance Win32_Process -Filter "ProcessId = $duenoId"
        if ($dueno -and (Test-MusiciaApiProcess $dueno $musiciaRoot)) {
            $siguenEscuchando += $dueno
            $null = Stop-MusiciaTree -ProcessSnapshot $dueno
        }
    }
    if ($vivos.Count -eq 0 -and $siguenEscuchando.Count -eq 0) { break }
    Start-Sleep -Milliseconds 400
} while ((Get-Date) -lt $limite)

$quedan = @(Get-MusiciaProcess)
if ($quedan.Count -gt 0) {
    foreach ($proceso in $quedan) {
        Write-Host "[Musicia] sigue vivo (PID $($proceso.ProcessId))"
    }
    exit 1
}
if (-not $engineStopped) { exit 1 }
if ($script:apiStopFailed) {
    Write-Host '[Musicia API] parada no acreditada por completo; procesos dudosos preservados'
    exit 1
}
Write-Host '[Musicia] procesos propios detenidos'
exit 0
