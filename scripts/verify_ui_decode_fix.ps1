<#
Independent verification of the authorized UI/decode correction. Runs real
checks and one Electron-submitted generation, observed through the live API.
Starts only Musicia via ensure_local; never stops unrelated services/jobs.
#>
param(
    [Parameter(Mandatory=$true)][string]$BaselineJob,
    [Parameter(Mandatory=$true)][string]$LayoutSource,
    [switch]$SkipFrontendChecks,
    [int]$PreviousRunnerPid = 0,
    [int]$CaptureDecodeWindowPid = 0,
    [string]$CaptureDecodeJob,
    [switch]$RefreshApiSmoke,
    [string]$CompletedEvidence,
    [string]$VerifiedLayoutEvidence,
    [switch]$LayoutOnly,
    [switch]$FinishVerification,
    [switch]$FunctionalUiAudit,
    [string]$AuditSource,
    [string]$AuditUpload,
    [ValidateSet('baseline','full')][string]$AuditPhase = 'full',
    [switch]$AuditCpuExports,
    [int]$StartupTimeoutSeconds = 240,
    [string]$Api = 'http://127.0.0.1:8000'
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$runDir = Join-Path $projectRoot ('logs\ui-decode-verification-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
$null = New-Item -ItemType Directory -Path $runDir -Force
$testTemp = Join-Path $runDir 'temp'
$null = New-Item -ItemType Directory -Path $testTemp -Force
$oldTemp = $env:TEMP
$oldTmp = $env:TMP
$oldProbeMode = $env:MUSICIA_PROBE_MODE
$oldProbeSource = $env:MUSICIA_PROBE_SOURCE
$oldProbeApi = $env:MUSICIA_API_URL
$oldProbeTimeout = $env:MUSICIA_PROBE_TIMEOUT_MS
$env:TEMP = $testTemp
$env:TMP = $testTemp
$backendPython = Join-Path $projectRoot 'backend\venv\Scripts\python.exe'
$enginePython = Join-Path $projectRoot 'vendor\ACE-Step-1.5\.venv\Scripts\python.exe'
$electronExe = Join-Path $projectRoot 'frontend\node_modules\electron\dist\electron.exe'
$report = [ordered]@{ status='RUNNING'; started_at=(Get-Date).ToString('o'); checks=@(); evidence=$runDir }

function Save-Report {
    $report | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath (Join-Path $runDir 'result.json') -Encoding utf8
}

function Check-Native([string]$Name, [string]$Executable, [string[]]$Arguments, [string]$Cwd) {
    Push-Location $Cwd
    try {
        $target = Join-Path $runDir ($Name + '.log')
        & $Executable @Arguments *> $target
        $resultCode = $LASTEXITCODE
        $report.checks += @{ name=$Name; command=$Executable; arguments=$Arguments; exit_code=$resultCode; log=$target }
        Save-Report
        Get-Content -LiteralPath $target -Tail 25
        if ($resultCode -ne 0) { throw "$Name failed, exit $resultCode" }
    } finally { Pop-Location }
}

function Wait-Services {
    $limit = (Get-Date).AddSeconds($StartupTimeoutSeconds)
    do {
        try {
            $apiHealth = Invoke-RestMethod -Uri ($Api + '/health') -TimeoutSec 5
            $motorHealth = Invoke-RestMethod -Uri 'http://127.0.0.1:8001/health' -TimeoutSec 5
            $report.api_health = $apiHealth
            $report.motor_health = $motorHealth
            Save-Report
            return
        } catch { Start-Sleep -Seconds 2 }
    } while ((Get-Date) -lt $limit)
    throw 'Musicia services did not become healthy in time'
}

Save-Report
Write-Output "EVIDENCE=$runDir"
try {
    $apiUri = [uri]$Api
    if ($apiUri.Host -notin @('127.0.0.1','localhost')) { throw 'Verification requires a local Musicia API' }
    if ($FunctionalUiAudit) {
        & (Join-Path $PSScriptRoot 'verify_functional_ui_audit.ps1') -Source $AuditSource -Upload $AuditUpload -OutputDirectory $runDir -Phase $AuditPhase -CpuExports:$AuditCpuExports -Api $Api
        $report.functionalAudit = Get-Content -LiteralPath (Join-Path $runDir 'functional-audit-verified.json') -Raw | ConvertFrom-Json
        $report.status = 'PASS'; $report.mode = 'functional-ui-audit'; $report.completed_at = (Get-Date).ToString('o')
        return
    }
    if ($CaptureDecodeWindowPid -ne 0) {
        if ($CaptureDecodeWindowPid -le 0 -or [string]::IsNullOrWhiteSpace($CaptureDecodeJob)) { throw 'Window PID and live job ID required for capture' }
        & (Join-Path $PSScriptRoot 'capture_decode_window.ps1') -WindowProcessId $CaptureDecodeWindowPid -JobId $CaptureDecodeJob -OutputDirectory $runDir -Api $Api
        $report.status = 'PASS'
        $report.mode = 'capture-existing-window-only'
        $report.completed_at = (Get-Date).ToString('o')
        return
    }
    if ($LayoutOnly) {
        & (Join-Path $PSScriptRoot 'verify_layout_window.ps1') -Source $LayoutSource -OutputDirectory $runDir -Api $Api
        $report.layoutVerified = Get-Content -LiteralPath (Join-Path $runDir 'layout-verified.json') -Raw | ConvertFrom-Json
        $report.status = 'PASS'
        $report.mode = 'layout-and-dsp-only'
        $report.completed_at = (Get-Date).ToString('o')
        return
    }
    if ($FinishVerification) {
        if ([string]::IsNullOrWhiteSpace($CompletedEvidence)) { throw 'Original decode evidence required' }
        Check-Native 'backend-final' $backendPython @('-m','unittest','discover','-p','test_*.py') (Join-Path $projectRoot 'backend')
        & (Join-Path $PSScriptRoot 'verify_layout_window.ps1') -Source $LayoutSource -OutputDirectory $runDir -Api $Api
        $report.layoutVerified = Get-Content -LiteralPath (Join-Path $runDir 'layout-verified.json') -Raw | ConvertFrom-Json
        & (Join-Path $PSScriptRoot 'refresh_api_decode_smoke.ps1') -CompletedEvidence $CompletedEvidence -VerifiedLayoutEvidence (Join-Path $runDir 'layout-verified.json') -OutputDirectory $runDir -Api $Api
        $report.status = 'PASS'
        $report.mode = 'complete-layout-refresh-own-api-and-real-create'
        $report.original_decode_evidence = $CompletedEvidence
        $report.completed_at = (Get-Date).ToString('o')
        return
    }
    if ($RefreshApiSmoke) {
        if ([string]::IsNullOrWhiteSpace($CompletedEvidence)) { throw 'Completed UI evidence required before API smoke' }
        & (Join-Path $PSScriptRoot 'refresh_api_decode_smoke.ps1') -CompletedEvidence $CompletedEvidence -VerifiedLayoutEvidence $VerifiedLayoutEvidence -OutputDirectory $runDir -Api $Api
        $report.status = 'PASS'
        $report.mode = 'refresh-own-api-and-real-create-smoke'
        $report.completed_at = (Get-Date).ToString('o')
        return
    }
    if ($PreviousRunnerPid -ne 0) {
        if ($PreviousRunnerPid -le 0 -or $PreviousRunnerPid -eq $PID) { throw 'Invalid previous runner PID' }
        $previous = Get-CimInstance Win32_Process -Filter "ProcessId = $PreviousRunnerPid"
        if (-not $previous -or $previous.Name -ne 'pwsh.exe' -or
            $previous.CommandLine -notmatch '(?i)verify_ui_decode_fix\.ps1' -or
            $previous.CommandLine -notlike "*$BaselineJob*") {
            throw 'Previous PID is not this verification runner with the same baseline; it was left untouched'
        }
        Stop-Process -Id $PreviousRunnerPid
        $report.previous_runner_stopped = @{ pid=$PreviousRunnerPid; at=(Get-Date).ToString('o'); children_stopped=$false }
        Save-Report
    }
    $history = Get-Content -LiteralPath (Join-Path $projectRoot 'backend\job_history.json') -Raw | ConvertFrom-Json
    $baseline = @($history.remix | Where-Object { $_.job_id -eq $BaselineJob })
    if ($baseline.Count -ne 1) { throw 'Baseline historical job not found uniquely' }
    $baselineFile = Join-Path $runDir 'baseline-history.json'
    $history | ConvertTo-Json -Depth 40 | Set-Content -LiteralPath $baselineFile -Encoding utf8
    $source = $baseline[0].project.source_name
    Push-Location $projectRoot
    try {
        $settingsOutput = & $backendPython -c "import sys,json; sys.path.insert(0,'backend'); from config import get_settings; s=get_settings(); print(json.dumps({'timeout':s.acestep.job_timeout,'output_dir':str(s.outputs_dir)}))"
    } finally { Pop-Location }
    if ($LASTEXITCODE -ne 0) { throw 'Configuration read failed' }
    $settings = $settingsOutput | ConvertFrom-Json
    if (-not (Test-Path -LiteralPath (Join-Path $settings.output_dir $LayoutSource))) { throw 'Exact real layout source does not exist' }
    $env:MUSICIA_PROBE_TIMEOUT_MS = [string]([int]($settings.timeout * 1000))
    $env:MUSICIA_API_URL = $Api

    if (-not $SkipFrontendChecks) {
        Check-Native 'lint' 'npm.cmd' @('run','lint') (Join-Path $projectRoot 'frontend')
        Check-Native 'build' 'npm.cmd' @('run','build') (Join-Path $projectRoot 'frontend')
        Check-Native 'node' 'node.exe' @('--test','src/*.test.js') (Join-Path $projectRoot 'frontend')
    } else {
        $report.frontend_checks = 'Skipped by explicit runner option; use separate recorded lint/build/Node evidence'
    }
    Check-Native 'backend' $backendPython @('-m','unittest','discover','-p','test_*.py') (Join-Path $projectRoot 'backend')
    Check-Native 'vae-patch' $enginePython @('-m','unittest','scripts.test_acestep_vae_patch','-v') $projectRoot
    # Inline PowerShell avoids a native stdout pipeline inherited by the
    # detached services. Stop only our previous runner, never its children.
    $startLog = Join-Path $runDir 'start-musicia.log'
    & (Join-Path $PSScriptRoot 'ensure_local.ps1') -Rearme *> $startLog
    $startSucceeded = $?
    $report.checks += @{ name='start-musicia'; command=(Join-Path $PSScriptRoot 'ensure_local.ps1'); arguments=@('-Rearme'); exit_code=([int](-not $startSucceeded)); log=$startLog }
    Save-Report
    Get-Content -LiteralPath $startLog -Tail 25
    if (-not $startSucceeded) { throw 'Musicia startup failed' }
    Wait-Services
    $existing = Invoke-RestMethod -Uri ($Api + '/music/jobs') -TimeoutSec 15
    if (@($existing.items | Where-Object { $_.status -in @('running','queued') }).Count -gt 0) {
        throw 'Another Musicia job is active; no generation submitted'
    }

    $env:MUSICIA_PROBE_MODE = 'decode'
    $env:MUSICIA_PROBE_SOURCE = $source
    $decodeOut = Join-Path $runDir 'decode-ui.stdout.log'
    $decodeErr = Join-Path $runDir 'decode-ui.stderr.log'
    $uiProcess = Start-Process -FilePath $electronExe -ArgumentList @((Join-Path $PSScriptRoot 'probe_plan_completion_ui.cjs'),'.') -WorkingDirectory $projectRoot -RedirectStandardOutput $decodeOut -RedirectStandardError $decodeErr -WindowStyle Hidden -PassThru
    $report.decode_ui_pid = $uiProcess.Id
    Save-Report
    $limit = (Get-Date).AddSeconds($settings.timeout)
    $submittedPath = $null
    do {
        $submittedPath = Get-ChildItem -LiteralPath (Join-Path $projectRoot 'logs') -Directory -Filter 'plan-completion-ui-decode-*' |
            Where-Object { $_.LastWriteTime -ge ([datetime]$report.started_at) } |
            ForEach-Object { Join-Path $_.FullName 'submitted.json' } |
            Where-Object { Test-Path -LiteralPath $_ } |
            Select-Object -First 1
        if ($submittedPath) { break }
        if ($uiProcess.HasExited) { throw "Electron decode probe exited before submission: $($uiProcess.ExitCode)" }
        Start-Sleep -Milliseconds 500
    } while ((Get-Date) -lt $limit)
    if (-not $submittedPath) { throw 'Electron did not submit a job before deadline; it is left untouched' }
    $submitted = Get-Content -LiteralPath $submittedPath -Raw | ConvertFrom-Json
    $report.submission = $submitted
    $report.submission_file = $submittedPath
    Save-Report
    Write-Output "DECODE_JOB=$($submitted.job_id)"
    Check-Native 'decode-http-audio' $backendPython @((Join-Path $PSScriptRoot 'probe_decode_recovery.py'),'--baseline-job',$BaselineJob,'--job-id',$submitted.job_id,'--history',$baselineFile,'--api',$Api,'--output-name',$submitted.request.output_name,'--report',(Join-Path $runDir 'decode-http-audio.json')) $projectRoot
    if (-not $uiProcess.WaitForExit([int]($settings.timeout * 1000))) { throw 'Electron timeout; process/job left untouched' }
    $report.decode_ui_exit_code = $uiProcess.ExitCode
    $decodeResult = Join-Path (Split-Path -Parent $submittedPath) 'result.json'
    $report.decode_ui = Get-Content -LiteralPath $decodeResult -Raw | ConvertFrom-Json
    if ($uiProcess.ExitCode -ne 0 -or $report.decode_ui.status -ne 'PASS') { throw 'Electron decode verification failed' }

    & (Join-Path $PSScriptRoot 'verify_layout_window.ps1') -Source $LayoutSource -OutputDirectory $runDir -Api $Api
    $report.layoutVerified = Get-Content -LiteralPath (Join-Path $runDir 'layout-verified.json') -Raw | ConvertFrom-Json
    $report.status = 'PASS'
    $report.completed_at = (Get-Date).ToString('o')
} catch {
    $report.status = 'FAIL'
    $report.error = $_.Exception.Message
    $report.completed_at = (Get-Date).ToString('o')
    Save-Report
    throw
} finally {
    Save-Report
    $env:TEMP = $oldTemp
    $env:TMP = $oldTmp
    $env:MUSICIA_PROBE_MODE = $oldProbeMode
    $env:MUSICIA_PROBE_SOURCE = $oldProbeSource
    $env:MUSICIA_API_URL = $oldProbeApi
    $env:MUSICIA_PROBE_TIMEOUT_MS = $oldProbeTimeout
    Write-Output "VERDICT=$($report.status) EVIDENCE=$runDir"
}
