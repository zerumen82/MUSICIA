<#
Detiene los procesos locales de Musicia (motor ACE-Step y API) y espera
a que suelten los puertos. taskkill /T mata el árbol: Stop-Process del
padre dejaba al hijo de uv escuchando en el 8001.

No casa con un main.py suelto: ComfyUI también se llama así.
No borra logs/stop.flag y no arranca nada.
#>
$ErrorActionPreference = 'SilentlyContinue'

function Test-MusiciaCommandLine {
    param($Line)
    if (-not $Line) { return $false }
    if ($Line -like '*backend\main.py*') { return $true }
    if ($Line -like '*backend/main.py*') { return $true }
    if ($Line -like '*acestep.api_server*') { return $true }
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

$iniciales = @(Get-MusiciaProcess)
$etiquetas = @{}
if ($iniciales.Count -eq 0) {
    Write-Host '[Musicia API] no estaba corriendo'
    Write-Host '[ACE-Step] no estaba corriendo'
} else {
    foreach ($proceso in $iniciales) {
        $idProc = [int]$proceso.ProcessId
        $linea = [string]$proceso.CommandLine
        if ($linea -like '*acestep.api_server*') {
            $etiqueta = 'ACE-Step'
        } else {
            $etiqueta = 'Musicia API'
        }
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
    $conexiones = @(Get-NetTCPConnection -LocalPort 8000,8001 -State Listen -ErrorAction SilentlyContinue)
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
Write-Host '[Musicia] puertos libres'
exit 0
