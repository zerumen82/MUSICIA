param(
    [Parameter(Mandatory=$true)][string]$Manifest,
    [Parameter(Mandatory=$true)][string]$OutputDirectory,
    [string]$Api = 'http://127.0.0.1:8000'
)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
if (([uri]$Api).Host -notin @('127.0.0.1','localhost')) { throw 'Local API required' }
if (Test-Path -LiteralPath (Join-Path $projectRoot 'logs\stop.flag')) { throw 'Musicia stopped; no probe' }
$jobs = Invoke-RestMethod -Uri ($Api + '/music/jobs') -TimeoutSec 10
if (@($jobs.items | Where-Object { $_.status -in @('queued','running') }).Count) { throw 'Active job; probe will not start' }
$caps = Invoke-RestMethod -Uri ($Api + '/music/remix/capabilities') -TimeoutSec 10
if (-not $caps.timeline) { throw 'R11 backend not deployed; no probe' }
$null = New-Item -ItemType Directory -Path $OutputDirectory -Force
if (Test-Path -LiteralPath (Join-Path $OutputDirectory 'result.json')) { throw 'Output directory has terminal evidence; use a fresh directory' }
$backendPython = Join-Path $projectRoot 'backend\venv\Scripts\python.exe'
Push-Location $projectRoot
try { $timeoutSeconds = & $backendPython -c "import sys;sys.path.insert(0,'backend');from config import get_settings;print(get_settings().acestep.job_timeout)" }
finally { Pop-Location }
if ($LASTEXITCODE -ne 0) { throw 'Could not read configured timeout' }
$env:MUSICIA_R11_MANIFEST = (Resolve-Path -LiteralPath $Manifest).Path
$env:MUSICIA_R11_OUTPUT = (Resolve-Path -LiteralPath $OutputDirectory).Path
$env:MUSICIA_API_URL = $Api
$env:MUSICIA_PROBE_TIMEOUT_MS = [string]([int]([double]$timeoutSeconds * 1000))
$ui = Start-Process -FilePath (Join-Path $projectRoot 'frontend\node_modules\electron\dist\electron.exe') -ArgumentList @((Join-Path $PSScriptRoot 'probe_remix_timeline_ui.cjs')) -WorkingDirectory $projectRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $OutputDirectory 'ui.stdout.log') -RedirectStandardError (Join-Path $OutputDirectory 'ui.stderr.log') -PassThru
$limit = (Get-Date).AddSeconds([double]$timeoutSeconds)
$resultFile = Join-Path $OutputDirectory 'result.json'
do {
    if (Test-Path -LiteralPath $resultFile) { break }
    if ($ui.HasExited) { throw 'Electron exited before terminal evidence' }
    Start-Sleep -Milliseconds 500
} while ((Get-Date) -lt $limit)
if (-not (Test-Path -LiteralPath $resultFile)) { throw 'Probe timeout; process/jobs left untouched' }
if (-not $ui.WaitForExit(10000)) { throw 'Terminal evidence exists but GUI process has not exited' }
$result = Get-Content -LiteralPath $resultFile -Raw | ConvertFrom-Json
@{process_id=$ui.Id;exit_code=$ui.ExitCode;result_file=$resultFile;status=$result.status} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $OutputDirectory 'process.json') -Encoding utf8
if ($ui.ExitCode -ne 0 -or $result.status -ne 'PASS') { throw "R11 UI FAIL: $($result.error)" }
foreach ($size in @('1400x900','1080x700')) {
    if (@($result.steps | Where-Object { $_.label -eq "Layout $size" }).Count -eq 0) { throw "Missing layout $size" }
}
& $backendPython (Join-Path $PSScriptRoot 'probe_remix_timeline.py') verify-ui --api $Api --ui-result $resultFile --report (Join-Path $OutputDirectory 'audio-evidence.json')
if ($LASTEXITCODE -ne 0) { throw 'R11 audio/API evidence failed' }
Write-Output "R11_UI_AUDIO=PASS EVIDENCE=$OutputDirectory"
