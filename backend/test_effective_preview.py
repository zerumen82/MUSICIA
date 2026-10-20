"""Regresiones del cierre R9/R10: preparación real, sin síntesis GPU."""
import asyncio
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from unittest.mock import AsyncMock

import httpx
from fastapi.testclient import TestClient
from pydub import AudioSegment

sys.path.insert(0, str(Path(__file__).resolve().parent))
import main
from config import AppSettings
from music_service import GenerationRequest, MusicEngineError, MusicService
from remix_project import RemixProjectRequest, project_generation


class ExplicitConflictTest(unittest.TestCase):
    def setUp(self):
        self.service = MusicService(AppSettings())

    def test_bpm_conflict_rejected_on_direct_build_payload(self):
        with self.assertRaisesRegex(MusicEngineError, "BPM"):
            self.service.build_payload(GenerationRequest(prompt="techno a 120 bpm", bpm=140))

    def test_explicit_voice_conflicts_rejected_including_discarded_lyrics(self):
        for request in (
            GenerationRequest(prompt="Canción sin voz", instrumental=False, lyrics="Letra cantada"),
            GenerationRequest(prompt="Techno", instrumental=True, lyrics="Letra cantada"),
            GenerationRequest(prompt="Con voz", instrumental=True),
        ):
            with self.subTest(request=request), self.assertRaises(MusicEngineError):
                self.service.build_payload(request)

    def test_meters_checked_and_api_numerator_supported(self):
        with self.assertRaisesRegex(MusicEngineError, "compás"):
            self.service.build_payload(GenerationRequest(prompt="Vals 3/4", time_signature="4"))
        self.service.build_payload(GenerationRequest(prompt="Vals 3/4", time_signature="3"))

    def test_partial_voice_exclusion_and_negated_bpm_not_misread(self):
        for prompt in ("Sin voz potente, con voz suave", "No instrumental, con voz", "No a 120 bpm, a 140 bpm"):
            payload = self.service.build_payload(GenerationRequest(
                prompt=prompt, instrumental=False, lyrics="Línea uno\nLínea dos", bpm=140))
            self.assertEqual(payload["prompt"], prompt)

    def test_source_voice_not_inferred_from_empty_lyrics(self):
        payload = self.service.build_payload(GenerationRequest(
            prompt="Sin voz potente", source_path="original.wav", task_type="cover"))
        self.assertEqual(payload["lyrics"], "")
        self.assertEqual(payload["audio_duration"], -1)

    def test_transport_json_matches_real_preview(self):
        captured = []
        request = GenerationRequest(prompt="techno 130 bpm", bpm=130, seed=324)
        preview = self.service.preview(request)

        async def check():
            def handle(http_request):
                captured.append(json.loads(http_request.content))
                return httpx.Response(200, json={"code": 200, "data": {"task_id": "test-transport"}})
            self.service._client = httpx.AsyncClient(base_url="http://engine-under-test",
                                                     transport=httpx.MockTransport(handle))
            try:
                await self.service.submit(request)
            finally:
                await self.service.aclose()
        asyncio.run(check())
        self.assertEqual(captured, [preview["effective_parameters"]])
        self.assertEqual(preview["provenance"]["bpm"], "request")
        self.assertEqual(preview["provenance"]["inference_steps"], "configuration")

    def test_real_seed_csv_assigned_per_variant_unknown_not_guessed(self):
        result = [{"file": "a.wav", "seed_value": "928,929"},
                  {"file": "b.wav", "seed_value": "928,929"}]
        tracks = self.service._parse_tracks(json.dumps(result))
        self.assertEqual([track["seed"] for track in tracks], [928, 929])
        self.assertEqual([track["seed_origin"] for track in tracks], ["engine.seed_value"] * 2)
        for entry in result:
            entry["seed_value"] = "928"
        self.assertEqual([track["seed"] for track in self.service._parse_tracks(result)], [None, None])

    def test_engine_error_is_not_lost_when_parsing_tracks(self):
        self.assertEqual(self.service._parse_tracks([{"error": "real failure"}])[0]["error"], "real failure")

    def test_repaint_resolution_matches_installed_engine_without_importing_gpu(self):
        import ast
        from config import PROJECT_ROOT

        source = PROJECT_ROOT / "vendor/ACE-Step-1.5/acestep/core/generation/handler/generate_music.py"
        tree = ast.parse(source.read_text(encoding="utf-8"))
        function = next(item for item in tree.body if isinstance(item, ast.FunctionDef)
                        and item.name == "_resolve_repaint_config")
        # Ejecutar solo la función pura del vendor, sin importar torch/GPU.
        namespace = {}
        exec(compile(ast.Module(body=[function], type_ignores=[]), str(source), "exec"), namespace)
        for mode in self.service.settings.remix.repaint_modes:
            for strength in (0.0, 0.5, 1.0):
                with self.subTest(mode=mode, strength=strength):
                    result = self.service.preview(GenerationRequest(
                        prompt="Cambio regional", task_type="repaint", source_path="original.wav",
                        repaint_start=1, repaint_end=2, repaint_mode=mode, repaint_strength=strength,
                        repaint_wav_crossfade_sec=0.8, repaint_latent_crossfade_frames=93))
                    _, frames, seconds = namespace["_resolve_repaint_config"](mode, strength)
                    self.assertEqual(result["effective_parameters"]["repaint_wav_crossfade_sec"], seconds)
                    self.assertEqual(result["effective_parameters"]["repaint_latent_crossfade_frames"], frames)
                    self.assertEqual(result["provenance"]["repaint_wav_crossfade_sec"], "engine_mode_strength_contract")


class PreviewApiTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="musicia-preview-")
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)
        AudioSegment.silent(duration=2000).export(self.folder / "original.wav", format="wav").close()
        patcher = patch.object(main.settings.paths, "outputs_dir", str(self.folder))
        patcher.start()
        self.addCleanup(patcher.stop)
        self.client = TestClient(main.app)

    def test_preview_no_job_and_defaults_equal_shared_preparer(self):
        before = dict(main.jobs)
        body = {"prompt": "Batería suave al fondo, 130 bpm", "bpm": 130}
        result = self.client.post("/music/preview", json=body)
        self.assertEqual(result.status_code, 200)
        generation, prepared = main._prepare_generation(main.MusicGenRequest(**body))
        self.assertEqual(result.json()["effective_parameters"], main.music.build_payload(generation))
        self.assertEqual(result.json(), prepared)
        self.assertEqual(main.jobs, before)

    def test_invalid_generation_never_creates_a_job(self):
        before = dict(main.jobs)
        for endpoint in ("/music/preview", "/music/generate"):
            response = self.client.post(endpoint, json={"prompt": "120 bpm", "bpm": 140})
            self.assertEqual(response.status_code, 422)
            self.assertIn("BPM", response.json()["detail"])
        self.assertEqual(main.jobs, before)

    def test_remix_preview_uses_original_source_and_repaint_contract(self):
        body = {"source_name": "original.wav", "source_kind": "output", "prompt": "Solo cambia percusión",
                "scope": "region", "region_start": 0.5, "region_end": 1.5, "seed": 23}
        response = self.client.post("/music/remix/preview", json=body)
        self.assertEqual(response.status_code, 200)
        result = response.json()
        generation = project_generation(RemixProjectRequest(**body), self.folder / "original.wav", None, main.settings)
        self.assertEqual(result["effective_parameters"], main.music.build_payload(generation))
        self.assertEqual(result["provenance"]["repaint_strength"], "configuration")
        self.assertEqual(result["operations"]["source_duration_seconds"], 2.0)

    def test_group_derived_material_is_pending_without_separation_or_jobs(self):
        before = dict(main.remix_jobs)
        body = {"source_name": "original.wav", "prompt": "Cambia la batería", "scope": "groups",
                "groups": {"vocals": "remove", "drums": "transform", "bass": "keep", "other": "keep"}}
        response = self.client.post("/music/remix/preview", json=body)
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertIsNone(result["effective_parameters"]["src_audio_path"])
        self.assertEqual(result["pending_material"][0]["groups"], ["drums"])
        self.assertEqual(main.remix_jobs, before)
        self.assertEqual(list(self.folder.iterdir()), [self.folder / "original.wav"])

    def test_deterministic_preview_omits_seed_and_engine(self):
        result = self.client.post("/music/remix/preview", json={
            "source_name": "original.wav", "scope": "groups", "seed": 47,
            "groups": {"vocals": "remove", "drums": "keep", "bass": "keep", "other": "keep"},
        }).json()
        self.assertEqual(result["effective_parameters"], {})
        self.assertFalse(result["operations"]["engine_required"])

    def test_invalid_remix_never_creates_a_job(self):
        before = dict(main.remix_jobs)
        response = self.client.post("/music/remix/project", json={
            "source_name": "original.wav", "prompt": "Techno 120 bpm", "bpm": 140})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(main.remix_jobs, before)

    def test_voice_base_preparation_respects_native_bpm_and_user_duration(self):
        request = main.AiRemixRequest(file_name="original.wav", prompt="Conserva la voz, techno", mode="voz", duration_seconds=240, seed=932)
        generation = main._prepare_ai_generation(request, self.folder / "original.wav", {"bpm": 128, "duration_seconds": 2})
        result = main.music.preview(generation)
        self.assertEqual(result["effective_parameters"]["bpm"], 128)
        self.assertEqual(result["effective_parameters"]["audio_duration"], 240)
        self.assertEqual(result["effective_parameters"]["lyrics"], main.settings.generation.instrumental_marker)
        self.assertEqual(result["effective_parameters"]["seed"], 932)
        self.assertFalse(result["effective_parameters"]["use_random_seed"])

    def test_unknown_generated_seed_does_not_inherit_source_seed_or_payload(self):
        source, target = self.folder / "original.wav", self.folder / "generated.wav"
        main._ficha_path(source).write_text(json.dumps({
            "seed": 77, "seed_origin": "engine.seed_value", "effective_parameters": {"prompt": "source"},
            "provenance": {"seed": "source-request"}}), encoding="utf-8")
        main._carry_ficha(source, target, "remix", seed=None, seed_origin="unknown",
                         effective_parameters={"prompt": "new"}, provenance={"seed": "configuration"})
        result = main._read_ficha(target)
        self.assertIsNone(result["seed"])
        self.assertEqual(result["seed_origin"], "unknown")
        self.assertEqual(result["effective_parameters"], {"prompt": "new"})
        self.assertEqual(result["source_generation"]["seed"], 77)
        main._carry_ficha(source, target, "dsp")
        result = main._read_ficha(target)
        self.assertIsNone(result["seed"])
        self.assertEqual(result["seed_origin"], "not_applicable")
        self.assertNotIn("effective_parameters", result)
        self.assertNotIn("provenance", result)


class AdmissionCancellationTest(unittest.TestCase):
    def _exercise_creation_cancel(self, phase):
        import time
        from fastapi import BackgroundTasks, HTTPException
        from music_service import EngineStatus, GeneratedTrack, STATUS_SUCCEEDED

        async def run(folder):
            import threading
            entered, release = asyncio.Event(), asyncio.Event()
            threaded_release = threading.Event()
            loop = asyncio.get_running_loop()
            job = {"job_id": "create-cleanup", "status": "queued", "compute_active": True,
                   "engine_active": True, "engine_task_id": "test-engine-task", "events": [],
                   "output_name": "created.mp3", "started": time.monotonic()}
            result = EngineStatus(task_id="test-engine-task", status=STATUS_SUCCEEDED,
                                  tracks=[GeneratedTrack(file="engine-audio.wav")])
            async def wait(*args, **kwargs):
                if phase == "wait":
                    entered.set()
                    await release.wait()
                return result
            async def download(*args):
                if phase == "download":
                    entered.set()
                    await release.wait()
            def measure(*args):
                if phase == "measure":
                    loop.call_soon_threadsafe(entered.set)
                    threaded_release.wait()
                return None
            with patch.object(main, "jobs", {job["job_id"]: job}), patch.object(main, "remix_jobs", {}), \
                    patch.object(main, "separate_jobs", {}), \
                    patch.object(main.settings.paths, "outputs_dir", folder), \
                    patch.object(main, "HISTORY_FILE", Path(folder) / "history.json"), \
                    patch.object(main.music, "wait", new=wait), patch.object(main.music, "download", new=download), \
                    patch.object(main.music, "verify_audio", new=AsyncMock(return_value=1000)), \
                    patch.object(main, "_measure_bpm", new=measure):
                task = asyncio.create_task(main._finalize_generation(job["job_id"]))
                await entered.wait()
                try:
                    self.assertTrue(job["compute_active"])
                    self.assertEqual(job["engine_active"], phase == "wait")
                    await main.cancel_job(job["job_id"])
                    self.assertEqual(job["status"], "failed")
                    with self.assertRaises(HTTPException) as caught:
                        await main.generate_music(main.MusicGenRequest(prompt="techno"), BackgroundTasks())
                    self.assertEqual(caught.exception.status_code, 409)
                finally:
                    release.set()
                    threaded_release.set()
                    await task
                self.assertEqual(job["status"], "failed")
                self.assertFalse(job["compute_active"])
                self.assertFalse(job["engine_active"])
                self.assertIsNone(main._gpu_busy())
        with tempfile.TemporaryDirectory(prefix="musicia-create-cancel-") as folder:
            asyncio.run(run(folder))

    def test_creation_cancel_waiting_restarts_engine_and_keeps_reservation(self):
        self._exercise_creation_cancel("wait")

    def test_creation_cancel_downloading_keeps_reservation_without_engine_restart(self):
        self._exercise_creation_cancel("download")

    def test_creation_cancel_during_measurement_never_overwrites_failed_with_success(self):
        self._exercise_creation_cancel("measure")

    def test_legacy_remix_rechecks_reservation_after_health_await(self):
        from fastapi import BackgroundTasks, HTTPException
        stores = {}
        async def health():
            stores["other"] = {"job_id": "other", "status": "queued"}
            await asyncio.sleep(0)
            return {"reachable": True}
        async def run():
            prepared = {"effective_parameters": {}, "provenance": {}, "warnings": [], "operations": {}}
            with patch.object(main, "jobs", {}), patch.object(main, "separate_jobs", {}), \
                    patch.object(main, "remix_jobs", stores), \
                    patch.object(main, "_prepare_ai_preview", new=AsyncMock(return_value=(Path("source.wav"), {}, prepared))), \
                    patch.object(main.music, "health", new=health):
                with self.assertRaises(HTTPException) as caught:
                    await main.audio_remix_ai(main.AiRemixRequest(file_name="source.wav", prompt="techno"), BackgroundTasks())
                self.assertEqual(caught.exception.status_code, 409)
                self.assertEqual(list(stores), ["other"])
        asyncio.run(run())

    def test_legacy_mix_phase_does_not_restart_idle_engine(self):
        job = {"status": "running", "phase": "Cuadrando voz", "engine_active": False}
        self.assertFalse(main._job_uses_motor(job, "remix"))
        job["engine_active"] = True
        self.assertTrue(main._job_uses_motor(job, "remix"))

    def test_cancelled_process_still_blocks_gpu_until_exit(self):
        with patch.object(main, "jobs", {}), patch.object(main, "separate_jobs", {}), \
                patch.object(main, "remix_jobs", {"x": {"status": "failed", "compute_active": True}}):
            self.assertIsNotNone(main._gpu_busy())
            main.remix_jobs["x"]["compute_active"] = False
            self.assertIsNone(main._gpu_busy())

    def test_new_generation_immediately_after_cancel_waits_for_process_cleanup(self):
        with tempfile.TemporaryDirectory(prefix="musicia-cancel-reservation-") as folder:
            job = {"job_id": "cleanup", "status": "running", "compute_active": True,
                   "engine_active": False, "phase": "Separando voz"}
            with patch.object(main, "jobs", {}), patch.object(main, "separate_jobs", {}), \
                    patch.object(main, "remix_jobs", {"cleanup": job}), \
                    patch.object(main, "HISTORY_FILE", Path(folder) / "history.json"):
                client = TestClient(main.app)
                cancelled = client.post("/music/jobs/cleanup/cancel")
                self.assertEqual(cancelled.status_code, 200)
                self.assertEqual(job["status"], "failed")
                blocked = client.post("/music/generate", json={"prompt": "techno"})
                self.assertEqual(blocked.status_code, 409)
                self.assertEqual(main.jobs, {})
                job["compute_active"] = False
                self.assertIsNone(main._gpu_busy())

    def test_actual_local_child_is_terminated_when_cancelled(self):
        import subprocess
        import threading
        import time
        import separator_service
        captured = []
        real_popen = subprocess.Popen
        def popen(*args, **kwargs):
            process = real_popen(*args, **kwargs)
            if args[0][0] == sys.executable:
                captured.append(process)
            return process
        config = AppSettings().remix
        config.subprocess_poll_seconds = 0.02
        cancelled = threading.Event()
        timer = threading.Timer(0.15, cancelled.set)
        started = time.monotonic()
        timer.start()
        try:
            with patch.object(separator_service.subprocess, "Popen", side_effect=popen):
                with self.assertRaisesRegex(RuntimeError, "Cancelado"):
                    separator_service.run_cancellable_process(
                        [sys.executable, "-c", "import time; time.sleep(60)"], config, cancelled.is_set)
        finally:
            timer.cancel()
        self.assertEqual(len(captured), 1)
        self.assertIsNotNone(captured[0].poll())
        self.assertLess(time.monotonic() - started, config.subprocess_termination_seconds)


if __name__ == "__main__":
    unittest.main()
