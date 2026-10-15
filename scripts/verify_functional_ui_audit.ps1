<# Own the actual Electron audit process and require its terminal result. #>
param(
    [Parameter(Mandatory=$true)][string]$Source,
    [Parameter(Mandatory=$true)][string]$Upload,
    [Parameter(Mandatory=$true)][string]$OutputDirectory,
    [ValidateSet('baseline','full')][string]$Phase = 'full',
    [switch]$CpuExports,
    [int]$TimeoutSeconds = 120,
    [string]$Api = 'http://127.0.0.1:8000'
)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
if (([uri]$Api).Host -notin @('127.0.0.1','localhost')) { throw 'Local API required' }
$health = Invoke-RestMethod -Uri ($Api + '/health') -TimeoutSec 8
$jobs = Invoke-RestMethod -Uri ($Api + '/music/jobs') -TimeoutSec 8
if (@($jobs.items | Where-Object { $_.status -in @('queued','running') }).Count -gt 0) { throw 'Another job is active; no audit started' }
$library = Invoke-RestMethod -Uri ($Api + '/music/library') -TimeoutSec 8
$uploads = Invoke-RestMethod -Uri ($Api + '/audio/uploads') -TimeoutSec 8
if (@($library.items | Where-Object { $_.name -eq $Source }).Count -ne 1 -or
    @($uploads.items | Where-Object { $_.name -eq $Upload }).Count -ne 1) { throw 'Exact real audit source/upload must exist' }
$existing = @(Get-ChildItem -LiteralPath (Join-Path $projectRoot 'logs') -Directory -Filter 'functional-ui-audit-*' | Select-Object -ExpandProperty FullName)
$env:MUSICIA_API_URL = $Api
$env:MUSICIA_AUDIT_SOURCE = $Source
$env:MUSICIA_AUDIT_UPLOAD = $Upload
$env:MUSICIA_AUDIT_PHASE = $Phase
$env:MUSICIA_AUDIT_CPU = if ($CpuExports) { '1' } else { '0' }
$env:MUSICIA_AUDIT_TIMEOUT_MS = [string]($TimeoutSeconds * 1000)
$ui = Start-Process -FilePath (Join-Path $projectRoot 'frontend\node_modules\electron\dist\electron.exe') -ArgumentList @((Join-Path $PSScriptRoot 'probe_functional_ui_audit.cjs'),'.') -WorkingDirectory $projectRoot -RedirectStandardOutput (Join-Path $OutputDirectory 'audit-ui.stdout.log') -RedirectStandardError (Join-Path $OutputDirectory 'audit-ui.stderr.log') -WindowStyle Hidden -PassThru
$limit = (Get-Date).AddSeconds($TimeoutSeconds * 8)
$resultPath = $null
do {
    $new = @(Get-ChildItem -LiteralPath (Join-Path $projectRoot 'logs') -Directory -Filter 'functional-ui-audit-*' | Where-Object { $_.FullName -notin $existing })
    if ($new.Count -gt 1) { throw 'Multiple new audit windows; result cannot be uniquely attributed' }
    if ($new.Count -eq 1) {
        $candidate = Join-Path $new[0].FullName 'result.json'
        if (Test-Path -LiteralPath $candidate) {
            $partial = Get-Content -LiteralPath $candidate -Raw | ConvertFrom-Json
            if ($partial.status -ne 'RUNNING') { $resultPath = $candidate; break }
        }
    }
    if ($ui.HasExited) { throw 'Audit Electron exited without a terminal result' }
    Start-Sleep -Milliseconds 500
} while ((Get-Date) -lt $limit)
if (-not $resultPath) { throw 'Audit timeout; existing services and own window left untouched' }
if (-not $ui.WaitForExit(10000)) { throw 'Audit result exists but process has not exited' }
$result = Get-Content -LiteralPath $resultPath -Raw | ConvertFrom-Json
@{ process_id=$ui.Id; exit_code=$ui.ExitCode; result_file=$resultPath; result=$result; health=$health } |
    ConvertTo-Json -Depth 45 | Set-Content -LiteralPath (Join-Path $OutputDirectory 'functional-audit-verified.json') -Encoding utf8
Write-Output "AUDIT=$($result.status) EVIDENCE=$resultPath"
if ($ui.ExitCode -ne 0 -or $result.status -ne 'PASS') { throw 'Current UI audit found failures; see per-criterion actual evidence' }
