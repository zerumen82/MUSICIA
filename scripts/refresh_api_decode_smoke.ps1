<# Restart only Musicia API after completed verification; preserve motor/apps. #>
param(
    [Parameter(Mandatory=$true)][string]$CompletedEvidence,
    [Parameter(Mandatory=$true)][string]$OutputDirectory,
    [string]$VerifiedLayoutEvidence,
    [switch]$RefreshOnly,
    [string]$Api = 'http://127.0.0.1:8000'
)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
if (([uri]$Api).Host -notin @('127.0.0.1','localhost')) { throw 'Local API required' }
$completed = Get-Content -LiteralPath $CompletedEvidence -Raw | ConvertFrom-Json
if ($VerifiedLayoutEvidence) {
    $layout = Get-Content -LiteralPath $VerifiedLayoutEvidence -Raw | ConvertFrom-Json
} else { $layout = $completed.layoutVerified }
if ($completed.decode_ui.status -ne 'PASS' -or
    @($completed.checks | Where-Object { $_.name -eq 'decode-http-audio' -and $_.exit_code -eq 0 }).Count -ne 1 -or
    $layout.result.status -ne 'PASS' -or $layout.exit_code -ne 0) { throw 'Original decode and independently checked layout must finish successfully before API refresh' }
if (Test-Path -LiteralPath (Join-Path $projectRoot 'logs\stop.flag')) { throw 'Musicia was stopped; no automatic API refresh' }
function Guard-Idle {
    $jobs = Invoke-RestMethod -Uri ($Api + '/music/jobs') -TimeoutSec 10
    if (@($jobs.items | Where-Object { $_.status -in @('queued','running') }).Count -gt 0) { throw 'Active Musicia job; API was left untouched' }
    # Current API log retains every analysis polled by the real UI windows.
    # Query their actual terminal states rather than assuming window closure
    # cancels a model operation.
    $apiLog = Get-Content -LiteralPath (Join-Path $projectRoot 'logs\musicia-api.log') -Raw
    $analysisIds = @([regex]::Matches($apiLog,'/music/remix/analyze/([a-f0-9]{32})') |
        ForEach-Object { $_.Groups[1].Value } | Sort-Object -Unique)
    if ($analysisIds.Count -eq 0) { throw 'No live analysis IDs found in API log; idle analysis cannot be verified' }
    foreach ($analysisId in $analysisIds) {
        $analysis = Invoke-RestMethod -Uri ($Api + '/music/remix/analyze/' + $analysisId) -TimeoutSec 10
        if ($analysis.status -in @('queued','running')) { throw 'Source analysis still active; API was left untouched' }
    }
    return @{ jobs=$jobs; analysis_ids=$analysisIds }
}
$idle = Guard-Idle
$port = ([uri]$Api).Port
$listeners = @(Get-NetTCPConnection -State Listen -LocalPort $port | Select-Object -ExpandProperty OwningProcess -Unique)
if ($listeners.Count -ne 1) { throw 'API listener PID is not unique' }
$apiPid = [int]$listeners[0]
$owner = Get-CimInstance Win32_Process -Filter "ProcessId = $apiPid"
$launcher = if ($owner) { Get-CimInstance Win32_Process -Filter "ProcessId = $($owner.ParentProcessId)" }
$expectedPython = Join-Path $projectRoot 'backend\venv\Scripts\python.exe'
$ownedLauncher = $launcher -and $launcher.Name -eq 'python.exe' -and
    $launcher.CommandLine -match 'backend[\\/]main\.py' -and
    $launcher.CommandLine.IndexOf($expectedPython,[StringComparison]::OrdinalIgnoreCase) -ge 0
$ownerHasRoot = $owner -and $owner.CommandLine.IndexOf($projectRoot,[StringComparison]::OrdinalIgnoreCase) -ge 0
if (-not $owner -or $owner.Name -ne 'python.exe' -or
    $owner.CommandLine -notmatch 'backend[\\/]main\.py' -or
    (-not $ownerHasRoot -and -not $ownedLauncher)) { throw 'Listener is not the local Musicia API; it was left untouched' }
$null = Guard-Idle
Stop-Process -Id $apiPid
$oldApi = Get-Process -Id $apiPid -ErrorAction SilentlyContinue
if ($oldApi -and -not $oldApi.WaitForExit(10000)) { throw 'Old API did not exit; no new service started' }
if ($ownedLauncher) {
    $oldLauncher = Get-Process -Id $launcher.ProcessId -ErrorAction SilentlyContinue
    if ($oldLauncher) {
        Stop-Process -Id $launcher.ProcessId
        if (-not $oldLauncher.WaitForExit(10000)) { throw 'Owned API launcher did not exit; no new service started' }
    }
}
Start-Sleep -Seconds 1
& (Join-Path $PSScriptRoot 'ensure_local.ps1') -SinMotor *> (Join-Path $OutputDirectory 'refresh-api.log')
$limit = (Get-Date).AddSeconds(60)
do {
    try {
        $health = Invoke-RestMethod -Uri ($Api + '/health') -TimeoutSec 5
        $next = @(Get-NetTCPConnection -State Listen -LocalPort $port | Select-Object -ExpandProperty OwningProcess -Unique)
        if ($next.Count -eq 1 -and $next[0] -ne $apiPid) { break }
    } catch { }
    Start-Sleep -Seconds 1
} while ((Get-Date) -lt $limit)
if ($next.Count -ne 1 -or $next[0] -eq $apiPid) { throw 'Refreshed API did not become healthy with a new PID' }
@{ before_pid=$apiPid; before_command=$owner.CommandLine; launcher_pid=($(if ($ownedLauncher) { $launcher.ProcessId })); after_pid=$next[0]; idle_guard=$idle; health=$health; at=(Get-Date).ToString('o') } |
    ConvertTo-Json -Depth 20 | Set-Content -LiteralPath (Join-Path $OutputDirectory 'refresh-api.json') -Encoding utf8
if ($RefreshOnly) {
    Write-Output "API_REFRESH=PASS EVIDENCE=$(Join-Path $OutputDirectory 'refresh-api.json')"
    return
}
$backendPython = Join-Path $projectRoot 'backend\venv\Scripts\python.exe'
Push-Location $projectRoot
try { $timeoutSeconds = & $backendPython -c "import sys; sys.path.insert(0,'backend'); from config import get_settings; print(get_settings().acestep.job_timeout)" }
finally { Pop-Location }
if ($LASTEXITCODE -ne 0) { throw 'CREAR timeout configuration could not be read' }
$oldDirectories = @(Get-ChildItem -LiteralPath (Join-Path $projectRoot 'logs') -Directory -Filter 'plan-completion-ui-create-*' | Select-Object -ExpandProperty FullName)
$env:MUSICIA_PROBE_MODE = 'create'
$env:MUSICIA_API_URL = $Api
$env:MUSICIA_PROBE_TIMEOUT_MS = [string]([int]([double]$timeoutSeconds * 1000))
$ui = Start-Process -FilePath (Join-Path $projectRoot 'frontend\node_modules\electron\dist\electron.exe') -ArgumentList @((Join-Path $PSScriptRoot 'probe_plan_completion_ui.cjs'),'.') -WorkingDirectory $projectRoot -RedirectStandardOutput (Join-Path $OutputDirectory 'create-ui.stdout.log') -RedirectStandardError (Join-Path $OutputDirectory 'create-ui.stderr.log') -WindowStyle Hidden -PassThru
$limit = (Get-Date).AddSeconds([double]$timeoutSeconds)
$submittedPath = $null
do {
    $newDirectories = @(Get-ChildItem -LiteralPath (Join-Path $projectRoot 'logs') -Directory -Filter 'plan-completion-ui-create-*' | Where-Object { $_.FullName -notin $oldDirectories })
    if ($newDirectories.Count -gt 1) { throw 'More than one new CREAR verifier; submission cannot be attributed uniquely' }
    if ($newDirectories.Count -eq 1) {
        $candidate = Join-Path $newDirectories[0].FullName 'submitted.json'
        if (Test-Path -LiteralPath $candidate) { $submittedPath = $candidate; break }
    }
    if ($ui.HasExited) { throw 'CREAR Electron exited before real submission evidence' }
    Start-Sleep -Milliseconds 500
} while ((Get-Date) -lt $limit)
if (-not $submittedPath) { throw 'CREAR did not submit before deadline; own GUI process left untouched' }
$submitted = Get-Content -LiteralPath $submittedPath -Raw | ConvertFrom-Json
Write-Output "CREATE_JOB=$($submitted.job_id)"
& $backendPython (Join-Path $PSScriptRoot 'probe_create_decode.py') --api $Api --job-id $submitted.job_id --request-file $submittedPath --report (Join-Path $OutputDirectory 'create-decode.json') *> (Join-Path $OutputDirectory 'create-decode.log')
if ($LASTEXITCODE -ne 0) { throw 'Real CREAR decode regression failed' }
if (-not $ui.WaitForExit([int]([double]$timeoutSeconds * 1000))) { throw 'CREAR GUI timeout; process left untouched' }
$uiResultFile = Join-Path (Split-Path -Parent $submittedPath) 'result.json'
$uiResult = Get-Content -LiteralPath $uiResultFile -Raw | ConvertFrom-Json
@{ process_id=$ui.Id; exit_code=$ui.ExitCode; result_file=$uiResultFile; result=$uiResult } |
    ConvertTo-Json -Depth 40 | Set-Content -LiteralPath (Join-Path $OutputDirectory 'create-ui-verified.json') -Encoding utf8
if ($ui.ExitCode -ne 0 -or $uiResult.status -ne 'PASS') { throw "CREAR UI failed: $($uiResult.error)" }
Get-Content -LiteralPath (Join-Path $OutputDirectory 'create-decode.log') -Tail 25
