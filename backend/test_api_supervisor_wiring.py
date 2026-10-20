"""ensure_local.ps1 solo reemplaza una API viva con código viejo al arrancar.

Regresión del 2026-10-19: relanzar Musicia dejaba el proceso de la API de
las 07:14 sirviendo código antiguo (el filtro WQL de open_musicia.ps1 no
mataba nada y ensure_local solo reponía la API cuando el puerto dejaba de
aceptar). El AST de PowerShell suministra el bloque real de decisión del
`if ($apiArriba)` y las dos funciones de edad reales; solo se aislan los
actuadores (taskkill.exe, Get-Process, Start-Servicio, Find-Python) y los
datos de proceso. El intérprete real ejecuta api_supervisor.api_is_stale
sobre una copia del backend con mtimes controlados.

Escenarios: -Rearme reemplaza la API obsoleta; sin -Rearme (vigilante de
la ventana), sin procesos identificables o sin python de la API, nunca se
mata nada.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
POWERSHELL = shutil.which("pwsh") or shutil.which("powershell")

API_HARNESS = r"""
$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $false
$tokens = $null
$parseErrors = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile(
    $env:MUSICIA_TEST_SUPERVISOR, [ref]$tokens, [ref]$parseErrors)
if ($parseErrors.Count) { throw ($parseErrors | Out-String) }

# Import the actual age helpers, without executing the launcher's top-level code.
foreach ($name in @('Get-OldestApiAgeSeconds', 'Get-NewestApiSourceAgeSeconds')) {
    $definition = @($ast.FindAll({
        param($node)
        $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and
            $node.Name -eq $name
    }, $true))
    if ($definition.Count -ne 1) { throw "Expected one production helper: $name" }
    . ([scriptblock]::Create($definition[0].Extent.Text))
}

# The production API admission chain: if ($apiArriba) { ... } elseif ... else ...
$admission = @($ast.FindAll({
    param($node)
    $node -is [System.Management.Automation.Language.IfStatementAst] -and
        $node.Clauses.Count -gt 0 -and
        $node.Clauses[0].Item1.Extent.Text -eq '$apiArriba'
}, $true))
if ($admission.Count -ne 1) { throw 'Expected one production API admission boundary' }
$source = $admission[0].Extent.Text

$script:actions = [System.Collections.Generic.List[string]]::new()
$script:apiAlive = $true
function Find-Python([string]$filter) { @() }
function Start-Sleep([int]$Milliseconds) {}
function Get-Process([int]$Id, [string]$ErrorAction) {
    if ($script:apiAlive -and $Id -eq 24680) { return [pscustomobject]@{ Id = $Id } }
}
function taskkill.exe { $script:apiAlive = $false; $script:actions.Add("kill:$($args[1])") }
function Start-Servicio(
    [string]$etiqueta, [string]$python, [string[]]$argumentos,
    [string]$cwd, [string]$salida, [string]$errorLog
) { $script:actions.Add("start:$etiqueta") }

$apiArriba = $env:MUSICIA_TEST_API_UP -eq '1'
$apiPort = $true
$apiPy = 'Z:\musicia-supervisor-no-api-python.exe'
if ($env:MUSICIA_TEST_API_PY) { $apiPy = $env:MUSICIA_TEST_API_PY }
$apiArgs = @('backend\main.py')
$apiOut = 'virtual-api.log'
$apiErr = 'virtual-api.err.log'
$raiz = $env:MUSICIA_TEST_RAIZ
$Rearme = $env:MUSICIA_TEST_REARM -eq '1'
$procAge = 0.0
if ($env:MUSICIA_TEST_PROC_AGE) { $procAge = [double]$env:MUSICIA_TEST_PROC_AGE }
$apiProcs = @()
if ($env:MUSICIA_TEST_API_PROCS -eq '1') {
    $apiProcs = @([pscustomobject]@{
        ProcessId = 24680
        CreationDate = (Get-Date).AddSeconds(-$procAge)
    })
}
$output = @(. ([scriptblock]::Create($source)))
[pscustomobject]@{
    actions = @($script:actions.ToArray())
    output = $output
} | ConvertTo-Json -Depth 5 -Compress
"""


@unittest.skipUnless(os.name == "nt" and POWERSHELL, "requiere Windows con PowerShell")
class ApiRefreshWiringTest(unittest.TestCase):
    STALE_PROCESS_SECONDS = 3600.0
    STALE_SOURCE_SECONDS = 10.0
    FRESH_PROCESS_SECONDS = 10.0
    FRESH_SOURCE_SECONDS = 3600.0

    def api_root(self, source_age_seconds: float) -> Path:
        """Copia real de api_supervisor.py + un main.py, con mtimes controlados."""
        root = Path(tempfile.mkdtemp(prefix="musicia-api-wiring-"))
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        backend = root / "backend"
        backend.mkdir()
        shutil.copy(ROOT / "backend" / "api_supervisor.py", backend / "api_supervisor.py")
        (backend / "main.py").write_text("# fixture\n", encoding="utf-8")
        write = time.time() - source_age_seconds
        for item in backend.glob("*.py"):
            os.utime(item, (write, write))
        return root

    def refresh(
        self, *, stale_source, stale_process, rearm=True, procs=True, api_python=True,
    ):
        root = self.api_root(
            self.STALE_SOURCE_SECONDS if stale_source else self.FRESH_SOURCE_SECONDS
        )
        environment = os.environ.copy()
        environment.update({
            "MUSICIA_TEST_SUPERVISOR": str(ROOT / "scripts" / "ensure_local.ps1"),
            "MUSICIA_TEST_RAIZ": str(root),
            "MUSICIA_TEST_API_UP": "1",
            "MUSICIA_TEST_REARM": "1" if rearm else "0",
            "MUSICIA_TEST_API_PROCS": "1" if procs else "0",
            "MUSICIA_TEST_PROC_AGE": str(
                self.STALE_PROCESS_SECONDS if stale_process else self.FRESH_PROCESS_SECONDS
            ),
            "MUSICIA_TEST_API_PY": sys.executable if api_python else "",
        })
        result = subprocess.run(
            [POWERSHELL, "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", API_HARNESS],
            env=environment, capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=30, creationflags=subprocess.CREATE_NO_WINDOW,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(result.stdout.strip(), result.stderr)
        try:
            return json.loads(result.stdout.strip())
        except json.JSONDecodeError as exc:
            self.fail(f"Invalid api harness output: {result.stdout!r} {result.stderr!r}: {exc}")

    def test_launch_replaces_a_stale_responsive_api(self):
        report = self.refresh(stale_source=True, stale_process=True, rearm=True)
        self.assertEqual(report["output"], ["API=refreshed"])
        self.assertEqual(report["actions"], ["kill:24680", "start:API"])

    def test_launch_keeps_an_api_that_already_serves_current_code(self):
        report = self.refresh(stale_source=False, stale_process=False, rearm=True)
        self.assertEqual(report["output"], ["API=up"])
        self.assertEqual(report["actions"], [])

    def test_the_window_watchdog_never_replaces_a_responsive_api(self):
        # Sin -Rearme no se decide nada, aunque el código sea muy posterior:
        # el vigilante no mata trabajos en curso.
        report = self.refresh(stale_source=True, stale_process=True, rearm=False)
        self.assertEqual(report["output"], ["API=up"])
        self.assertEqual(report["actions"], [])

    def test_without_identifiable_processes_nothing_is_killed(self):
        report = self.refresh(stale_source=True, stale_process=True, rearm=True, procs=False)
        self.assertEqual(report["output"], ["API=up"])
        self.assertEqual(report["actions"], [])

    def test_without_the_api_interpreter_nothing_is_killed(self):
        # Ante la duda (no se puede evaluar ni reponer) se conserva el proceso.
        report = self.refresh(
            stale_source=True, stale_process=True, rearm=True, api_python=False,
        )
        self.assertEqual(report["output"], ["API=up"])
        self.assertEqual(report["actions"], [])


if __name__ == "__main__":
    unittest.main()
