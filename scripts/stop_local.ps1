<#
Detiene los procesos locales de Musicia (motor ACE-Step y API) y espera
a que suelten los puertos. taskkill /T mata el árbol: Stop-Process del
padre dejaba al hijo de uv escuchando en el 8001.

No casa con un main.py suelto: ComfyUI también se llama así.
No borra logs/stop.flag y no arranca nada.
#>
$ErrorActionPreference = 'SilentlyContinue'
. (Join-Path $PSScriptRoot 'engine_identity.ps1')

function Test-MusiciaCommandLine {
    param($Line)
    if (-not $Line) { return $false }
    if ($Line -like '*backend\main.py*') { return $true }
    if ($Line -like '*backend/main.py*') { return $true }
    return $false
}

function Get-MusiciaProcess {
    Get-CimInstance Win32_Process | Where-Object {
        $nombre = $_.Name
        if ($nombre -ne 'python.exe' -and $nombre -ne 'pythonw.exe' -and $nombre -ne 'uv.exe') {
            return $false
        }
        Test-MusiciaCommandLine $_.CommandLine
    }
}

function Stop-MusiciaTree {
    param($TargetId)
    & taskkill.exe /F /T /PID $TargetId | Out-Null
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
        Remove-Item -LiteralPath $ownerFile -Force
        if (@(Get-NetTCPConnection -LocalPort 8001 -State Listen -ErrorAction SilentlyContinue).Count -gt 0) {
            Write-Host '[ACE-Step] PID ausente y puerto ocupado; proceso preservado'
            return $false
        }
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
        Stop-Process -Id $enginePid -Force -ErrorAction Stop
    } catch {
        Write-Host "[ACE-Step] no se pudo detener el PID verificado $enginePid"
        return $false
    }
    $deadline = (Get-Date).AddSeconds(15)
    do {
        Start-Sleep -Milliseconds 250
        $remaining = Get-CimInstance Win32_Process -Filter "ProcessId = $enginePid" -ErrorAction SilentlyContinue
    } while ($remaining -and $remaining.CreationDate -eq $process.CreationDate -and (Get-Date) -lt $deadline)
    if ($remaining -and $remaining.CreationDate -eq $process.CreationDate) {
        Write-Host "[ACE-Step] tiempo agotado para el PID $enginePid"
        return $false
    }
    Remove-Item -LiteralPath $ownerFile -Force
    if (@(Get-NetTCPConnection -LocalPort 8001 -State Listen -ErrorAction SilentlyContinue).Count -gt 0) {
        Write-Host '[ACE-Step] puerto 8001 sigue ocupado; no se detiene otro proceso'
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
        Stop-MusiciaTree -TargetId $idProc
        Write-Host "[$etiqueta] detenido (PID $idProc)"
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
        Stop-MusiciaTree -TargetId ([int]$proceso.ProcessId)
    }
    $siguenEscuchando = @()
    $conexiones = @(Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue)
    foreach ($conexion in $conexiones) {
        $duenoId = [int]$conexion.OwningProcess
        $dueno = Get-CimInstance Win32_Process -Filter "ProcessId = $duenoId"
        if ($dueno -and (Test-MusiciaCommandLine $dueno.CommandLine)) {
            $siguenEscuchando += $dueno
            Stop-MusiciaTree -TargetId $duenoId
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
Write-Host '[Musicia] puertos libres'
exit 0
