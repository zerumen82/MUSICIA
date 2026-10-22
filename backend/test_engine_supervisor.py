"""CPU regressions of real engine admission and owned-process shutdown.

PowerShell AST imports production functions without running service launchers.
Policy tests isolate discovery/actuators. Shutdown tests run an existing real
Windows venv launcher and disposable HTTP module, with real CIM and kernel
signals; only the fixed port and selected teardown observations are isolated.
No test loads ACE-Step, performs inference, or controls Musicia services.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parents[1]
POWERSHELL = shutil.which("pwsh") or shutil.which("powershell")
FIXTURE_SECONDS = 4.0  # Exceeds the production HTTP probe's three-second timeout.

FIXTURE = r"""
import http.server
import json
import os
import sys
import time

mode = sys.argv[1]
delay = float(sys.argv[2])
identity = {"pid": os.getpid(), "token": sys.argv[3]}

class Handler(http.server.BaseHTTPRequestHandler):
    first = True

    def do_GET(self):
        if Handler.first:
            Handler.first = False
            time.sleep(delay)
        body = json.dumps(identity).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass

    def log_message(self, *_args):
        pass

if mode == "http":
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    print(json.dumps({**identity, "port": server.server_port}), flush=True)
    server.serve_forever()
else:
    print(json.dumps(identity), flush=True)
    time.sleep(120)
"""

HARNESS = r"""
$ErrorActionPreference = 'Stop'
$tokens = $null
$parseErrors = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile(
    $env:MUSICIA_TEST_SUPERVISOR, [ref]$tokens, [ref]$parseErrors)
if ($parseErrors.Count) { throw ($parseErrors | Out-String) }

# Import the actual probes, without executing the launcher's top-level code.
foreach ($name in @('Test-Endpoint', 'Test-Port')) {
    $definition = @($ast.FindAll({
        param($node)
        $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and
            $node.Name -eq $name
    }, $true))
    if ($definition.Count -ne 1) { throw "Expected one production probe: $name" }
    . ([scriptblock]::Create($definition[0].Extent.Text))
}
$script:productionEndpoint = (Get-Item Function:\Test-Endpoint).ScriptBlock
$script:productionPort = (Get-Item Function:\Test-Port).ScriptBlock

# Locate the engine block and replace only its startup actuator boundary.
# Do not run configuration reads, patching, or any real service launch.
$motor = @($ast.FindAll({
    param($node)
    $node -is [System.Management.Automation.Language.IfStatementAst] -and
        @($node.Clauses | Where-Object { $_.Item1.Extent.Text -eq '-not $SinMotor' }).Count -eq 1
}, $true))
if ($motor.Count -ne 1) { throw 'Expected one production engine block' }
$engineClause = @($motor[0].Clauses | Where-Object { $_.Item1.Extent.Text -eq '-not $SinMotor' })[0]
$body = $engineClause.Item2
$admission = @($body.FindAll({
    param($node)
    $node -is [System.Management.Automation.Language.IfStatementAst] -and
        $node.Clauses[0].Item1.Extent.Text -eq '$motorArriba'
}, $true))
if ($admission.Count -ne 1 -or -not $admission[0].ElseClause) {
    throw 'Expected one production engine start boundary'
}
$start = $admission[0].ElseClause.Extent
if ($start.Text -notmatch "Start-Servicio 'MOTOR'") {
    throw 'Engine start boundary did not contain the production actuator'
}
$source = $body.Extent.Text.Remove(
    $start.StartOffset - $body.Extent.StartOffset, $start.Text.Length).Insert(
    $start.StartOffset - $body.Extent.StartOffset, "{ Start-Servicio 'MOTOR' }")
$source = $source.Substring(1, $source.Length - 2)

$script:actions = [System.Collections.Generic.List[string]]::new()
$script:probes = [System.Collections.Generic.List[bool]]::new()
$SinMotor = $false
$IdleEngine = $false
$WakeEngine = $false
$idleFlag = 'Z:\musicia-supervisor-no-idle-flag'
function Test-Endpoint([string]$url) {
    $result = & $script:productionEndpoint "http://127.0.0.1:$env:MUSICIA_TEST_PORT/health"
    $script:probes.Add([bool]$result)
    return $result
}
function Test-Port([int]$port) {
    & $script:productionPort ([int]$env:MUSICIA_TEST_PORT)
}
function Find-Python([string]$filter) {
    $observed = Get-Process -Id ([int]$env:MUSICIA_TEST_PID) -ErrorAction SilentlyContinue
    if ($observed) { [pscustomobject]@{ ProcessId = $observed.Id } }
}
function Stop-Motor([string]$reason) { $script:actions.Add("stop:$reason") }
function Start-Servicio([string]$label) { $script:actions.Add("start:$label") }
$Rearme = $env:MUSICIA_TEST_REARM -eq '1'
$output = @(. ([scriptblock]::Create($source)))
[pscustomobject]@{
    actions = @($script:actions.ToArray())
    health_results = @($script:probes.ToArray())
    output = $output
    observed_pid = @(Find-Python 'fixture' | ForEach-Object { $_.ProcessId })
} | ConvertTo-Json -Depth 5 -Compress
"""

OWNER_HARNESS = r"""
$ErrorActionPreference = 'Stop'
. $env:MUSICIA_TEST_IDENTITY
$tokens = $null
$parseErrors = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile(
    $env:MUSICIA_TEST_SUPERVISOR, [ref]$tokens, [ref]$parseErrors)
if ($parseErrors.Count) { throw ($parseErrors | Out-String) }
$script:ownerAvailable = $env:MUSICIA_TEST_OWNER_AVAILABLE -eq '1'
$script:rootQueries = 0
$script:ownerText = $env:MUSICIA_TEST_OWNER
$script:fakeProc = [pscustomobject]@{
    ProcessId = 17123
    CreationDate = [datetime]::Parse(
        $env:MUSICIA_TEST_CREATION,
        [Globalization.CultureInfo]::InvariantCulture,
        [Globalization.DateTimeStyles]::AssumeLocal
    )
    ExecutablePath = 'D:\fake\python.exe'
    CommandLine = 'D:\fake\python.exe -m acestep.api_server'
}
$script:actions = [System.Collections.Generic.List[string]]::new()
$engineOwnerFile = 'virtual-owner.json'
$StopTimeoutSeconds = 1
function Test-Path([string]$LiteralPath, [string]$PathType) {
    if ($LiteralPath -eq $engineOwnerFile) { return $script:ownerAvailable }
    return $false
}
function Get-Content([string]$LiteralPath, [switch]$Raw) { return $script:ownerText }
function Get-CimInstance([string]$Class, [string]$Filter, [string]$ErrorAction) {
    if ($script:fakeProc -and $Filter -eq 'ProcessId = 17123') {
        $script:rootQueries++
        if ($env:MUSICIA_TEST_ROOT_MISSING -eq '1') { return }
        if ($script:exiting) {
            if ($script:exitingProbes -gt 0) {
                $script:exitingProbes--
                return [pscustomobject]@{ ProcessId = 17123 }
            }
            $script:fakeProc = $null
            return
        }
        $copy = $script:fakeProc.PSObject.Copy()
        if ($env:MUSICIA_TEST_REUSE_BEFORE_SIGNAL -eq '1' -and $script:rootQueries -ge 3) {
            $copy.CreationDate = $copy.CreationDate.AddSeconds(1)
        }
        return $copy
    }
    if ($script:fakeProc -and $Filter -eq 'ParentProcessId = 17123' -and
        $env:MUSICIA_TEST_CONHOST -eq 'impostor') {
        return [pscustomobject]@{
            ProcessId = 17124
            ParentProcessId = 17123
            CreationDate = $script:fakeProc.CreationDate
            Name = 'conhost.exe'
            ExecutablePath = 'D:\untrusted\conhost.exe'
            CommandLine = 'D:\untrusted\conhost.exe 0x4'
        }
    }
}
function Find-Python([string]$Filter) { if ($script:fakeProc) { return @($script:fakeProc) }; return @() }
function Test-Port([int]$Port) { return $false }
function Stop-Process([int]$Id, [switch]$Force, [string]$ErrorAction) {
    $script:actions.Add("stop:$Id")
    if ($env:MUSICIA_TEST_STOP_FAILURE -eq '1') { throw 'fixture stop failure' }
    if ($env:MUSICIA_TEST_EXITING_METADATA -eq '1') {
        $script:exiting = $true
        $script:exitingProbes = 2
        return
    }
    if ($env:MUSICIA_TEST_REUSE_AFTER_SIGNAL -eq '1') {
        $script:fakeProc.CreationDate = $script:fakeProc.CreationDate.AddSeconds(1)
        return
    }
    $script:fakeProc = $null
}
function Start-Sleep([int]$Milliseconds) {}
function Remove-Item([string]$LiteralPath, [switch]$Force, [string]$ErrorAction) {
    $script:actions.Add('remove-owner')
}
foreach ($name in @('Get-VerifiedEngineOwner', 'Stop-OwnedEngine')) {
    $definition = @($ast.FindAll({
        param($node)
        $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and
            $node.Name -eq $name
    }, $true))
    if ($definition.Count -ne 1) { throw "Expected production owner function: $name" }
    . ([scriptblock]::Create($definition[0].Extent.Text))
}
$succeeded = $true
$errorText = ''
try {
    $null = Stop-OwnedEngine 'test'
} catch {
    $succeeded = $false
    $errorText = $_.Exception.Message
}
[pscustomobject]@{
    succeeded = $succeeded
    error = $errorText
    actions = @($script:actions.ToArray())
} | ConvertTo-Json -Compress
"""

STATUS_HARNESS = r"""
$ErrorActionPreference = 'Stop'
$tokens = $null
$parseErrors = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile(
    $env:MUSICIA_TEST_SUPERVISOR, [ref]$tokens, [ref]$parseErrors)
if ($parseErrors.Count) { throw ($parseErrors | Out-String) }
$script:ownerState = $env:MUSICIA_TEST_OWNER_STATE
$script:portOpen = $env:MUSICIA_TEST_PORT_OPEN -eq '1'
$script:engineReady = $env:MUSICIA_TEST_ENGINE_READY -eq '1'
$lifecycleErrorFile = 'virtual-lifecycle-error'
function Get-VerifiedEngineOwner {
    if ($script:ownerState -eq 'unverified') { throw 'owner cannot be verified' }
    if ($script:ownerState -in @('awake', 'starting')) {
        return [pscustomobject]@{ ProcessId = 17123 }
    }
    return $null
}
function Find-Python([string]$Filter) {
    if ($script:ownerState -eq 'unverified') {
        return @([pscustomobject]@{ ProcessId = 17123 })
    }
    return @()
}
function Test-Port([int]$Port) { return $script:portOpen }
function Test-Endpoint([string]$Url) { return $script:engineReady }
function Test-Path([string]$LiteralPath, [string]$PathType) {
    return $LiteralPath -eq $lifecycleErrorFile -and $env:MUSICIA_TEST_ERROR_PRESENT -eq '1'
}
function Get-Content([string]$LiteralPath, [switch]$Raw, [string]$ErrorAction) {
    return 'supervisor previously failed to verify engine state'
}
$definition = @($ast.FindAll({
    param($node)
    $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and
        $node.Name -eq 'Get-EngineLifecycleStatus'
}, $true))
if ($definition.Count -ne 1) { throw 'Expected production lifecycle status function' }
. ([scriptblock]::Create($definition[0].Extent.Text))
try {
    $status = Get-EngineLifecycleStatus
} catch {
    $status = [pscustomobject]@{ state = 'error'; error = $_.Exception.Message }
}
$status | ConvertTo-Json -Compress
"""

PAIR_FIXTURE = r"""
import http.server
import json
import os
import subprocess
import sys
server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), http.server.SimpleHTTPRequestHandler)
extra = None
if os.environ.get('MUSICIA_TEST_MODE') == 'ambiguous':
    extra = subprocess.Popen([sys._base_executable, '-c', 'import time; time.sleep(120)'],
                             creationflags=subprocess.CREATE_NO_WINDOW)
with open(os.environ['MUSICIA_TEST_READY'], 'w') as ready:
    json.dump({'pid': os.getpid(), 'port': server.server_port,
               'extra_pid': extra.pid if extra else None}, ready)
server.serve_forever()
"""

PAIR_HARNESS = r"""
$ErrorActionPreference = 'Stop'
. $env:MUSICIA_TEST_IDENTITY
$engineOwnerFile = $env:MUSICIA_TEST_OWNER_FILE
$StopTimeoutSeconds = 5
$PSScriptRoot = Join-Path (Split-Path (Split-Path $engineOwnerFile)) 'scripts'
$tokens = $null
$parseErrors = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile(
    $env:MUSICIA_TEST_SUPERVISOR, [ref]$tokens, [ref]$parseErrors)
if ($parseErrors.Count) { throw ($parseErrors | Out-String) }
foreach ($name in @('Get-VerifiedEngineOwner', 'Stop-OwnedEngine')) {
    $definition = @($ast.FindAll({ param($node)
        $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq $name
    }, $true))
    if ($definition.Count -eq 1) {
        # AST-created blocks have no script path; isolate only that path lookup.
        . ([scriptblock]::Create($definition[0].Extent.Text.Replace(
            '$PSScriptRoot', '$env:MUSICIA_TEST_SCRIPT_ROOT')))
    }
}
function Test-Port([int]$port) {
    $client = [System.Net.Sockets.TcpClient]::new()
    try { $client.Connect('127.0.0.1', [int]$env:MUSICIA_TEST_PORT); return $true }
    catch {
        if ($env:MUSICIA_TEST_MODE -eq 'transient' -and $script:closedPortProbes -lt 2) {
            $script:closedPortProbes++
            return $true
        }
        return $false
    } finally { $client.Dispose() }
}
$script:closedPortProbes = 0
$script:exitMetadataProbes = 0
function Get-CimInstance([string]$Class, [string]$Filter, [string]$ErrorAction) {
    if ($env:MUSICIA_TEST_MODE -eq 'exiting-child-metadata' -and $script:childWasSignaled -and
        $Filter -eq "ProcessId = $env:MUSICIA_TEST_CHILD_PID" -and $script:exitMetadataProbes -lt 2) {
        $script:exitMetadataProbes++
        return [pscustomobject]@{ ProcessId = [int]$env:MUSICIA_TEST_CHILD_PID }
    }
    CimCmdlets\Get-CimInstance -ClassName $Class -Filter $Filter -ErrorAction Stop
}
function Get-NetTCPConnection([int]$LocalPort, [string]$State, [string]$ErrorAction) {
    # Remap the fixed production port to the disposable real TCP listener.
    if (Test-Port $LocalPort) { [pscustomobject]@{ OwningProcess = 0 } }
}
function Find-Python([string]$filter) {
    @(Get-CimInstance Win32_Process -Filter "ProcessId = $env:MUSICIA_TEST_PID")
}
$script:stopObservations = [System.Collections.Generic.List[int]]::new()
function Stop-Process([int]$Id, [switch]$Force, [string]$ErrorAction) {
    $script:stopObservations.Add($Id)
    Microsoft.PowerShell.Management\Stop-Process -Id $Id -Force -ErrorAction Stop
    if ($Id -eq [int]$env:MUSICIA_TEST_CHILD_PID) { $script:childWasSignaled = $true }
}
$process = Get-CimInstance Win32_Process -Filter "ProcessId = $env:MUSICIA_TEST_PID"
$fixtureProcesses = @($process)
foreach ($idText in @($env:MUSICIA_TEST_CHILD_PID, $env:MUSICIA_TEST_EXTRA_PID)) {
    if ($idText) { $fixtureProcesses += Get-CimInstance Win32_Process -Filter "ProcessId = $idText" }
}
$fixtureProcesses | Select-Object ProcessId, ParentProcessId, CreationDate, ExecutablePath, CommandLine |
    Export-Clixml -LiteralPath (Join-Path $env:MUSICIA_TEST_FIXTURE_ROOT 'fixture-processes.xml')
[ordered]@{
    pid = [int]$process.ProcessId
    creation_date = Format-EngineCreationDate $process.CreationDate
    executable_path = [string]$process.ExecutablePath
    command_line = [string]$process.CommandLine
} | ConvertTo-Json | Set-Content -LiteralPath $engineOwnerFile
$succeeded = $true
$detail = ''
try {
    $result = @(Stop-OwnedEngine 'fixture')
    if ($env:MUSICIA_TEST_STOP_SCRIPT -eq '1') { $succeeded = [bool]$result[-1] }
} catch { $succeeded = $false; $detail = $_.Exception.Message }
[pscustomobject]@{
    succeeded = $succeeded
    error = $detail
    owner_present = Test-Path -LiteralPath $engineOwnerFile
    root_alive = [bool](Get-Process -Id ([int]$env:MUSICIA_TEST_PID) -ErrorAction SilentlyContinue)
    child_alive = [bool](Get-Process -Id ([int]$env:MUSICIA_TEST_CHILD_PID) -ErrorAction SilentlyContinue)
    port_open = Test-Port 8001
    stopped_ids = @($script:stopObservations.ToArray())
    closed_port_probes = $script:closedPortProbes
    exit_metadata_probes = $script:exitMetadataProbes
} | ConvertTo-Json -Compress
"""


@unittest.skipUnless(os.name == "nt" and POWERSHELL, "Windows PowerShell supervisor")
class EngineSupervisorTest(unittest.TestCase):
    def test_real_venv_pair_stops_launcher_child_and_socket(self):
        self.exercise_real_venv_pair()

    def test_real_venv_pair_preserves_ambiguous_descendant_and_owner(self):
        self.exercise_real_venv_pair('ambiguous')

    def test_real_venv_pair_waits_for_transient_port_close(self):
        # Two delayed closure observations exercise the production deadline;
        # the disposable listener and all process signals remain real.
        self.exercise_real_venv_pair('transient')

    def test_real_venv_pair_preserves_foreign_listener_and_owner(self):
        self.exercise_real_venv_pair('foreign')

    def test_real_venv_pair_waits_for_child_cim_teardown_before_launcher(self):
        self.exercise_real_venv_pair('exiting-child-metadata')

    def exercise_real_venv_pair(self, mode='normal'):
        foreign = self.fixture()[1] if mode == 'foreign' else None
        for script in ('ensure_local.ps1', 'stop_local.ps1'):
            with self.subTest(script=script), tempfile.TemporaryDirectory(prefix='musicia-r18-') as folder:
                fixture_root = Path(folder)
                package = fixture_root / 'acestep'
                package.mkdir()
                (package / '__init__.py').write_text('', encoding='utf-8')
                (package / 'api_server.py').write_text(PAIR_FIXTURE, encoding='utf-8')
                (fixture_root / 'logs').mkdir()
                launcher = ROOT / 'vendor' / 'ACE-Step-1.5' / '.venv311' / 'Scripts' / 'python.exe'
                self.assertTrue(launcher.is_file(), 'Regression requires the existing project venv')
                environment = os.environ.copy()
                environment.update({
                    'MUSICIA_TEST_READY': str(fixture_root / 'ready.json'),
                    'MUSICIA_TEST_LAUNCHER': str(launcher),
                    'MUSICIA_TEST_FIXTURE_ROOT': str(fixture_root),
                    'MUSICIA_TEST_MODE': mode,
                    'MUSICIA_TEST_IDENTITY': str(ROOT / 'scripts' / 'engine_identity.ps1'),
                })
                started = subprocess.run(
                    [POWERSHELL, '-NoLogo', '-NoProfile', '-NonInteractive', '-Command', r'''
$p = Start-Process -FilePath $env:MUSICIA_TEST_LAUNCHER -ArgumentList '-m','acestep.api_server' `
    -WorkingDirectory $env:MUSICIA_TEST_FIXTURE_ROOT -WindowStyle Hidden -PassThru `
    -RedirectStandardOutput (Join-Path $env:MUSICIA_TEST_FIXTURE_ROOT 'stdout.log') `
    -RedirectStandardError (Join-Path $env:MUSICIA_TEST_FIXTURE_ROOT 'stderr.log')
$p.Id | Set-Content -LiteralPath (Join-Path $env:MUSICIA_TEST_FIXTURE_ROOT 'root.pid')
Get-CimInstance Win32_Process -Filter "ProcessId = $($p.Id)" |
    Select-Object ProcessId, ParentProcessId, CreationDate, ExecutablePath, CommandLine |
    Export-Clixml -LiteralPath (Join-Path $env:MUSICIA_TEST_FIXTURE_ROOT 'launcher.xml')
'''], env=environment, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=20,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
                self.assertEqual(started.returncode, 0)
                root_pid = int((fixture_root / 'root.pid').read_text(encoding='utf-8-sig').strip())
                child = None
                try:
                    deadline = time.monotonic() + 10
                    ready = fixture_root / 'ready.json'
                    while not ready.is_file() and time.monotonic() < deadline:
                        time.sleep(0.05)
                    self.assertTrue(ready.is_file(), (fixture_root / 'stderr.log').read_text())
                    identity = json.loads(ready.read_text())
                    child = identity['pid']
                    self.assertNotEqual(child, root_pid, 'Expected real Windows venv launcher topology')
                    environment.update({
                        'MUSICIA_TEST_IDENTITY': str(ROOT / 'scripts' / 'engine_identity.ps1'),
                        'MUSICIA_TEST_SUPERVISOR': str(ROOT / 'scripts' / script),
                        'MUSICIA_TEST_OWNER_FILE': str(fixture_root / 'logs' / 'engine.pid.json'),
                        'MUSICIA_TEST_PID': str(root_pid),
                        'MUSICIA_TEST_CHILD_PID': str(child),
                        'MUSICIA_TEST_EXTRA_PID': str(identity.get('extra_pid') or ''),
                        'MUSICIA_TEST_PORT': str((foreign or identity)['port']),
                        'MUSICIA_TEST_STOP_SCRIPT': '1' if script == 'stop_local.ps1' else '0',
                        'MUSICIA_TEST_SCRIPT_ROOT': str(fixture_root / 'scripts'),
                    })
                    result = subprocess.run(
                        [POWERSHELL, '-NoLogo', '-NoProfile', '-NonInteractive', '-Command', PAIR_HARNESS],
                        env=environment, capture_output=True, text=True, encoding='utf-8',
                        errors='replace', timeout=40, creationflags=subprocess.CREATE_NO_WINDOW,
                    )
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                    outcome = json.loads(result.stdout.strip().splitlines()[-1])
                    outcome['harness_output'] = result.stdout.strip().splitlines()[:-1]
                    if mode == 'ambiguous':
                        self.assertFalse(outcome['succeeded'], outcome)
                        self.assertEqual(outcome['stopped_ids'], [], outcome)
                        self.assertTrue(outcome['owner_present'], outcome)
                        self.assertTrue(outcome['root_alive'], outcome)
                        self.assertTrue(outcome['child_alive'], outcome)
                        self.assertTrue(outcome['port_open'], outcome)
                        continue
                    self.assertEqual(outcome['succeeded'], mode != 'foreign', outcome)
                    self.assertTrue(outcome['stopped_ids'], outcome)
                    self.assertEqual(outcome['stopped_ids'][0], child, outcome)
                    self.assertFalse(outcome['root_alive'], outcome)
                    self.assertFalse(outcome['child_alive'], outcome)
                    self.assertEqual(outcome['port_open'], mode == 'foreign', outcome)
                    self.assertEqual(outcome['owner_present'], mode == 'foreign', outcome)
                    if mode == 'transient':
                        self.assertEqual(outcome['closed_port_probes'], 2, outcome)
                    if mode == 'exiting-child-metadata':
                        self.assertEqual(outcome['exit_metadata_probes'], 2, outcome)
                    if foreign:
                        with urlopen(f"http://127.0.0.1:{foreign['port']}/health", timeout=5) as response:
                            self.assertEqual(json.load(response),
                                             {'pid': foreign['pid'], 'token': self.id()})
                finally:
                    # Revalidate every disposable identity before cleanup; a
                    # completed stop may already have released/reused its PID.
                    cleanup = subprocess.run(
                        [POWERSHELL, '-NoLogo', '-NoProfile', '-NonInteractive', '-Command', r'''
. $env:MUSICIA_TEST_IDENTITY
$snapshotFile = Join-Path $env:MUSICIA_TEST_FIXTURE_ROOT 'fixture-processes.xml'
if (-not (Test-Path -LiteralPath $snapshotFile)) {
    $snapshotFile = Join-Path $env:MUSICIA_TEST_FIXTURE_ROOT 'launcher.xml'
}
$snapshots = @(Import-Clixml -LiteralPath $snapshotFile)
[array]::Reverse($snapshots)
foreach ($snapshot in $snapshots) {
    $current = Get-CimInstance Win32_Process -Filter "ProcessId = $($snapshot.ProcessId)"
    if (Test-EngineProcessSnapshot $snapshot $current) {
        Stop-Process -Id ([int]$snapshot.ProcessId) -Force -ErrorAction Stop
    } elseif ($current) { throw 'Fixture cleanup refused a reused PID' }
}
'''], env=environment, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                        text=True, timeout=20, creationflags=subprocess.CREATE_NO_WINDOW,
                    )
                    self.assertEqual(cleanup.returncode, 0, cleanup.stderr)

    def fixture(self, mode="http", delay=0):
        # Use the real interpreter directly: Windows venv launchers can spawn
        # an extra child, while this fixture must own exactly one process.
        process = subprocess.Popen(
            [sys._base_executable, "-u", "-c", FIXTURE, mode, str(delay), self.id()],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", creationflags=subprocess.CREATE_NO_WINDOW,
        )

        def cleanup():
            if process.poll() is None:
                process.terminate()
            process.communicate(timeout=10)

        self.addCleanup(cleanup)
        identity = json.loads(process.stdout.readline())
        self.assertEqual(identity["pid"], process.pid)
        return process, identity

    def closed_port(self):
        reserved = socket.socket()
        reserved.bind(("127.0.0.1", 0))
        self.addCleanup(reserved.close)
        return reserved.getsockname()[1]

    def decision(self, pid, port, rearm=False):
        environment = os.environ.copy()
        environment.update({
            "MUSICIA_TEST_SUPERVISOR": str(ROOT / "scripts" / "ensure_local.ps1"),
            "MUSICIA_TEST_PID": str(pid),
            "MUSICIA_TEST_PORT": str(port),
            "MUSICIA_TEST_REARM": "1" if rearm else "0",
        })
        result = subprocess.run(
            [POWERSHELL, "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", HARNESS],
            env=environment, capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=20, creationflags=subprocess.CREATE_NO_WINDOW,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(result.stdout.strip(), result.stderr)
        try:
            return json.loads(result.stdout.strip())
        except json.JSONDecodeError as exc:
            self.fail(f"Invalid supervisor harness output: {result.stdout!r} {result.stderr!r}: {exc}")

    def owner_decision(
        self, owner_available, creation_date="2026-10-18T19:55:34",
        recorded_creation=None, reuse_before_signal=False, stop_failure=False,
        root_missing=False, conhost='',
        exiting_metadata=False, reuse_after_signal=False,
    ):
        environment = os.environ.copy()
        environment.update({
            "MUSICIA_TEST_SUPERVISOR": str(ROOT / "scripts" / "ensure_local.ps1"),
            "MUSICIA_TEST_IDENTITY": str(ROOT / "scripts" / "engine_identity.ps1"),
            "MUSICIA_TEST_OWNER_AVAILABLE": "1" if owner_available else "0",
            "MUSICIA_TEST_REUSE_BEFORE_SIGNAL": "1" if reuse_before_signal else "0",
            "MUSICIA_TEST_STOP_FAILURE": "1" if stop_failure else "0",
            "MUSICIA_TEST_ROOT_MISSING": "1" if root_missing else "0",
            "MUSICIA_TEST_CONHOST": conhost,
            "MUSICIA_TEST_EXITING_METADATA": "1" if exiting_metadata else "0",
            "MUSICIA_TEST_REUSE_AFTER_SIGNAL": "1" if reuse_after_signal else "0",
            "MUSICIA_TEST_CREATION": creation_date,
            "MUSICIA_TEST_OWNER": json.dumps({
                "pid": 17123,
                "creation_date": recorded_creation or creation_date,
                "executable_path": r"D:\fake\python.exe",
                "command_line": r"D:\fake\python.exe -m acestep.api_server",
            }),
        })
        result = subprocess.run(
            [POWERSHELL, "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", OWNER_HARNESS],
            env=environment, capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=20, creationflags=subprocess.CREATE_NO_WINDOW,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(result.stdout.strip(), result.stderr)
        try:
            return json.loads(result.stdout.strip())
        except json.JSONDecodeError as exc:
            self.fail(f"Invalid ownership harness output: {result.stdout!r} {result.stderr!r}: {exc}")

    def lifecycle_decision(
        self, owner_state, *, port_open=False, engine_ready=True, error_present=False,
    ):
        environment = os.environ.copy()
        environment.update({
            "MUSICIA_TEST_SUPERVISOR": str(ROOT / "scripts" / "ensure_local.ps1"),
            "MUSICIA_TEST_OWNER_STATE": owner_state,
            "MUSICIA_TEST_PORT_OPEN": "1" if port_open else "0",
            "MUSICIA_TEST_ENGINE_READY": "1" if engine_ready else "0",
            "MUSICIA_TEST_ERROR_PRESENT": "1" if error_present else "0",
        })
        result = subprocess.run(
            [POWERSHELL, "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", STATUS_HARNESS],
            env=environment, capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=20, creationflags=subprocess.CREATE_NO_WINDOW,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return json.loads(result.stdout.strip())

    def test_health_timeout_preserves_live_pid_and_later_identity(self):
        process, identity = self.fixture(delay=FIXTURE_SECONDS)
        result = self.decision(process.pid, identity["port"])
        self.assertEqual(result["health_results"], [False])
        with urlopen(f"http://127.0.0.1:{identity['port']}/health", timeout=5) as response:
            later = json.load(response)
        self.assertEqual(later, {"pid": process.pid, "token": self.id()})
        self.assertIsNone(process.poll())
        self.assertEqual(result["observed_pid"], [process.pid])
        self.assertEqual(result["actions"], [], result)
        self.assertIn("MOTOR=starting", result["output"])

    def test_present_process_without_open_port_is_preserved(self):
        process, _identity = self.fixture(mode="sleep")
        result = self.decision(process.pid, self.closed_port())
        self.assertEqual(result["health_results"], [False])
        self.assertIsNone(process.poll())
        self.assertEqual(result["observed_pid"], [process.pid])
        self.assertEqual(result["actions"], [], result)
        self.assertIn("MOTOR=starting", result["output"])

    def test_absent_engine_requests_one_start(self):
        process, _identity = self.fixture(mode="sleep")
        process.terminate()
        process.communicate(timeout=10)
        result = self.decision(process.pid, self.closed_port())
        self.assertEqual(result["observed_pid"], [])
        self.assertEqual(result["actions"], ["start:MOTOR"])

    def test_explicit_rearm_requests_stop_then_start(self):
        process, identity = self.fixture()
        result = self.decision(process.pid, identity["port"], rearm=True)
        self.assertEqual(result["health_results"], [True])
        self.assertEqual(result["actions"], ["stop:liberando-vram", "start:MOTOR"])
        self.assertIsNone(process.poll())  # Stop is recorded, never performed.

    def test_engine_stop_uses_only_the_proven_pid(self):
        result = self.owner_decision(
            owner_available=True,
            creation_date="2026-10-18T19:55:34.1234567Z",
        )
        self.assertTrue(result["succeeded"], result)
        self.assertEqual(result["actions"], ["stop:17123", "remove-owner"])

    def test_engine_stop_refuses_a_reused_pid(self):
        result = self.owner_decision(
            owner_available=True,
            creation_date="2026-10-18T19:55:35",
            recorded_creation="2026-10-18T19:55:34",
        )
        self.assertFalse(result["succeeded"])
        self.assertIn("no coincide", result["error"])
        self.assertEqual(result["actions"], [])

    def test_engine_stop_revalidates_identity_immediately_before_signal(self):
        result = self.owner_decision(owner_available=True, reuse_before_signal=True)
        self.assertFalse(result['succeeded'], result)
        self.assertIn('cambi', result['error'])
        self.assertEqual(result['actions'], [], result)

    def test_engine_stop_preserves_owner_on_stop_failure(self):
        result = self.owner_decision(owner_available=True, stop_failure=True)
        self.assertFalse(result['succeeded'], result)
        self.assertIn('fixture stop failure', result['error'])
        self.assertEqual(result['actions'], ['stop:17123'], result)

    def test_engine_stop_preserves_owner_if_root_is_absent_but_engine_remains(self):
        result = self.owner_decision(owner_available=True, root_missing=True)
        self.assertFalse(result['succeeded'], result)
        self.assertEqual(result['actions'], [], result)

    def test_engine_stop_refuses_console_host_outside_system_directory(self):
        result = self.owner_decision(owner_available=True, conhost='impostor')
        self.assertFalse(result['succeeded'], result)
        self.assertEqual(result['actions'], [], result)

    def test_engine_stop_waits_for_incomplete_cim_metadata_during_exit(self):
        result = self.owner_decision(owner_available=True, exiting_metadata=True)
        self.assertTrue(result['succeeded'], result)
        self.assertEqual(result['actions'], ['stop:17123', 'remove-owner'], result)

    def test_engine_stop_preserves_owner_for_proven_reuse_after_signal(self):
        result = self.owner_decision(owner_available=True, reuse_after_signal=True)
        self.assertFalse(result['succeeded'], result)
        self.assertIn('reutilizado', result['error'])
        self.assertEqual(result['actions'], ['stop:17123'], result)

    def test_engine_stop_accepts_unambiguous_legacy_date_from_other_locale(self):
        result = self.owner_decision(
            owner_available=True,
            creation_date="2026-10-18T19:55:34.1644250",
            recorded_creation="10/18/2026 19:55:34",
        )
        self.assertTrue(result["succeeded"], result)
        self.assertEqual(result["actions"], ["stop:17123", "remove-owner"])

    def test_engine_stop_refuses_ambiguous_legacy_date(self):
        result = self.owner_decision(
            owner_available=True,
            creation_date="2026-01-02T19:55:34",
            recorded_creation="01/02/2026 19:55:34",
        )
        self.assertFalse(result["succeeded"])
        self.assertIn("no coincide", result["error"])
        self.assertEqual(result["actions"], [])

    def test_engine_stop_refuses_a_process_without_ownership_record(self):
        result = self.owner_decision(owner_available=False)
        self.assertFalse(result["succeeded"])
        self.assertIn("verificable", result["error"])
        self.assertEqual(result["actions"], [])

    def test_inspection_reports_verified_live_engine_as_awake(self):
        result = self.lifecycle_decision("awake", port_open=True, engine_ready=True)
        self.assertEqual(result, {"state": "awake", "process_id": 17123})

    def test_inspection_does_not_report_awake_when_health_fails(self):
        result = self.lifecycle_decision(
            "awake", port_open=True, engine_ready=False,
        )
        self.assertEqual(result, {"state": "starting", "process_id": 17123})

    def test_inspection_reports_verified_unready_engine_as_starting(self):
        result = self.lifecycle_decision("starting")
        self.assertEqual(result, {"state": "starting", "process_id": 17123})

    def test_inspection_reports_idle_only_without_process_or_port(self):
        result = self.lifecycle_decision("absent")
        self.assertEqual(result, {"state": "idle"})

    def test_inspection_preserves_unverified_process_as_error_not_idle(self):
        result = self.lifecycle_decision("unverified")
        self.assertEqual(result["state"], "error")
        self.assertIn("owner cannot be verified", result["error"])

    def test_inspection_preserves_supervisor_error_without_engine_owner(self):
        result = self.lifecycle_decision("absent", error_present=True)
        self.assertEqual(result["state"], "error")
        self.assertIn("supervisor previously failed", result["error"])


if __name__ == "__main__":
    unittest.main()
