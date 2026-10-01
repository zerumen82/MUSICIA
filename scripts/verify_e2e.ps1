<#
Prueba de humo end-to-end: arranca motor + API, genera música de verdad y
verifica el archivo resultante (existe, no está vacío y dura lo pedido).

Uso:  powershell -ExecutionPolicy Bypass -File scripts\verify_e2e.ps1 -Seconds 30

Deja el resultado en logs\e2e-result.json.
#>
param(
    [int]$Seconds = 30,
    [string]$Prompt = 'synthwave nocturno, bajo analogico, bombo lento',
    [int]$EsperaMinutos = 8
)

$ErrorActionPreference = 'Continue'
$raiz = Split-Path -Parent $PSScriptRoot
$logs = Join-Path $raiz 'logs'
New-Item -ItemType Directory -Force -Path $logs | Out-Null
$resultado = [ordered]@{
    iniciado_en = (Get-Date).ToString('s')
    peticion = @{ prompt = $Prompt; duracion_s = $Seconds }
    motor_ok = $false
    api_ok = $false
    job_id = $null
    estado = $null
    duracion_real_s = $null
    archivo = $null
    bytes = $null
    correcto = $false
}

function Test-Endpoint([string]$url) {
    try { $null = Invoke-WebRequest -Uri $url -TimeoutSec 5 -UseBasicParsing; return $true }
    catch { return $false }
}

Write-Host "== 1/5 motor ACE-Step =="
if (-not (Test-Endpoint 'http://127.0.0.1:8001/health')) {
    Start-Process -FilePath (Join-Path $raiz 'vendor\ACE-Step-1.5\.venv\Scripts\python.exe') `
        -ArgumentList '-m', 'acestep.api_server' `
        -WorkingDirectory (Join-Path $raiz 'vendor\ACE-Step-1.5') `
        -RedirectStandardOutput (Join-Path $logs 'acestep-api.log') `
        -RedirectStandardError (Join-Path $logs 'acestep-api.err.log') `
        -WindowStyle Hidden | Out-Null
}
$limite = (Get-Date).AddMinutes(4)
while (-not (Test-Endpoint 'http://127.0.0.1:8001/health') -and (Get-Date) -lt $limite) { Start-Sleep -Seconds 5 }
$resultado.motor_ok = Test-Endpoint 'http://127.0.0.1:8001/health'
Write-Host "   motor responde: $($resultado.motor_ok)"
if (-not $resultado.motor_ok) { $resultado | ConvertTo-Json | Set-Content (Join-Path $logs 'e2e-result.json'); exit 1 }

Write-Host "== 2/5 API Musicia =="
if (-not (Test-Endpoint 'http://127.0.0.1:8000/health')) {
    Start-Process -FilePath (Join-Path $raiz 'backend\venv\Scripts\python.exe') `
        -ArgumentList 'backend\main.py' `
        -WorkingDirectory $raiz `
        -RedirectStandardOutput (Join-Path $logs 'musicia-api.log') `
        -RedirectStandardError (Join-Path $logs 'musicia-api.err.log') `
        -WindowStyle Hidden | Out-Null
}
$limite = (Get-Date).AddSeconds(60)
while (-not (Test-Endpoint 'http://127.0.0.1:8000/health') -and (Get-Date) -lt $limite) { Start-Sleep -Seconds 3 }
$resultado.api_ok = Test-Endpoint 'http://127.0.0.1:8000/health'
Write-Host "   api responde: $($resultado.api_ok)"
if (-not $resultado.api_ok) { $resultado | ConvertTo-Json | Set-Content (Join-Path $logs 'e2e-result.json'); exit 1 }

Write-Host "== 3/5 generando musica ($Seconds s) =="
$cuerpo = @{ prompt = $Prompt; duration_seconds = $Seconds; instrumental = $true } | ConvertTo-Json
$peticion = Invoke-RestMethod -Uri 'http://127.0.0.1:8000/music/generate' -Method Post -Body $cuerpo -ContentType 'application/json' -TimeoutSec 60
$resultado.job_id = $peticion.job_id
Write-Host "   job: $($peticion.job_id) (tarea motor $($peticion.engine_task_id))"

Write-Host "== 4/5 siguiendo el progreso =="
$limite = (Get-Date).AddMinutes($EsperaMinutos)
do {
    Start-Sleep -Seconds 15
    $estado = Invoke-RestMethod -Uri "http://127.0.0.1:8000/music/status/$($peticion.job_id)" -TimeoutSec 20
    $marca = Get-Date -Format 'HH:mm:ss'
    if ($estado.progress) { Write-Host "   [$marca] $($estado.status) - $($estado.progress)" }
    else { Write-Host "   [$marca] $($estado.status)" }
} while ($estado.status -in @('queued', 'running') -and (Get-Date) -lt $limite)

$resultado.estado = $estado.status
if ($estado.error) { Write-Host "   ERROR: $($estado.error)" }
if ($estado.output_name) { $resultado.archivo = $estado.output_name }
if ($estado.duration_seconds) { $resultado.duracion_real_s = $estado.duration_seconds }

Write-Host "== 5/5 verificando el archivo =="
if ($estado.status -eq 'succeeded' -and $estado.output_name) {
    $ruta = Join-Path $raiz "backend\outputs\$($estado.output_name)"
    if (Test-Path $ruta) {
        $resultado.bytes = (Get-Item $ruta).Length
        $ffprobe = Get-Command ffprobe -ErrorAction SilentlyContinue
        if ($ffprobe) {
            $salida = & ffprobe -v error -show_entries format=duration -of csv=p=0 $ruta 2>$null
            if ($salida) { $resultado.duracion_real_s = [math]::Round([double]$salida, 2) }
        }
        $resultado.correcto = ($resultado.bytes -gt 0) -and ($resultado.duracion_real_s -ge ($Seconds * 0.8))
        Write-Host "   archivo: $($resultado.bytes) bytes | duracion: $($resultado.duracion_real_s) s"
        Write-Host "   CORRECTO: $($resultado.correcto)"
    } else {
        Write-Host "   el backend no dejo el archivo en outputs\"
    }
}

$resultado | ConvertTo-Json | Set-Content (Join-Path $logs 'e2e-result.json')
Write-Host "resultado guardado en logs\e2e-result.json"