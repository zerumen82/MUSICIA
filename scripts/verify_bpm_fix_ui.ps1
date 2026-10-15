param(
    [Parameter(Mandatory=$true)][string]$Manifest,
    [Parameter(Mandatory=$true)][string]$OutputDirectory,
    [string]$Api = 'http://127.0.0.1:8000',
    [switch]$Full,
    [Nullable[long]]$Seed
)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
if (([uri]$Api).Host -notin @('127.0.0.1','localhost')) { throw 'Local API required' }
if (Test-Path -LiteralPath (Join-Path $projectRoot 'logs\stop.flag')) { throw 'Musicia stopped; no probe' }
$jobs = Invoke-RestMethod -Uri ($Api + '/music/jobs') -TimeoutSec 10
if (@($jobs.items | Where-Object { $_.status -in @('queued','running') }).Count) { throw 'Active job; probe will not start' }
$source = Get-Content -LiteralPath $Manifest -Raw | ConvertFrom-Json
$previewBody = @{source_name=$source.source_name;source_kind=$source.source_kind;scope='full';prompt='A track with gabber';bpm=$source.bpm} | ConvertTo-Json
$preview = Invoke-RestMethod -Uri ($Api + '/music/remix/preview') -Method Post -ContentType 'application/json' -Body $previewBody -TimeoutSec 30
if ($preview.operations.timeline.tempo_method -ne 'measured_pcm_atempo' -or $preview.operations.timeline.status -ne 'pending_generated_audio') { throw 'B6 backend not deployed; no probe' }
$null = New-Item -ItemType Directory -Path $OutputDirectory -Force
if (Test-Path -LiteralPath (Join-Path $OutputDirectory 'result.json')) { throw 'Existing terminal evidence; use a fresh directory' }
$backendPython = Join-Path $projectRoot 'backend\venv\Scripts\python.exe'
Push-Location $projectRoot
try { $timeoutSeconds = & $backendPython -c "import sys;sys.path.insert(0,'backend');from config import get_settings;print(get_settings().acestep.job_timeout)" }
finally { Pop-Location }
if ($LASTEXITCODE -ne 0) { throw 'Could not read configured timeout' }
$env:MUSICIA_B6_MANIFEST = (Resolve-Path -LiteralPath $Manifest).Path
$env:MUSICIA_B6_OUTPUT = (Resolve-Path -LiteralPath $OutputDirectory).Path
$env:MUSICIA_B6_FULL_VERIFY = if ($Full) { '1' } else { '0' }
$env:MUSICIA_B6_SEED = if ($null -ne $Seed) { [string]$Seed } else { $null }
$env:MUSICIA_API_URL = $Api
$env:MUSICIA_PROBE_TIMEOUT_MS = [string]([int]([double]$timeoutSeconds * 1000))
$ui = Start-Process -FilePath (Join-Path $projectRoot 'frontend\node_modules\electron\dist\electron.exe') -ArgumentList @((Join-Path $PSScriptRoot 'probe_bpm_fix_ui.cjs')) -WorkingDirectory $projectRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $OutputDirectory 'ui.stdout.log') -RedirectStandardError (Join-Path $OutputDirectory 'ui.stderr.log') -PassThru
# Acquire the handle while the process is alive; Start-Process otherwise can
# release it before ExitCode is read after a short-lived Electron run.
$null = $ui.Handle
$limit = (Get-Date).AddSeconds([double]$timeoutSeconds)
$resultFile = Join-Path $OutputDirectory 'result.json'
do {
    if (Test-Path -LiteralPath $resultFile) { break }
    if ($ui.HasExited) { throw 'Electron exited before terminal evidence' }
    Start-Sleep -Milliseconds 500
} while ((Get-Date) -lt $limit)
if (-not (Test-Path -LiteralPath $resultFile)) { throw 'Probe timeout; process/jobs left untouched' }
if (-not $ui.WaitForExit(10000)) { throw 'Terminal evidence exists but probe has not exited' }
$ui.Refresh()
$result = Get-Content -LiteralPath $resultFile -Raw | ConvertFrom-Json
@{process_id=$ui.Id;exit_code=$ui.ExitCode;result_file=$resultFile;status=$result.status} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $OutputDirectory 'process.json') -Encoding utf8
if ($ui.ExitCode -ne 0 -or $result.status -ne 'PASS') { throw "B6 UI FAIL: $($result.error)" }
foreach ($scope in @('groups','full')) {
    foreach ($size in @('1400x900','1080x700')) {
        if (@($result.steps | Where-Object { $_.label -eq "Layout $scope $size" }).Count -eq 0) { throw "Missing layout $scope $size" }
    }
}
& $backendPython (Join-Path $PSScriptRoot 'probe_bpm_fix.py') verify --api $Api --existing-report $resultFile --report (Join-Path $OutputDirectory 'audio-evidence.json')
if ($LASTEXITCODE -ne 0) { throw 'B6 audio/API evidence failed' }
if ($Full) {
    & $backendPython (Join-Path $PSScriptRoot 'probe_bpm_fix.py') verify --full-ui --api $Api --existing-report $resultFile --report (Join-Path $OutputDirectory 'full-audio-evidence.json')
    if ($LASTEXITCODE -ne 0) { throw 'B6 full audio/API evidence failed' }
}
Write-Output "B6_UI_AUDIO=PASS EVIDENCE=$OutputDirectory"
