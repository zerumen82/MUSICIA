"""CPU verification of leases, ASGI background lifetime and lifecycle failures."""

import asyncio
import sys
import unittest
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from engine_lifecycle import EngineLifecycle, EngineLifecycleMiddleware
from starlette.applications import Starlette
from starlette.background import BackgroundTask
from starlette.responses import JSONResponse
from starlette.routing import Route


class EngineLifecycleTest(unittest.IsolatedAsyncioTestCase):
    def make_lifecycle(self, *, enabled=True, activate=True):
        self.actions = []

        async def wake():
            self.actions.append("wake")

        async def pause():
            self.actions.append("pause")

        lifecycle = EngineLifecycle(enabled=enabled, wake=wake, pause=pause)
        if activate:
            lifecycle.activate()
        return lifecycle

    async def test_activation_waits_for_supervisor_reconciliation(self):
        lifecycle = self.make_lifecycle(activate=False)
        lifecycle.activate()
        self.assertEqual(lifecycle.state, "reconciling")

        lifecycle.reconcile("awake")

        self.assertEqual(lifecycle.state, "awake")
        self.assertEqual(lifecycle.operation_count, 0)
        with self.assertRaisesRegex(ValueError, "Invalid engine lifecycle state"):
            lifecycle.reconcile("idle-ish")

    async def test_passive_lease_does_not_pause_an_adopted_engine(self):
        lifecycle = self.make_lifecycle()
        lifecycle.reconcile("awake")

        async with lifecycle.operation():
            self.assertEqual(lifecycle.state, "awake")
            self.assertEqual(self.actions, [])

        self.assertEqual(self.actions, [])
        async with lifecycle.operation():
            await lifecycle.ensure_awake()
        self.assertEqual(self.actions, ["pause"])

    async def test_overlapping_operations_wake_once_and_last_one_releases(self):
        lifecycle = self.make_lifecycle()
        first_ready, second_ready = asyncio.Event(), asyncio.Event()
        finish_first, finish_second = asyncio.Event(), asyncio.Event()

        async def operation(ready, finish):
            async with lifecycle.operation():
                await lifecycle.ensure_awake()
                ready.set()
                await finish.wait()

        first = asyncio.create_task(operation(first_ready, finish_first))
        await first_ready.wait()
        second = asyncio.create_task(operation(second_ready, finish_second))
        await second_ready.wait()
        self.assertEqual(lifecycle.operation_count, 2)
        self.assertEqual(self.actions, ["wake"])
        finish_first.set()
        await first
        self.assertEqual(self.actions, ["wake"])
        finish_second.set()
        await second
        self.assertEqual(self.actions, ["wake", "pause"])
        self.assertEqual(lifecycle.state, "idle")
        self.assertEqual(lifecycle.operation_count, 0)

    async def test_next_operation_waits_for_pause_then_wakes_again(self):
        actions = []
        stopping, allow_stop, next_started = (
            asyncio.Event(), asyncio.Event(), asyncio.Event()
        )

        async def wake():
            actions.append("wake")

        async def pause():
            actions.append("pause_start")
            stopping.set()
            await allow_stop.wait()
            actions.append("pause_end")

        lifecycle = EngineLifecycle(enabled=True, wake=wake, pause=pause)
        lifecycle.activate()

        async def run_first():
            async with lifecycle.operation():
                await lifecycle.ensure_awake()

        async def run_next():
            next_started.set()
            async with lifecycle.operation():
                await lifecycle.ensure_awake()
                actions.append("next")

        first = asyncio.create_task(run_first())
        await stopping.wait()
        self.assertEqual(lifecycle.state, "stopping")
        second = asyncio.create_task(run_next())
        await next_started.wait()
        self.assertEqual(actions, ["wake", "pause_start"])
        allow_stop.set()
        await asyncio.gather(first, second)
        self.assertEqual(actions, [
            "wake", "pause_start", "pause_end", "wake", "next",
            "pause_start", "pause_end",
        ])

    async def test_cancelled_operation_releases_and_preserves_cancellation(self):
        lifecycle = self.make_lifecycle()
        started = asyncio.Event()

        async def run():
            async with lifecycle.operation():
                await lifecycle.ensure_awake()
                started.set()
                await asyncio.Event().wait()

        task = asyncio.create_task(run())
        await started.wait()
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertEqual(self.actions, ["wake", "pause"])
        self.assertEqual(lifecycle.operation_count, 0)

    async def test_cancellation_during_pause_still_waits_for_cleanup(self):
        stopping, finish = asyncio.Event(), asyncio.Event()
        actions = []

        async def wake():
            actions.append("wake")

        async def pause():
            stopping.set()
            await finish.wait()
            actions.append("pause")

        lifecycle = EngineLifecycle(enabled=True, wake=wake, pause=pause)
        lifecycle.activate()

        async def run():
            async with lifecycle.operation():
                await lifecycle.ensure_awake()

        task = asyncio.create_task(run())
        await stopping.wait()
        task.cancel()
        await asyncio.sleep(0)
        self.assertFalse(task.done())
        finish.set()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertEqual(actions, ["wake", "pause"])
        self.assertEqual(lifecycle.state, "idle")

    async def test_failed_pause_preserves_original_error_and_reports_state(self):
        lifecycle = self.make_lifecycle()

        async def fail_pause():
            raise RuntimeError("process still exists")

        lifecycle._pause = fail_pause
        original = ValueError("generation failed")
        with self.assertRaises(ValueError) as caught:
            async with lifecycle.operation():
                await lifecycle.ensure_awake()
                raise original
        self.assertIs(caught.exception, original)
        self.assertEqual(lifecycle.state, "error")
        self.assertIn("process still exists", lifecycle.error)
        self.assertEqual(lifecycle.operation_count, 0)

    async def test_failed_pause_is_not_reported_as_idle_on_successful_body(self):
        lifecycle = self.make_lifecycle()

        async def fail_pause():
            raise RuntimeError("cannot stop engine")

        lifecycle._pause = fail_pause
        with self.assertRaisesRegex(RuntimeError, "cannot stop engine"):
            async with lifecycle.operation():
                await lifecycle.ensure_awake()
        self.assertEqual(lifecycle.state, "error")

    async def test_failed_start_attempts_cleanup_and_next_cycle_can_retry(self):
        lifecycle = self.make_lifecycle()

        async def fail_start():
            self.actions.append("partial_wake")
            raise RuntimeError("readiness failed")

        lifecycle._wake = fail_start
        with self.assertRaisesRegex(RuntimeError, "readiness failed"):
            async with lifecycle.operation():
                await lifecycle.ensure_awake()
        self.assertEqual(self.actions, ["partial_wake", "pause"])
        self.assertEqual(lifecycle.state, "error")
        self.assertIn("readiness failed", lifecycle.error)

        async def successful_wake():
            self.actions.append("wake")

        lifecycle._wake = successful_wake
        async with lifecycle.operation():
            await lifecycle.ensure_awake()
            self.assertIsNone(lifecycle.error)
        self.assertEqual(lifecycle.state, "idle")

    async def test_lease_without_use_does_not_wake_or_pause(self):
        lifecycle = self.make_lifecycle()
        async with lifecycle.operation():
            self.assertTrue(lifecycle.in_operation)
        self.assertFalse(lifecycle.in_operation)
        self.assertEqual(self.actions, [])

    async def test_health_call_outside_operation_cannot_wake(self):
        lifecycle = self.make_lifecycle()
        with self.assertRaisesRegex(RuntimeError, "inside an operation"):
            await lifecycle.ensure_awake()
        self.assertEqual(self.actions, [])

    async def test_detached_child_cannot_reuse_finished_request_lease(self):
        lifecycle = self.make_lifecycle()
        parent_finished = asyncio.Event()

        async def detached_child():
            await parent_finished.wait()
            self.assertFalse(lifecycle.in_operation)
            with self.assertRaisesRegex(RuntimeError, "inside an operation"):
                await lifecycle.ensure_awake()

        async with lifecycle.operation():
            child = asyncio.create_task(detached_child())
        parent_finished.set()
        await child
        self.assertEqual(self.actions, [])

    async def test_disabled_or_not_activated_lifecycle_bypasses_callbacks(self):
        for options in ({"enabled": False}, {"activate": False}):
            lifecycle = self.make_lifecycle(**options)
            async with lifecycle.operation():
                await lifecycle.ensure_awake()
            self.assertEqual(self.actions, [])
            self.assertEqual(lifecycle.state, "inactive")


class EngineLifecycleASGITest(unittest.IsolatedAsyncioTestCase):
    async def test_response_download_and_background_finish_before_release(self):
        actions = []
        download_started, allow_download = asyncio.Event(), asyncio.Event()
        body_sent, allow_background = asyncio.Event(), asyncio.Event()

        async def wake():
            actions.append("wake")

        async def pause():
            actions.append("pause")

        lifecycle = EngineLifecycle(enabled=True, wake=wake, pause=pause)
        lifecycle.activate()

        async def download_and_finish():
            download_started.set()
            await allow_download.wait()
            actions.append("download")
            await allow_background.wait()
            actions.append("background_end")

        async def endpoint(request):
            await lifecycle.ensure_awake()
            return JSONResponse({"accepted": True}, background=BackgroundTask(
                download_and_finish,
            ))

        app = EngineLifecycleMiddleware(
            Starlette(routes=[Route("/generate", endpoint, methods=["POST"])]),
            lifecycle, ("/generate",),
        )

        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}

        async def send(message):
            if message["type"] == "http.response.body":
                body_sent.set()

        task = asyncio.create_task(app({
            "type": "http", "method": "POST", "path": "/generate",
            "headers": [], "query_string": b"",
        }, receive, send))
        await body_sent.wait()
        await download_started.wait()
        self.assertEqual(actions, ["wake"])
        allow_download.set()
        await asyncio.sleep(0)
        self.assertEqual(actions, ["wake", "download"])
        self.assertEqual(lifecycle.operation_count, 1)
        allow_background.set()
        await task
        self.assertEqual(actions, ["wake", "download", "background_end", "pause"])

    async def test_only_configured_post_is_leased_and_invalid_request_does_not_wake(self):
        observations = []

        async def forbidden_callback():
            self.fail("an unused request must not start or stop the engine")

        lifecycle = EngineLifecycle(
            enabled=True, wake=forbidden_callback, pause=forbidden_callback,
        )
        lifecycle.activate()

        async def app(scope, receive, send):
            observations.append((scope["method"], scope["path"], lifecycle.in_operation))
            await send({"type": "http.response.start", "status": 422, "headers": []})
            await send({"type": "http.response.body", "body": b"invalid"})

        wrapped = EngineLifecycleMiddleware(app, lifecycle, ("/generate",))

        async def receive():
            return {"type": "http.request", "body": b""}

        async def send(message):
            pass

        for method, path in (("GET", "/generate"), ("POST", "/other"),
                             ("GET", "/health"), ("POST", "/generate")):
            await wrapped({"type": "http", "method": method, "path": path}, receive, send)
        self.assertEqual(observations, [
            ("GET", "/generate", False), ("POST", "/other", False),
            ("GET", "/health", False), ("POST", "/generate", True),
        ])
        self.assertEqual(lifecycle.operation_count, 0)


if __name__ == "__main__":
    unittest.main()
