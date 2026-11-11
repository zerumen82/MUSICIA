"""API ownership against actual Python command lines from two project roots.

The temporary scripts are process-identity fixtures, never pretend API servers.
PowerShell AST loads only pure production predicates; no supervisor actuator is
imported or invoked. Every child exits through an owned stop file in cleanup.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest


ROOT = Path(__file__).resolve().parents[1]
POWERSHELL = shutil.which("pwsh") or shutil.which("powershell")
FIXTURE = """from pathlib import Path
import sys
import time
ready = Path(sys.argv[-1])
ready.write_text('process ready', encoding='utf-8')
while not ready.with_suffix('.stop').exists():
    time.sleep(0.03)
"""
PREDICATE_HARNESS = r"""
$ErrorActionPreference = 'Stop'
$tokens = $null
$errors = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile(
    $env:MUSICIA_IDENTITY_HELPER, [ref]$tokens, [ref]$errors)
if ($errors.Count) { throw ($errors | Out-String) }
foreach ($name in @('Get-MusiciaApiScriptArgument', 'Test-MusiciaApiCommandLine',
    'Get-MusiciaApiCreationTicks', 'Test-MusiciaApiProcess', 'Test-MusiciaApiProcessSnapshot')) {
    $definitions = @($ast.FindAll({ param($node)
        $node -is [Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq $name
    }, $true))
    if ($definitions.Count -ne 1) { throw "Expected one pure predicate $name" }
    . ([scriptblock]::Create($definitions[0].Extent.Text))
}
$root = $env:MUSICIA_IDENTITY_ROOT
$ids = $env:MUSICIA_IDENTITY_PIDS | ConvertFrom-Json
$rows = @{}
foreach ($entry in $ids.PSObject.Properties) {
    $process = Get-CimInstance Win32_Process -Filter "ProcessId = $($entry.Value)"
    if (-not $process) { throw "Fixture process absent: $($entry.Name)" }
    $rows[$entry.Name] = [pscustomobject]@{
        ProcessId = $process.ProcessId
        CreationDate = $process.CreationDate
        ExecutablePath = $process.ExecutablePath
        CommandLine = $process.CommandLine
    }
}
$own = $rows.own
$mutated = @{}
foreach ($field in @('ProcessId', 'CreationDate', 'ExecutablePath', 'CommandLine')) {
    $changed = $own | Select-Object *
    switch ($field) {
        'ProcessId' { $changed.ProcessId = [int]$own.ProcessId + 1 }
        'CreationDate' { $changed.CreationDate = $own.CreationDate.AddSeconds(1) }
        'ExecutablePath' { $changed.ExecutablePath = Join-Path $env:MUSICIA_IDENTITY_FOREIGN 'python.exe' }
        'CommandLine' { $changed.CommandLine = $own.CommandLine + ' changed-argument' }
    }
    $mutated[$field] = Test-MusiciaApiProcessSnapshot $own $changed $root
}
$incomplete = @{}
foreach ($field in @('CreationDate', 'ExecutablePath', 'CommandLine')) {
    $changed = $own | Select-Object *
    $changed.$field = $null
    $incomplete[$field] = Test-MusiciaApiProcessSnapshot $own $changed $root
}
[pscustomobject]@{
    owned = Test-MusiciaApiProcess $rows.own $root
    foreign = Test-MusiciaApiProcess $rows.foreign $root
    relative = Test-MusiciaApiProcess $rows.relative $root
    command = Test-MusiciaApiProcess $rows.command $root
    unchanged = Test-MusiciaApiProcessSnapshot $own $own $root
    without_u = Test-MusiciaApiCommandLine ($own.CommandLine.Replace(' -u ', ' ')) $root
    altered = $mutated
    incomplete = $incomplete
    executable_paths = @($rows.own.ExecutablePath, $rows.foreign.ExecutablePath)
    command_lines = @($rows.own.CommandLine, $rows.foreign.CommandLine,
        $rows.relative.CommandLine, $rows.command.CommandLine)
} | ConvertTo-Json -Depth 5 -Compress
"""


@unittest.skipUnless(os.name == "nt" and POWERSHELL, "requires Windows CIM and PowerShell")
class ApiProcessIdentityTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix="musicia API identity ")
        cls.addClassCleanup(cls.temporary.cleanup)
        root = Path(cls.temporary.name)
        cls.own = root / "Musicia project with spaces"
        cls.foreign = root / "Foreign project with spaces"
        for directory in (cls.own, cls.foreign):
            (directory / "backend").mkdir(parents=True)
            (directory / "backend" / "main.py").write_text(FIXTURE, encoding="utf-8")
        children = []

        def cleanup():
            # Signal and wait for the actual interpreters, including venv children;
            # terminating only the launcher would leave those children orphaned.
            for _process, ready in children:
                ready.with_suffix(".stop").write_text("stop", encoding="utf-8")
            for process, _ready in children:
                process.wait(timeout=10)

        cls.addClassCleanup(cleanup)
        entries = {}
        for label, directory, flags in (
            ("own", cls.own, ["-u", str(cls.own / "backend" / "main.py")]),
            ("foreign", cls.foreign, [str(cls.foreign / "backend" / "main.py")]),
            ("relative", cls.own, ["backend/main.py"]),
            ("command", cls.own, ["-c", FIXTURE, str(cls.own / "backend" / "main.py")]),
        ):
            ready = root / (label + ".ready")
            process = subprocess.Popen(
                [sys.executable, *flags, str(ready)], cwd=directory,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            children.append((process, ready))
            deadline = time.monotonic() + 10
            while not ready.exists():
                if process.poll() is not None or time.monotonic() > deadline:
                    raise RuntimeError(f"Actual identity fixture failed to become ready: {label}")
                time.sleep(0.03)
            entries[label] = process.pid
        environment = os.environ.copy()
        environment.update({
            "MUSICIA_IDENTITY_HELPER": str(ROOT / "scripts" / "api_identity.ps1"),
            "MUSICIA_IDENTITY_ROOT": str(cls.own),
            "MUSICIA_IDENTITY_FOREIGN": str(cls.foreign),
            "MUSICIA_IDENTITY_PIDS": json.dumps(entries),
        })
        result = subprocess.run(
            [POWERSHELL, "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", PREDICATE_HARNESS],
            env=environment, capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=30, creationflags=subprocess.CREATE_NO_WINDOW,
        )
        if result.returncode:
            raise RuntimeError(result.stdout + result.stderr)
        cls.report = json.loads(result.stdout)

    def test_absolute_script_in_the_own_root_is_identified(self):
        self.assertTrue(self.report["owned"], self.report)
        self.assertTrue(self.report["without_u"], self.report)

    def test_other_root_using_the_same_interpreter_is_preserved(self):
        self.assertEqual(*self.report["executable_paths"])
        self.assertFalse(self.report["foreign"], self.report)

    def test_legacy_relative_script_is_not_adopted(self):
        self.assertFalse(self.report["relative"], self.report)

    def test_a_path_after_python_c_does_not_establish_ownership(self):
        self.assertFalse(self.report["command"], self.report)

    def test_an_unchanged_real_cim_snapshot_matches(self):
        self.assertTrue(self.report["unchanged"], self.report)

    def test_reused_pid_or_changed_identity_is_rejected(self):
        for field, result in self.report["altered"].items():
            with self.subTest(field=field):
                self.assertFalse(result, self.report)

    def test_unknown_snapshot_fields_are_preserved(self):
        for field, result in self.report["incomplete"].items():
            with self.subTest(field=field):
                self.assertFalse(result, self.report)


if __name__ == "__main__":
    unittest.main()
