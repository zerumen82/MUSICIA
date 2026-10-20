"""CPU regression of ensure_local.ps1's real engine admission decision.

The PowerShell AST supplies the production probes and decision block. Only
process discovery and stop/start actuators are isolated from real Musicia
services. A disposable Python child supplies its real PID and HTTP socket.
This verifies supervisor policy, not GPU inference or service startup.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
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
    if ($script:fakeProc) { return $script:fakeProc }
}
function Find-Python([string]$Filter) { if ($script:fakeProc) { return @($script:fakeProc) }; return @() }
function Test-Port([int]$Port) { return $false }
function Stop-Process([int]$Id, [switch]$Force, [string]$ErrorAction) {
    $script:actions.Add("stop:$Id")
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


@unittest.skipUnless(os.name == "nt" and POWERSHELL, "Windows PowerShell supervisor")
class EngineSupervisorTest(unittest.TestCase):
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
        recorded_creation=None,
    ):
        environment = os.environ.copy()
        environment.update({
            "MUSICIA_TEST_SUPERVISOR": str(ROOT / "scripts" / "ensure_local.ps1"),
            "MUSICIA_TEST_IDENTITY": str(ROOT / "scripts" / "engine_identity.ps1"),
            "MUSICIA_TEST_OWNER_AVAILABLE": "1" if owner_available else "0",
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
