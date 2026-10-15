<# Real layout/DSP verifier with owned GUI process and terminal result oracle. #>
param(
    [Parameter(Mandatory=$true)][string]$Source,
    [Parameter(Mandatory=$true)][string]$OutputDirectory,
    [string]$Api = 'http://127.0.0.1:8000'
)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$backendPython = Join-Path $projectRoot 'backend\venv\Scripts\python.exe'
Push-Location $projectRoot
try { $timeoutSeconds = & $backendPython -c "import sys; sys.path.insert(0,'backend'); from config import get_settings; print(get_settings().acestep.job_timeout)" }
finally { Pop-Location }
if ($LASTEXITCODE -ne 0) { throw 'Layout timeout configuration could not be read' }
$oldDirectories = @(Get-ChildItem -LiteralPath (Join-Path $projectRoot 'logs') -Directory -Filter 'plan-completion-ui-layout-*' | Select-Object -ExpandProperty FullName)
$env:MUSICIA_PROBE_MODE = 'layout'
$env:MUSICIA_PROBE_SOURCE = $Source
$env:MUSICIA_API_URL = $Api
$env:MUSICIA_PROBE_TIMEOUT_MS = [string]([int]([double]$timeoutSeconds * 1000))
$ui = Start-Process -FilePath (Join-Path $projectRoot 'frontend\node_modules\electron\dist\electron.exe') -ArgumentList @((Join-Path $PSScriptRoot 'probe_plan_completion_ui.cjs'),'.') -WorkingDirectory $projectRoot -RedirectStandardOutput (Join-Path $OutputDirectory 'layout-ui.stdout.log') -RedirectStandardError (Join-Path $OutputDirectory 'layout-ui.stderr.log') -WindowStyle Hidden -PassThru
$limit = (Get-Date).AddSeconds([double]$timeoutSeconds)
$resultPath = $null
do {
    $newDirectories = @(Get-ChildItem -LiteralPath (Join-Path $projectRoot 'logs') -Directory -Filter 'plan-completion-ui-layout-*' | Where-Object { $_.FullName -notin $oldDirectories })
    if ($newDirectories.Count -gt 1) { throw 'More than one new layout verifier; result cannot be attributed uniquely' }
    if ($newDirectories.Count -eq 1) {
        $candidate = Join-Path $newDirectories[0].FullName 'result.json'
        if (Test-Path -LiteralPath $candidate) { $resultPath = $candidate; break }
    }
    if ($ui.HasExited) { throw 'Layout Electron exited without terminal result evidence' }
    Start-Sleep -Milliseconds 500
} while ((Get-Date) -lt $limit)
if (-not $resultPath) { throw 'Layout timeout; own GUI process left untouched' }
if (-not $ui.WaitForExit(10000)) { throw 'Layout recorded result but process has not exited' }
$result = Get-Content -LiteralPath $resultPath -Raw | ConvertFrom-Json
@{ process_id=$ui.Id; exit_code=$ui.ExitCode; result_file=$resultPath; result=$result } |
    ConvertTo-Json -Depth 40 | Set-Content -LiteralPath (Join-Path $OutputDirectory 'layout-verified.json') -Encoding utf8
if ($ui.ExitCode -ne 0 -or $result.status -ne 'PASS') { throw "Layout failed: $($result.error)" }
foreach ($size in @('1400x900','1080x700')) {
    if (@($result.steps | Where-Object { $_.label -like "*$size*" }).Count -eq 0) { throw "Missing real screenshot/layout evidence at $size" }
}
if (-not $result.adjustment_busy -or -not $result.adjustment_audio) { throw 'Missing live DSP busy/recovery evidence' }
Write-Output "LAYOUT=PASS EVIDENCE=$resultPath"
