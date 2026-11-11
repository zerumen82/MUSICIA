"""Retry the production control coroutine against a real, private Windows mutex.

The temporary supervisor performs actual IPC acquisition; it never claims an
engine was started. The holder and control processes are owned by this test.
"""
import ast
import asyncio
from pathlib import Path
import subprocess
from types import SimpleNamespace
import tempfile
import time
import unittest
import uuid

CONTROL_SOURCE = Path(__file__).with_name("main.py")


@unittest.skipUnless(__import__("os").name == "nt", "Windows supervisor control")
class EngineControlContentionTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="musicia-control-ipc-")
        self.root = Path(self.temp.name)
        (self.root / "scripts").mkdir()
        self.mutex = "Local\\MusiciaControlTest-" + uuid.uuid4().hex
        self.ready = self.root / "ready"
        self.attempts = self.root / "attempts"
        self.mode = self.root / "mode"
        self.holder = None
        source = CONTROL_SOURCE.read_text(encoding="utf-8-sig")
        definition = next(node for node in ast.parse(source).body
                          if isinstance(node, ast.AsyncFunctionDef) and node.name == "_engine_control")
        settings = SimpleNamespace(acestep=SimpleNamespace(
            lifecycle_start_timeout_seconds=8.0, lifecycle_stop_timeout_seconds=8.0,
            poll_interval=0.05))
        self.namespace = dict(asyncio=asyncio, subprocess=subprocess, tempfile=tempfile,
                              time=time, PROJECT_ROOT=self.root, settings=settings)
        exec(compile(ast.Module(body=[definition], type_ignores=[]), str(Path(__file__)), "exec"),
             self.namespace)
        self.control = self.namespace["_engine_control"]
        script = r"""param([switch]$WakeEngine,[switch]$IdleEngine,[int]$StartTimeoutSeconds,[int]$StopTimeoutSeconds)
Add-Content -LiteralPath '@ATTEMPTS@' -Value 'attempt'
if (Test-Path -LiteralPath '@MODE@') { [Console]::Error.WriteLine('real-control-error'); exit 3 }
$mutex = New-Object System.Threading.Mutex($false, '@MUTEX@')
$owned = $false
try {
    $owned = $mutex.WaitOne(100)
    if (-not $owned) { Write-Output 'BUSY'; exit 1 }
    Write-Output 'MUTEX=acquired'
} finally { if ($owned) { $mutex.ReleaseMutex() }; $mutex.Dispose() }
"""
        for marker, value in (("@ATTEMPTS@", str(self.attempts)), ("@MODE@", str(self.mode)),
                              ("@MUTEX@", self.mutex)):
            script = script.replace(marker, value.replace("'", "''"))
        (self.root / "scripts" / "ensure_local.ps1").write_text(script, encoding="utf-8")

    async def asyncTearDown(self):
        if self.holder is not None:
            if self.holder.poll() is None:
                self.holder.terminate()
            self.holder.wait(timeout=5)
        self.temp.cleanup()

    async def hold(self, milliseconds):
        script = ("$m=New-Object System.Threading.Mutex($false,'" + self.mutex + "');"
                  "$null=$m.WaitOne();try{[IO.File]::WriteAllText('" + str(self.ready) + "','held');"
                  "Start-Sleep -Milliseconds " + str(milliseconds) +
                  "}finally{$m.ReleaseMutex();$m.Dispose()}")
        self.holder = subprocess.Popen(["powershell.exe", "-NoProfile", "-Command", script],
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        deadline = time.monotonic() + 5
        while not self.ready.exists():
            if self.holder.poll() is not None or time.monotonic() > deadline:
                self.fail("Owned mutex holder did not become ready")
            await asyncio.sleep(0.02)

    async def test_busy_retries_until_actual_mutex_is_released(self):
        await self.hold(2200)
        result = await self.control("WakeEngine")
        self.assertEqual(result, "MUTEX=acquired")
        self.assertGreater(len(self.attempts.read_text().splitlines()), 1)
        self.assertEqual(self.holder.wait(timeout=5), 0)

    async def test_busy_does_not_reset_the_global_deadline(self):
        await self.hold(10000)
        self.namespace["settings"].acestep.lifecycle_stop_timeout_seconds = 1.5
        started = time.monotonic()
        with self.assertRaisesRegex(RuntimeError, "timeout|timed out"):
            await self.control("IdleEngine")
        self.assertLess(time.monotonic() - started, 3)

    async def test_other_real_errors_are_not_retried(self):
        self.mode.write_text("error", encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "exited 3: real-control-error"):
            await self.control("WakeEngine")
        self.assertEqual(len(self.attempts.read_text().splitlines()), 1)


if __name__ == "__main__":
    unittest.main()
