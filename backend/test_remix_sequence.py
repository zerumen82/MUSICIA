"""Secuencia de pasos del remix (spec/02 [R20.A]): reparto, contrato y API."""
import sys
import tempfile
import time
import unittest
from array import array
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydub import AudioSegment

sys.path.insert(0, str(Path(__file__).resolve().parent))
import main
from config import AppSettings
from mixer_service import MixerService
from music_service import MusicService
from music_service import EngineStatus, GeneratedTrack, STATUS_SUCCEEDED
from remix_project import RemixProjectRequest, RemixProjectRuntime, timeline_plan
from remix_recovery import file_digest
from remix_sequence import (MATERIAL_ORIGIN_MIX, SequenceStep, active_steps,
                            material_origin, plan_segments, sequence_timeline,
                            step_seed, validate_steps)
from style_translator import style_for_engine


def steps(count=8, enabled_every=1, prompt="bombo a cuatro"):
    return [SequenceStep(index=index, enabled=index % enabled_every == 0, focus="todo",
                         prompt=prompt if index % enabled_every == 0 else "")
            for index in range(count)]


class SequenceStepsTest(unittest.TestCase):
    def setUp(self):
        self.config = AppSettings().remix

    def test_only_enabled_steps_are_active(self):
        active = active_steps(steps(8, enabled_every=2))
        self.assertEqual([step.index for step in active], [0, 2, 4, 6])

    def test_validate_rejects_missing_disabled_and_duplicated_steps(self):
        with self.assertRaisesRegex(ValueError, "al menos un paso"):
            validate_steps([], self.config)
        with self.assertRaisesRegex(ValueError, "al menos un paso"):
            validate_steps([SequenceStep(index=0, enabled=False, prompt="x")], self.config)
        with self.assertRaisesRegex(ValueError, "numerados"):
            validate_steps([SequenceStep(index=0, prompt="a"), SequenceStep(index=0, prompt="b")], self.config)
        with self.assertRaisesRegex(ValueError, "texto"):
            validate_steps([SequenceStep(index=0, prompt="  ")], self.config)
        with self.assertRaisesRegex(ValueError, "foco"):
            validate_steps([SequenceStep(index=0, prompt="a", focus="kazoo")], self.config)

    def test_validate_rejects_a_focus_that_is_not_implemented_yet(self):
        with self.assertRaisesRegex(ValueError, "todavía no está implementado"):
            validate_steps([SequenceStep(index=0, prompt="a", focus="drums")], self.config)

    def test_validate_respects_the_configured_maximum(self):
        allowed = [SequenceStep(index=index, prompt="a") for index in range(self.config.sequence_max_steps)]
        self.assertEqual(len(validate_steps(allowed, self.config)), self.config.sequence_max_steps)
        too_many = [SequenceStep(index=index, prompt="a")
                    for index in range(self.config.sequence_max_steps + 1)]
        with self.assertRaisesRegex(ValueError, "hasta"):
            validate_steps(too_many, self.config)

    def test_segments_follow_the_bars_when_the_tempo_is_known(self):
        planned = plan_segments(180.0, 128.0, steps(8), self.config, 4)
        self.assertEqual(len(planned), 8)
        self.assertTrue(all(segment["bar_aligned"] for segment in planned))
        self.assertEqual(planned[0]["start"], 0.0)
        self.assertEqual(planned[-1]["end"], 180.0)
        for previous, following in zip(planned, planned[1:]):
            self.assertEqual(previous["end"], following["start"])
        self.assertEqual(planned[0]["bars"], 12)

    def test_segments_are_refused_without_a_measured_tempo(self):
        with self.assertRaisesRegex(ValueError, "BPM fiable"):
            plan_segments(180.0, None, steps(8), self.config, 4)


    def test_timeline_keeps_the_source_duration(self):
        timeline = sequence_timeline(180.0, 128.0, steps(8), self.config, 4)
        self.assertEqual(timeline["method"], "sequence_steps")
        self.assertEqual(timeline["natural_duration_seconds"], 180.0)
        self.assertEqual(timeline["target_duration_seconds"], 180.0)
        self.assertEqual(timeline["tempo_ratio"], 1.0)
        self.assertEqual(timeline["step_count"], 8)

    def test_the_first_step_uses_the_requested_seed_and_none_exceeds_the_maximum(self):
        maximo = 2147483647
        self.assertEqual(step_seed(4242, 0, maximo), 4242)
        self.assertEqual(step_seed(4242, 3, maximo), 4245)
        # Con un máximo menor, la semilla se acota en vez de salirse.
        self.assertEqual(step_seed(999, 2, 1000), 0)
        self.assertIsNone(step_seed(None, 0, maximo))
        self.assertIsNone(step_seed(True, 0, maximo))

    def test_material_origin_is_declared(self):
        request = RemixProjectRequest(source_name="original.wav", scope="sequence", steps=steps(2))
        self.assertEqual(material_origin(request), MATERIAL_ORIGIN_MIX)

    def test_request_timeline_uses_the_sequence_plan(self):
        request = RemixProjectRequest(source_name="original.wav", scope="sequence", steps=steps(8))
        plan = timeline_plan(request, 180.0, AppSettings(), {"bpm_measured": 128.0, "bpm_confidence": 0.9})
        self.assertEqual(plan["method"], "sequence_steps")
        self.assertEqual(len(plan["steps"]), 8)

    def test_the_declared_tempo_origin_is_the_real_one(self):
        measured = {"bpm_measured": 128.0, "bpm_confidence": 0.9}
        request = RemixProjectRequest(source_name="original.wav", scope="sequence", steps=steps(8))
        plan = timeline_plan(request, 180.0, AppSettings(), measured)
        self.assertEqual(plan["source_bpm_origin"], "measurement")
        manual = RemixProjectRequest(source_name="original.wav", scope="sequence",
                                     steps=steps(8), source_bpm=124)
        manual_plan = timeline_plan(manual, 180.0, AppSettings(), measured)
        self.assertEqual(manual_plan["source_bpm_origin"], "manual")
        self.assertEqual(manual_plan["source_bpm"], 124)


class SequenceApiTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="musicia-sequence-")
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)
        AudioSegment.silent(duration=60000).export(self.folder / "original.wav", format="wav").close()
        patcher = patch.object(main.settings.paths, "outputs_dir", str(self.folder))
        patcher.start()
        self.addCleanup(patcher.stop)
        self.client = TestClient(main.app)

    def body(self, **kwargs):
        payload = {"source_name": "original.wav", "source_kind": "output", "scope": "sequence",
                   "source_bpm": 120,
                   "steps": [{"index": index, "enabled": index < 2, "focus": "todo",
                              "prompt": "four on the floor" if index < 2 else ""}
                             for index in range(8)]}
        payload.update(kwargs)
        return payload

    def test_capabilities_expose_the_sequence_limits(self):
        capabilities = self.client.get("/music/remix/capabilities").json()
        self.assertEqual(capabilities["sequence"]["default_steps"], 8)
        self.assertEqual(capabilities["sequence"]["max_steps"], 16)
        self.assertEqual(capabilities["sequence"]["focuses"], ["todo"])
        self.assertIn("drums", capabilities["sequence"]["focuses_pending"])
        self.assertIn("sequence", [scope["id"] for scope in capabilities["scopes"]])

    def test_preview_returns_the_plan_of_every_step(self):
        before = dict(main.remix_jobs)
        response = self.client.post("/music/remix/preview", json=self.body())
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertEqual(result["sequence"]["engine_calls"], 2)
        self.assertEqual(len(result["sequence"]["steps"]), 8)
        self.assertEqual(result["sequence"]["steps"][0]["effective_prompt"], "four on the floor")
        self.assertEqual(result["effective_prompt"], "four on the floor")
        self.assertEqual(result["operations"]["scope"], "sequence")
        self.assertTrue(result["operations"]["engine_required"])
        self.assertEqual(result["operations"]["timeline"]["source_bpm_origin"], "manual")
        self.assertEqual(main.remix_jobs, before)

    def test_preview_refuses_a_sequence_without_text_or_without_steps(self):
        before = dict(main.remix_jobs)
        without_text = self.body(steps=[{"index": 0, "enabled": True, "focus": "todo", "prompt": " "}])
        response = self.client.post("/music/remix/preview", json=without_text)
        self.assertEqual(response.status_code, 422)
        self.assertIn("texto", response.json()["detail"])
        without_steps = self.body(steps=[])
        self.assertEqual(self.client.post("/music/remix/preview", json=without_steps).status_code, 422)
        self.assertEqual(main.remix_jobs, before)

    def test_preview_refuses_a_sequence_without_a_reliable_tempo(self):
        # Un audio sin groove medible no se reparte: cortar a mitad de golpe
        # destrozaría el ritmo. El usuario da el BPM original revisado.
        without_tempo = self.body()
        without_tempo.pop("source_bpm", None)
        response = self.client.post("/music/remix/preview", json=without_tempo)
        self.assertEqual(response.status_code, 422)
        self.assertIn("BPM fiable", response.json()["detail"])

    def test_sequence_refuses_the_fields_it_does_not_use(self):
        for field, value in (("bpm", 120), ("duration_seconds", 30),
                             ("repeat_start", 0.0), ("transition_seconds", 0.5),
                             ("batch_size", 2)):
            with self.subTest(field=field):
                response = self.client.post("/music/remix/preview", json=self.body(**{field: value}))
                self.assertEqual(response.status_code, 422, response.text)
                self.assertIn("La secuencia", response.json()["detail"])

    def test_preview_warns_about_one_engine_call_per_step(self):
        result = self.client.post("/music/remix/preview", json=self.body()).json()
        warnings = " ".join(result["warnings"])
        self.assertIn("2 pasos son 2 generaciones", warnings)
        self.assertIn("parar en cualquier paso", warnings)


class SequenceExecutionTest(unittest.IsolatedAsyncioTestCase):
    """La secuencia llama al motor una vez por paso, en orden y encadenada."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="musicia-seq-run-")
        self.addCleanup(self.temp.cleanup)
        self.settings = AppSettings()
        self.settings.paths.outputs_dir = self.temp.name
        self.music = MusicService(self.settings)
        self.source = Path(self.temp.name) / "source.wav"
        AudioSegment.silent(duration=12000, frame_rate=48000).set_channels(2).export(
            self.source, format="wav").close()
        self.request = RemixProjectRequest(
            source_name=self.source.name, source_kind="upload", scope="sequence",
            steps=[SequenceStep(index=0, enabled=True, focus="todo", prompt="four on the floor"),
                   SequenceStep(index=1, enabled=True, focus="todo", prompt="breakbeat drums"),
                   SequenceStep(index=2, enabled=False, focus="todo", prompt="")])
        self.published = []
        self.submitted = []

    def runtime(self):
        def unique(stem, suffix):
            return Path(self.temp.name) / f"published-{len(self.published)}{suffix}"

        def publish(source, output, task_type, **ficha):
            self.published.append((output, ficha))

        return RemixProjectRuntime(
            FastAPI(), self.music, self.settings, {}, {},
            lambda *_: self.source, lambda: None, lambda *_: None, lambda job: job,
            lambda job, event: job.update(phase=event), lambda: None,
            unique, lambda raw, fallback: raw or fallback, publish,
            lambda path: None, lambda: "2026-11-12T00:00:00+00:00", lambda job: None)

    def engine(self):
        async def submit(generation):
            self.submitted.append(generation)
            return (f"paso-{len(self.submitted)}", "queued")

        async def wait(task_id, on_update=None):
            return EngineStatus(task_id=task_id, status=STATUS_SUCCEEDED, tracks=[
                GeneratedTrack(file=f"/v1/audio?path={task_id}.wav", prompt="",
                               seed=1, seed_origin="engine.seed")])

        async def download(_remote, path):
            rate = self.settings.remix.sample_rate
            samples = array("f", [0.2] * (rate * 12 * 2))
            MixerService._write_float_wav(path, samples, rate, 2)
            return path

        return submit, wait, download

    def job(self):
        plan = sequence_timeline(12.0, 128.0, self.request.steps, self.settings.remix, self.settings.mixer.beats_per_bar)
        return {"job_id": "secuencia-1", "status": "queued", "phase": "En cola", "error": None,
                "events": [], "started": time.monotonic(), "created_at": "2026-11-12T00:00:00+00:00",
                "project": self.request.model_dump(),
                "source_digest": file_digest(self.source),
                "operations": {"source_digest": file_digest(self.source), "timeline": plan},
                "effective_parameters": {}, "provenance": {}, "warnings": []}

    async def test_every_enabled_step_calls_the_engine_in_order(self):
        runtime = self.runtime()
        job = self.job()
        submit, wait, download = self.engine()
        with patch.object(self.music, "submit", new=submit), \
                patch.object(self.music, "wait", new=wait), \
                patch.object(self.music, "download", new=download):
            await runtime.run(job, self.source, None, self.request, 12.0)
        self.assertEqual(job["status"], "succeeded", job.get("error"))
        # Solo los dos pasos encendidos llaman al motor.
        self.assertEqual(len(self.submitted), 2)
        for generation in self.submitted:
            self.assertEqual(generation.task_type, "repaint")
            self.assertEqual(generation.batch_size, 1)
        self.assertEqual(self.submitted[0].repaint_start, 0.0)
        self.assertEqual(self.submitted[0].repaint_end, 3.75)
        self.assertEqual(self.submitted[1].repaint_start, 3.75)
        self.assertEqual(self.submitted[1].repaint_end, 7.5)
        self.assertEqual(self.submitted[0].prompt, "four on the floor")
        self.assertEqual(self.submitted[1].prompt, "breakbeat drums")
        # El segundo paso se aplica sobre el audio del primero.
        self.assertEqual(self.submitted[0].source_path, str(self.source))
        self.assertNotEqual(self.submitted[1].source_path, str(self.source))
        self.assertEqual(len(self.published), 1)
        _output, ficha = self.published[0]
        self.assertEqual([step["status"] for step in ficha["steps"]], ["done", "done", "kept"])
        self.assertEqual(ficha["material_origin"], "separado_de_mezcla")
        self.assertEqual(job["result"]["material_origin"], "separado_de_mezcla")

    async def test_stopping_keeps_what_was_done_and_marks_the_rest(self):
        runtime = self.runtime()
        job = self.job()
        job["stop_requested"] = True
        submit, wait, download = self.engine()
        with patch.object(self.music, "submit", new=submit), \
                patch.object(self.music, "wait", new=wait), \
                patch.object(self.music, "download", new=download):
            await runtime.run(job, self.source, None, self.request, 12.0)
        self.assertEqual(job["status"], "succeeded", job.get("error"))
        self.assertEqual(len(self.submitted), 1)
        self.assertEqual(len(self.published), 1)
        _output, ficha = self.published[0]
        self.assertEqual([step["status"] for step in ficha["steps"]], ["done", "kept", "kept"])
        self.assertIn("no llegó a rehacerse", ficha["steps"][1]["warning"])


if __name__ == "__main__":
    unittest.main()
