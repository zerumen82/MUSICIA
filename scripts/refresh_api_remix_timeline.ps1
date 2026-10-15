<# R11: refresh only the owned idle Musicia API, preserving motor/other apps. #>
param(
    [Parameter(Mandatory=$true)][string]$OutputDirectory,
    [string]$Api = 'http://127.0.0.1:8000'
)
$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path -LiteralPath (Split-Path -Parent $PSScriptRoot)).Path
if (([uri]$Api).Host -notin @('127.0.0.1','localhost')) { throw 'Local API required' }
if (Test-Path -LiteralPath (Join-Path $projectRoot 'logs\stop.flag')) { throw 'Musicia stopped; API left untouched' }
$null = New-Item -ItemType Directory -Path $OutputDirectory -Force
$backendPython = Join-Path $projectRoot 'backend\venv\Scripts\python.exe'
Push-Location $projectRoot
try { $engineBase = & $backendPython -c "import sys;sys.path.insert(0,'backend');from config import get_settings;print(get_settings().acestep.base_url)" }
finally { Pop-Location }
if ($LASTEXITCODE -ne 0 -or ([uri]$engineBase).Host -notin @('127.0.0.1','localhost')) { throw 'Configured local engine URL unavailable' }
$enginePort = ([uri]$engineBase).Port
$script:r11InitialPostAnalysisCount = $null
function Guard-Idle {
    $jobs = Invoke-RestMethod -Uri ($Api + '/music/jobs') -TimeoutSec 10
    if (@($jobs.items | Where-Object { $_.status -in @('queued','running') }).Count) { throw 'Active Musicia job; API left untouched' }
    $apiLog = Get-Content -LiteralPath (Join-Path $projectRoot 'logs\musicia-api.log') -Raw
    $posts = @([regex]::Matches($apiLog,'POST /music/remix/analyze HTTP/[^\r\n]*? 200(?: |\r|\n)'))
    $polls = @([regex]::Matches($apiLog,'GET /music/remix/analyze/[a-f0-9]{32}'))
    if ($null -eq $script:r11InitialPostAnalysisCount) {
        if ($posts.Count -and (-not $polls.Count -or $posts[-1].Index -gt $polls[-1].Index)) { throw 'Latest accepted analysis has no subsequent observed poll; API left untouched' }
        $script:r11InitialPostAnalysisCount = $posts.Count
    } elseif ($posts.Count -ne $script:r11InitialPostAnalysisCount) { throw 'Analysis submission occurred during refresh guard; API left untouched' }
    $analysisIds = @([regex]::Matches($apiLog,'/music/remix/analyze/([a-f0-9]{32})') | ForEach-Object { $_.Groups[1].Value } | Sort-Object -Unique)
    if (-not $analysisIds.Count -and $apiLog -match 'POST /music/remix/analyze') { throw 'Analysis submission without observable ID; API left untouched' }
    $states = @()
    foreach ($analysisId in $analysisIds) {
        try {
            $analysis = Invoke-RestMethod -Uri ($Api + '/music/remix/analyze/' + $analysisId) -TimeoutSec 10
            if ($analysis.status -in @('queued','running')) { throw 'Source analysis active; API left untouched' }
            $states += @{id=$analysisId;status=$analysis.status}
        } catch {
            if ([int]$_.Exception.Response.StatusCode -ne 404) { throw }
            # source_understanding evicts terminal entries only, never queued/running entries.
            $states += @{id=$analysisId;status='absent';http_status=404;reason='terminal entries evicted or previous API process'}
        }
    }
    return @{jobs=$jobs;analysis_states=$states;analysis_ids=$analysisIds}
}
$idle = Guard-Idle
$port = ([uri]$Api).Port
$listeners = @(Get-NetTCPConnection -State Listen -LocalPort $port | Select-Object -ExpandProperty OwningProcess -Unique)
if ($listeners.Count -ne 1) { throw 'API listener not unique; untouched' }
$apiPid = [int]$listeners[0]
$owner = Get-CimInstance Win32_Process -Filter "ProcessId = $apiPid"
$launcher = if ($owner) { Get-CimInstance Win32_Process -Filter "ProcessId = $($owner.ParentProcessId)" }
$expectedPython = Join-Path $projectRoot 'backend\venv\Scripts\python.exe'
$ownedLauncher = $launcher -and $launcher.Name -eq 'python.exe' -and $launcher.CommandLine -match 'backend[\\/]main\.py' -and $launcher.CommandLine.IndexOf($expectedPython,[StringComparison]::OrdinalIgnoreCase) -ge 0
$ownerHasRoot = $owner -and $owner.CommandLine.IndexOf($projectRoot,[StringComparison]::OrdinalIgnoreCase) -ge 0
if (-not $owner -or $owner.Name -ne 'python.exe' -or $owner.CommandLine -notmatch 'backend[\\/]main\.py' -or (-not $ownerHasRoot -and -not $ownedLauncher)) { throw 'Listener not owned project API; untouched' }
$engineBefore = Invoke-RestMethod -Uri ($engineBase + '/health') -TimeoutSec 10
$enginePidBefore = @(Get-NetTCPConnection -State Listen -LocalPort $enginePort | Select-Object -ExpandProperty OwningProcess -Unique)
$idleFinal = Guard-Idle
$ownerFinal = Get-CimInstance Win32_Process -Filter "ProcessId = $apiPid"
if (-not $ownerFinal -or $ownerFinal.CreationDate -ne $owner.CreationDate -or $ownerFinal.CommandLine -ne $owner.CommandLine) { throw 'API ownership changed; untouched' }
Stop-Process -Id $apiPid
$old = Get-Process -Id $apiPid -ErrorAction SilentlyContinue
if ($old -and -not $old.WaitForExit(10000)) { throw 'Old API did not exit; no replacement started' }
if ($ownedLauncher) {
    $oldLauncher = Get-Process -Id $launcher.ProcessId -ErrorAction SilentlyContinue
    if ($oldLauncher) {
        $launcherFinal = Get-CimInstance Win32_Process -Filter "ProcessId = $($launcher.ProcessId)"
        if ($launcherFinal) {
            if ($launcherFinal.CreationDate -ne $launcher.CreationDate -or $launcherFinal.CommandLine -ne $launcher.CommandLine) { throw 'Launcher ownership changed; no further process stopped' }
            Stop-Process -Id $launcher.ProcessId
            if (-not $oldLauncher.WaitForExit(10000)) { throw 'Owned launcher did not exit; no replacement started' }
        }
        # Parent launcher may finish between Get-Process and CIM after its API child exits.
        # An absent process needs no stop; a different live owner above remains an abort.
    }
}
& (Join-Path $PSScriptRoot 'ensure_local.ps1') -SinMotor *> (Join-Path $OutputDirectory 'ensure-api.log')
$limit = (Get-Date).AddSeconds(60)
do {
    try {
        $health = Invoke-RestMethod -Uri ($Api + '/health') -TimeoutSec 5
        $next = @(Get-NetTCPConnection -State Listen -LocalPort $port | Select-Object -ExpandProperty OwningProcess -Unique)
        if ($next.Count -eq 1 -and $next[0] -ne $apiPid) { break }
    } catch { }
    Start-Sleep -Milliseconds 500
} while ((Get-Date) -lt $limit)
if ($next.Count -ne 1 -or $next[0] -eq $apiPid) { throw 'Replacement API not healthy with new PID' }
$caps = Invoke-RestMethod -Uri ($Api + '/music/remix/capabilities') -TimeoutSec 10
if (-not $caps.timeline) { throw 'Replacement API lacks R11 capabilities' }
$enginePidAfter = @(Get-NetTCPConnection -State Listen -LocalPort $enginePort | Select-Object -ExpandProperty OwningProcess -Unique)
if (Compare-Object $enginePidBefore $enginePidAfter) { throw 'Engine listener changed during API refresh' }
@{status='PASS';before_pid=$apiPid;before_command=$owner.CommandLine;launcher_pid=($(if($ownedLauncher){$launcher.ProcessId}));after_pid=$next[0];idle=$idle;idle_final=$idleFinal;engine_pid_before=$enginePidBefore;engine_pid_after=$enginePidAfter;engine_health_before=$engineBefore;health=$health;capabilities=$caps;at=(Get-Date).ToString('o')} | ConvertTo-Json -Depth 30 | Set-Content -LiteralPath (Join-Path $OutputDirectory 'refresh-api.json') -Encoding utf8
Write-Output "R11_API_REFRESH=PASS EVIDENCE=$OutputDirectory"
