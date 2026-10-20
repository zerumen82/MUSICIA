"""Production FastAPI integration for lazy engine start and request leases."""

import asyncio
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock

import httpx

BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import main
from engine_lifecycle import EngineLifecycleMiddleware
from music_service import GenerationRequest


class EngineLifecycleProductionIntegrationTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.lifecycle = main.engine_lifecycle
        self._lifecycle_callbacks = (
            self.lifecycle._wake, self.lifecycle._pause, self.lifecycle._enabled,
        )
        self.actions = []
        self.background_started = asyncio.Queue()
        self.pause_finished = asyncio.Event()
        self._originals = {}

        async def wake():
            self.actions.append("wake")

        async def pause():
            self.actions.append("pause")
            self.pause_finished.set()

        self.lifecycle._enabled = True
        self.lifecycle._activated = False
        self.lifecycle._awake = False
        self.lifecycle._touched = False
        self.lifecycle._operations = 0
        self.lifecycle._state = "inactive"
        self.lifecycle._error = None
        self.lifecycle._wake = wake
        self.lifecycle._pause = pause
        self._replace(main.music, "start", AsyncMock())
        self._replace(main.music, "aclose", AsyncMock())
        self._replace(main, "_save_history", lambda: None)
        self._replace(main, "_gpu_busy", lambda: None)
        self._replace(
            main, "_engine_control",
            AsyncMock(return_value=json.dumps({"state": "idle"})),
        )
        self._old_jobs = dict(main.jobs)
        main.jobs.clear()
        self._old_admission = main._ADMIT_GENERATION
        main._ADMIT_GENERATION = asyncio.Lock()

        self._lifespan = main.app.router.lifespan_context(main.app)
        await self._lifespan.__aenter__()
        self.client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=main.app),
            base_url="http://testserver",
        )

    def _replace(self, target, name, value):
        self._originals.setdefault((target, name), getattr(target, name))
        setattr(target, name, value)

    async def asyncTearDown(self):
        await self.client.aclose()
        await self._lifespan.__aexit__(None, None, None)
        self.lifecycle._wake, self.lifecycle._pause, self.lifecycle._enabled = (
            self._lifecycle_callbacks
        )
        for (target, name), value in self._originals.items():
            setattr(target, name, value)
        main.jobs.clear()
        main.jobs.update(self._old_jobs)
        main._ADMIT_GENERATION = self._old_admission

    def install_generation(self, submit, finalize):
        self._replace(
            main, "_prepare_generation",
            lambda _request: (
                GenerationRequest(prompt="integration"),
                {"effective_parameters": {}, "provenance": {}, "warnings": []},
            ),
        )
        self._replace(main.music, "health", AsyncMock(return_value={"reachable": True}))
        self._replace(main.music, "submit", submit)
        self._replace(main, "_finalize_generation", finalize)

    async def post_generation(self, output_name="integration"):
        return await self.client.post(
            "/music/generate",
            json={"prompt": "integration test", "output_name": output_name},
        )

    async def test_successful_background_work_holds_lease_and_next_request_wakes_once(self):
        finish = asyncio.Event()

        async def submit(_generation):
            return "task-1", "queued"

        async def finalize(job_id):
            self.background_started.put_nowait(job_id)
            await finish.wait()

        self.install_generation(submit, finalize)
        request = asyncio.create_task(self.post_generation())
        await asyncio.wait_for(self.background_started.get(), timeout=3)
        self.assertEqual(self.actions, ["wake"])
        self.assertEqual(self.lifecycle.operation_count, 1)
        finish.set()
        response = await asyncio.wait_for(request, timeout=3)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.actions, ["wake", "pause"])
        self.assertEqual(self.lifecycle.state, "idle")

        self._replace(main, "_finalize_generation", AsyncMock())
        next_response = await self.post_generation("second")
        self.assertEqual(next_response.status_code, 200)
        self.assertEqual(self.actions, ["wake", "pause", "wake", "pause"])

    async def test_submit_failure_releases_engine_and_returns_error(self):
        async def submit(_generation):
            raise RuntimeError("engine rejected request")

        async def finalize(_job_id):
            self.fail("failed submit must not schedule finalization")

        self.install_generation(submit, finalize)
        response = await self.post_generation()
        self.assertEqual(response.status_code, 503)
        self.assertEqual(self.actions, ["wake", "pause"])
        self.assertEqual(self.lifecycle.state, "idle")

    async def test_cancelled_asgi_request_waits_for_cleanup(self):
        finish = asyncio.Event()

        async def submit(_generation):
            return "task-cancel", "queued"

        async def finalize(job_id):
            self.background_started.put_nowait(job_id)
            await finish.wait()

        self.install_generation(submit, finalize)
        request = asyncio.create_task(self.post_generation())
        await asyncio.wait_for(self.background_started.get(), timeout=3)
        request.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await request
        await asyncio.wait_for(self.pause_finished.wait(), timeout=3)
        self.assertEqual(self.actions, ["wake", "pause"])
        self.assertEqual(self.lifecycle.operation_count, 0)
        self.assertEqual(self.lifecycle.state, "idle")

    async def test_cancel_endpoint_does_not_interrupt_other_engine_lease(self):
        finish = asyncio.Event()

        async def submit(_generation):
            return "task-stop", "queued"

        async def finalize(job_id):
            self.background_started.put_nowait(job_id)
            await finish.wait()

        self.install_generation(submit, finalize)
        request = asyncio.create_task(self.post_generation())
        job_id = await asyncio.wait_for(self.background_started.get(), timeout=3)
        cancelled = await self.client.post(f"/music/jobs/{job_id}/cancel")
        self.assertEqual(cancelled.status_code, 200)
        self.assertIn("se detendrá", cancelled.json()["note"])
        self.assertEqual(self.actions, ["wake"])
        self.assertEqual(self.lifecycle.operation_count, 1)

        finish.set()
        self.assertEqual((await asyncio.wait_for(request, timeout=3)).status_code, 200)
        self.assertEqual(self.actions, ["wake", "pause"])

    async def test_concurrent_jobs_share_wake_and_only_last_completion_pauses(self):
        release = {}

        async def submit(_generation):
            return f"task-{len(release) + 1}", "queued"

        async def finalize(job_id):
            release[job_id] = asyncio.Event()
            self.background_started.put_nowait(job_id)
            await release[job_id].wait()

        self.install_generation(submit, finalize)
        first = asyncio.create_task(self.post_generation("first"))
        second = asyncio.create_task(self.post_generation("second"))
        first_job, second_job = await asyncio.wait_for(
            asyncio.gather(self.background_started.get(), self.background_started.get()),
            timeout=3,
        )
        self.assertEqual(self.actions, ["wake"])
        self.assertEqual(self.lifecycle.operation_count, 2)

        release[first_job].set()
        done, pending = await asyncio.wait(
            {first, second}, return_when=asyncio.FIRST_COMPLETED, timeout=3,
        )
        self.assertEqual(len(done), 1)
        completed = done.pop()
        remaining = pending.pop()
        self.assertEqual((await completed).status_code, 200)
        self.assertEqual(self.actions, ["wake"])
        self.assertEqual(self.lifecycle.operation_count, 1)

        release[second_job].set()
        self.assertEqual((await asyncio.wait_for(remaining, timeout=3)).status_code, 200)
        self.assertEqual(self.actions, ["wake", "pause"])
        self.assertEqual(self.lifecycle.operation_count, 0)

    async def test_idle_health_model_poll_and_invalid_request_do_not_wake(self):
        self._replace(
            main.music, "health",
            AsyncMock(side_effect=AssertionError("idle health must not poll ACE-Step")),
        )
        self._replace(
            main.music, "engine_info",
            AsyncMock(side_effect=AssertionError("idle model polling must not query ACE-Step")),
        )
        self._replace(
            main.music, "list_models",
            AsyncMock(side_effect=AssertionError("idle model polling must not query ACE-Step")),
        )
        self._replace(
            main, "_prepare_generation",
            lambda _request: (
                GenerationRequest(prompt="preview"),
                {"effective_parameters": {}, "provenance": {}, "warnings": []},
            ),
        )
        health = await self.client.get("/health")
        models = await self.client.get("/music/models")
        invalid = await self.client.post("/music/generate", json={})
        preview = await self.client.post("/music/preview", json={"prompt": "preview"})
        self.assertEqual(health.status_code, 200)
        self.assertEqual(health.json()["engine_lifecycle"]["state"], "idle")
        self.assertEqual(models.status_code, 200)
        self.assertTrue(models.json()["idle"])
        self.assertEqual(invalid.status_code, 422)
        self.assertEqual(preview.status_code, 200)
        self.assertEqual(self.actions, [])
        self.assertEqual(self.lifecycle.operation_count, 0)

    async def test_api_restart_reconciles_surviving_engine_as_not_idle(self):
        await self._lifespan.__aexit__(None, None, None)
        self._replace(
            main, "_engine_control",
            AsyncMock(return_value=json.dumps({"state": "awake", "process_id": 8421})),
        )
        self._lifespan = main.app.router.lifespan_context(main.app)
        await self._lifespan.__aenter__()
        self._replace(
            main.music, "health", AsyncMock(return_value={"reachable": True}),
        )

        response = await self.client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["engine_lifecycle"]["state"], "awake")
        self.assertNotIn("idle", response.json()["engine"])
        self.assertEqual(self.lifecycle.operation_count, 0)
        self._replace(main.music, "engine_info", AsyncMock(return_value={}))
        self._replace(main.music, "list_models", AsyncMock(return_value=[]))
        self._replace(main, "free_vram_mb", lambda: None)
        model_response = await self.client.get("/music/models")
        self.assertEqual(model_response.status_code, 200)
        self.assertEqual(self.actions, [])
        self.assertEqual(self.lifecycle.state, "awake")

    async def test_reachable_health_does_not_adopt_an_unverified_engine(self):
        self._replace(
            main, "_engine_control",
            AsyncMock(return_value=json.dumps({"state": "reconciling"})),
        )
        self._replace(
            main.music, "health", AsyncMock(return_value={"reachable": True}),
        )
        self.lifecycle.reconcile("reconciling")

        response = await self.client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["engine_lifecycle"]["state"], "reconciling")

    async def test_unreachable_health_keeps_verified_starting_engine_retryable(self):
        self.lifecycle.reconcile("awake")
        self._replace(
            main.music, "health", AsyncMock(return_value={"reachable": False}),
        )
        self._replace(
            main, "_engine_control",
            AsyncMock(return_value=json.dumps({"state": "starting", "process_id": 8421})),
        )

        response = await self.client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["engine_lifecycle"]["state"], "starting")

    async def test_project_remix_path_is_leased_until_background_returns(self):
        observations = []

        async def downstream(scope, receive, send):
            observations.append(self.lifecycle.in_operation)
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b"ok"})

        middleware = EngineLifecycleMiddleware(
            downstream, self.lifecycle, main.ENGINE_OPERATION_PATHS,
        )

        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}

        async def send(_message):
            return None

        await middleware({
            "type": "http", "method": "POST", "path": "/music/remix/project",
            "headers": [], "query_string": b"",
        }, receive, send)

        self.assertEqual(observations, [True])
        self.assertEqual(self.lifecycle.operation_count, 0)
        self.assertEqual(self.actions, [])


if __name__ == "__main__":
    unittest.main()
