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

function Test-Port([int]$puerto) {
    $cliente = New-Object System.Net.Sockets.TcpClient
    try {
        $espera = $cliente.BeginConnect('127.0.0.1', $puerto, $null, $null)
        if (-not $espera.AsyncWaitHandle.WaitOne(400)) { return $false }
        $cliente.EndConnect($espera)
        return $true
    } catch {
        return $false
    } finally {
        $cliente.Close()
    }
}

Write-Host "== 1/5 motor ACE-Step =="
if (-not (Test-Endpoint 'http://127.0.0.1:8001/health')) {
    # El motor se arranca por la ruta del producto (ensure_local.ps1): él aplica
    # los parches, resuelve la configuración y escribe la identidad del motor en
    # logs\engine.pid.json, que R18 necesita para poder pausarlo al terminar.
    # Un Start-Process directo deja un motor "ajeno" que IdleEngine preserva por
    # diseño (incidente 2026-10-20 13:15:50: fase 2 del e2e no alcanzada).
    # Si responde MOTOR=idle (flag de reposo R18) el motor NO se arranca aquí:
    # la primera peticion lo despierta sola, igual que en la app real.
    Remove-Item (Join-Path $logs 'stop.flag') -Force -ErrorAction SilentlyContinue
    & (Join-Path $PSScriptRoot 'ensure_local.ps1')
}
$limite = (Get-Date).AddMinutes(4)
while (-not (Test-Endpoint 'http://127.0.0.1:8001/health') -and (Get-Date) -lt $limite) { Start-Sleep -Seconds 5 }
$resultado.motor_ok = Test-Endpoint 'http://127.0.0.1:8001/health'
Write-Host "   motor responde: $($resultado.motor_ok) (False con reposo R18 no corta: lo despierta la peticion)"

Write-Host "== 2/5 API Musicia =="
if (-not (Test-Endpoint 'http://127.0.0.1:8000/health')) {
    # La API también se arranca por la ruta del producto (mismo motivo arriba).
    Remove-Item (Join-Path $logs 'stop.flag') -Force -ErrorAction SilentlyContinue
    & (Join-Path $PSScriptRoot 'ensure_local.ps1')
}
$limite = (Get-Date).AddSeconds(90)
while (-not (Test-Endpoint 'http://127.0.0.1:8000/health') -and (Get-Date) -lt $limite) { Start-Sleep -Seconds 3 }
$resultado.api_ok = Test-Endpoint 'http://127.0.0.1:8000/health'
Write-Host "   api responde: $($resultado.api_ok)"
if (-not $resultado.api_ok) { $resultado | ConvertTo-Json | Set-Content (Join-Path $logs 'e2e-result.json'); exit 1 }

Write-Host "== 3/5 generando musica ($Seconds s) =="
$cuerpo = @{ prompt = $Prompt; duration_seconds = $Seconds; instrumental = $true } | ConvertTo-Json
# 900 s: si el motor está en reposo, esta misma peticion lo despierta (R18) y
# arranca en frío antes de encolar; el plazo del cliente no debe cortar esa
# espera (la UI usa GENERATE_SUBMIT_TIMEOUT_MS = 960 s).
$peticion = Invoke-RestMethod -Uri 'http://127.0.0.1:8000/music/generate' -Method Post -Body $cuerpo -ContentType 'application/json' -TimeoutSec 900
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
# Con reposo R18 el motor despierta durante la peticion: si el trabajo corrió,
# el motor respondió y el dato del paso 1 pasa a reflejarlo.
if ($estado.status -in @('queued', 'running', 'succeeded')) {
    $resultado.motor_ok = $resultado.motor_ok -or (Test-Endpoint 'http://127.0.0.1:8001/health')
}
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
