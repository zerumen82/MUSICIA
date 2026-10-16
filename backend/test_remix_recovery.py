"""Recuperación explícita: integridad y entrega del lote sin otra inferencia."""
import copy
import json
import sqlite3
import sys
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from urllib.parse import urlencode

sys.path.insert(0, str(Path(__file__).resolve().parent))

from fastapi import FastAPI
from pydub.generators import Sine
from config import AppSettings
from music_service import STATUS_SUCCEEDED, EngineStatus, GeneratedTrack, MusicService
from remix_project import RemixProjectRequest, RemixProjectRuntime, project_generation, timeline_plan
from remix_recovery import (RECEIPT_NAME, atomic_json, build_receipt, file_digest,
                            receipt_digest, validate_receipt, work_directory)


class DownloadedRemixTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.settings = AppSettings()
        self.settings.paths.outputs_dir = self.temp.name
        self.music = MusicService(self.settings)
        self.work = work_directory(self.settings.outputs_dir, "interrupted-job")
        self.work.mkdir(parents=True)
        self.source = Path(self.temp.name) / "source.wav"
        self.audio = Sine(220).to_audio_segment(duration=2000).set_channels(2)
        self.audio.export(self.source, format="wav").close()
        self.groups = {item["id"]: "keep" for item in self.settings.remix.groups}
        self.groups.update(drums="transform", bass="transform", other="transform")
        self.request = RemixProjectRequest(source_name=self.source.name, source_kind="upload",
            prompt="Original prompt", scope="groups", groups=self.groups,
            duration_seconds=4, transition_seconds=0.1)
        self.originals = {}
        for key in self.groups:
            path = self.work / f"tempo-{key}.wav"
            self.audio.export(path, format="wav").close()
            self.originals[key] = path
        engine_source = self.work / "material-a-transformar.wav"
        self.audio.export(engine_source, format="wav").close()
        self.generated = []
        for index, seed in enumerate((8123, 7429)):
            path = self.work / f"variante-{index + 1}.wav"
            self.audio.export(path, format="wav").close()
            self.generated.append((path, GeneratedTrack(file=f"/v1/audio?path=real-{index}.wav",
                prompt=self.request.prompt, seed=seed, seed_origin="engine.seed_value",
                metas={"bpm": 120})))
        digest = file_digest(self.source)
        self.job = {"job_id": "interrupted-job", "status": "failed", "phase": "Interrumpido",
            "error": "Interrumpido: la API se reinició antes de terminar",
            "project": self.request.model_dump(), "source_digest": digest,
            "engine_task_id": "real-task", "events": [], "pending_material": [],
            "started": time.monotonic(), "created_at": "2026-10-15T00:00:00+00:00",
            "operations": {"source_digest": digest,
                "timeline": timeline_plan(self.request, 2, self.settings)},
            "effective_parameters": self.music.build_payload(project_generation(
                self.request, engine_source, None, self.settings))}
        self.receipt = build_receipt(self.job, self.source, None, self.request, 2,
                                    self.settings, self.generated, self.originals)
        self.job["operations"]["downloaded_batch_sha256"] = receipt_digest(self.receipt)

    async def validate(self, receipt=None):
        return await validate_receipt(receipt or self.receipt, self.job, self.source, None,
                                      self.request, 2, self.settings, self.music)

    async def test_roundtrip_atomic_receipt_preserves_real_seeds(self):
        atomic_json(self.work / RECEIPT_NAME, self.receipt)
        receipt = json.loads((self.work / RECEIPT_NAME).read_text(encoding="utf-8"))
        generated, originals = await self.validate(receipt)
        self.assertEqual([track.seed for _path, track in generated], [8123, 7429])
        self.assertEqual(originals, self.originals)
        self.assertFalse((self.work / (RECEIPT_NAME + ".tmp")).exists())

    async def test_corrupt_wav_source_or_prepared_group_rejected(self):
        for path in (self.generated[0][0], self.source, self.originals["vocals"]):
            original = path.read_bytes()
            path.write_bytes(original + b"changed")
            with self.subTest(path=path.name), self.assertRaises(ValueError):
                await self.validate()
            path.write_bytes(original)

    async def test_incomplete_batch_repeated_variant_and_escaped_path_rejected(self):
        candidates = []
        missing = copy.deepcopy(self.receipt)
        missing["tracks"].pop()
        candidates.append(missing)
        repeated = copy.deepcopy(self.receipt)
        repeated["tracks"][1] = repeated["tracks"][0]
        candidates.append(repeated)
        escaped = copy.deepcopy(self.receipt)
        escaped["tracks"][0]["path"] = "../outside.wav"
        candidates.append(escaped)
        for receipt in candidates:
            self.job["operations"]["downloaded_batch_sha256"] = receipt_digest(receipt)
            with self.assertRaises(ValueError):
                await self.validate(receipt)

    async def test_cancelled_and_published_jobs_rejected_without_changes(self):
        for overrides in ({"cancelled": True}, {"error": "Cancelado por el usuario"},
                          {"status": "succeeded"}, {"result": {"variants": ["existing.mp3"]}}):
            saved = copy.deepcopy(self.job)
            self.job.update(overrides)
            before = copy.deepcopy(self.job)
            with self.assertRaises(ValueError):
                await self.validate()
            self.assertEqual(self.job, before)
            self.job = saved

    async def test_changed_job_parameters_request_or_timeline_rejected(self):
        for field in ("engine_task_id", "effective_parameters", "project", "operations"):
            saved = copy.deepcopy(self.job)
            if field == "engine_task_id":
                self.job[field] = "another-task"
            elif field == "effective_parameters":
                self.job[field]["guidance_scale"] += 1
            elif field == "project":
                self.job[field]["duration_seconds"] = 9
            else:
                self.job[field]["timeline"]["target_duration_seconds"] = 9
            with self.subTest(field=field), self.assertRaises(ValueError):
                await self.validate()
            self.job = saved

    async def test_valid_hash_does_not_hide_wrong_natural_duration(self):
        path = self.generated[0][0]
        self.audio[:1000].export(path, format="wav").close()
        self.receipt["tracks"][0]["sha256"] = file_digest(path)
        self.job["operations"]["downloaded_batch_sha256"] = receipt_digest(self.receipt)
        with self.assertRaisesRegex(ValueError, "Duración natural"):
            await self.validate()

    async def test_changed_metadata_alone_rejected_by_history_anchor(self):
        for key, value in (("seed", 999), ("seed_origin", "invented"), ("file", "other.wav")):
            receipt = copy.deepcopy(self.receipt)
            receipt["tracks"][0]["track"][key] = value
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, "anclado"):
                await self.validate(receipt)

    async def test_missing_history_anchor_is_not_trusted(self):
        del self.job["operations"]["downloaded_batch_sha256"]
        with self.assertRaisesRegex(ValueError, "anclado"):
            await self.validate()

    def runtime(self, published):
        def unique(stem, suffix):
            return Path(self.temp.name) / f"published-{len(published)}{suffix}"

        def publish(source, output, task_type, **ficha):
            published.append((output, ficha))

        return RemixProjectRuntime(FastAPI(), self.music, self.settings, {}, {},
            lambda *_: self.source, lambda: None, lambda *_: None, lambda job: job,
            lambda job, event: job.update(phase=event), lambda: None,
            unique, lambda raw, fallback: raw or fallback, publish,
            lambda path: None, lambda: "2026-10-15T00:00:01+00:00", lambda job: None)

    def continuation(self):
        """El cover ya descargado no se repite. Lo que sobra pide un repaint del final."""
        submitted = []

        async def submit(generation):
            submitted.append(generation)
            return (f"cont-{len(submitted)}", "queued")

        async def wait(task_id, on_update=None):
            return EngineStatus(task_id=task_id, status=STATUS_SUCCEEDED, tracks=[
                GeneratedTrack(file=f"/v1/audio?path={task_id}.wav", prompt=self.request.prompt,
                               seed=1, seed_origin="engine.seed")])

        async def download(_remote, path):
            Sine(220).to_audio_segment(duration=5000).set_channels(2).export(path, format="wav").close()
            return path

        return submitted, submit, wait, download

    async def test_finish_reuses_the_downloaded_cover_and_continues_the_bed(self):
        published = []
        runtime = self.runtime(published)
        manifest = {"groups": [{"id": key, "file_name": path.name} for key, path in self.originals.items()]}
        before = copy.deepcopy(self.job["project"])
        submitted, submit, wait, download = self.continuation()
        with patch.object(self.music, "submit", new=submit), \
                patch.object(self.music, "wait", new=wait), \
                patch.object(self.music, "download", new=download), \
                patch.object(runtime, "_groups", new=AsyncMock(return_value=manifest)):
            await runtime.finish_downloaded(self.job, self.source, None, self.request, 2, self.receipt)
        self.assertEqual(len(submitted), 2)
        for generation in submitted:
            self.assertEqual(generation.task_type, "repaint")
            self.assertEqual(generation.batch_size, 1)
            self.assertGreater(generation.repaint_end, generation.repaint_start)
        self.assertEqual(self.job["status"], "succeeded", self.job.get("error"))
        self.assertEqual(self.job["project"], before)
        self.assertEqual(len(published), 2)
        self.assertEqual([item[1]["seed"] for item in published], [8123, 7429])
        for path, ficha in published:
            self.assertAlmostEqual(await self.music.verify_audio(path) / 1000, 4, places=2)
            self.assertEqual(ficha["project"], before)

    async def test_failure_of_second_export_does_not_publish_first_variant(self):
        published = []
        runtime = self.runtime(published)
        manifest = {"groups": [{"id": key, "file_name": path.name} for key, path in self.originals.items()]}
        calls = 0

        def fail_on_second_export(path):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise RuntimeError("Real second-stage failure")
            return None

        runtime.measure_bpm = fail_on_second_export
        _submitted, submit, wait, download = self.continuation()
        with patch.object(self.music, "submit", new=submit), \
                patch.object(self.music, "wait", new=wait), \
                patch.object(self.music, "download", new=download), \
                patch.object(runtime, "_groups", new=AsyncMock(return_value=manifest)):
            await runtime.finish_downloaded(self.job, self.source, None, self.request, 2, self.receipt)
        self.assertEqual(self.job["status"], "failed")
        self.assertEqual(published, [])
        self.assertEqual(self.job["error"], "Real second-stage failure")

    async def test_prepublication_guard_prevents_a_partial_delivery(self):
        published = []
        runtime = self.runtime(published)
        manifest = {"groups": [{"id": key, "file_name": path.name} for key, path in self.originals.items()]}

        def changed_history():
            raise ValueError("History changed before publication")

        _submitted, submit, wait, download = self.continuation()
        with patch.object(self.music, "submit", new=submit), \
                patch.object(self.music, "wait", new=wait), \
                patch.object(self.music, "download", new=download), \
                patch.object(runtime, "_groups", new=AsyncMock(return_value=manifest)):
            await runtime.finish_downloaded(self.job, self.source, None, self.request, 2,
                                            self.receipt, before_publish=changed_history)
        self.assertEqual(self.job["status"], "failed")
        self.assertEqual(published, [])
        self.assertEqual(self.job["error"], "History changed before publication")

    async def test_normal_download_saves_anchored_receipt_before_postprocessing_failure(self):
        from music_service import EngineStatus, STATUS_SUCCEEDED
        runtime = self.runtime([])
        self.job["provenance"] = {}
        manifest = {"groups": [{"id": key, "file_name": path.name} for key, path in self.originals.items()]}
        status = EngineStatus(task_id="real-task", status=STATUS_SUCCEEDED,
                              tracks=[track for _path, track in self.generated])

        async def downloaded(_remote, path):
            return path

        with patch.object(self.music, "submit", new=AsyncMock(return_value=("real-task", "queued"))), \
                patch.object(self.music, "wait", new=AsyncMock(return_value=status)), \
                patch.object(self.music, "download", new=downloaded), \
                patch.object(runtime, "_groups", new=AsyncMock(side_effect=[manifest, RuntimeError("postprocessing failure")])):
            await runtime.run(self.job, self.source, None, self.request, 2)
        saved = json.loads((self.work / RECEIPT_NAME).read_text(encoding="utf-8"))
        self.assertEqual(self.job["status"], "failed")
        self.assertEqual(self.job["operations"]["downloaded_batch_sha256"], receipt_digest(saved))
        self.assertEqual([entry["track"]["seed"] for entry in saved["tracks"]], [8123, 7429])

    async def test_legacy_cache_binds_task_real_metadata_and_wav_hash(self):
        from scripts.complete_downloaded_remix import legacy_receipt
        cache_root = Path(self.temp.name) / "cache"
        cache = cache_root / "local_redis" / "cache.db"
        cache.parent.mkdir(parents=True)
        audio_root = cache_root / "tmp" / "api_audio"
        audio_root.mkdir(parents=True)
        entries = []
        parameters = self.job["effective_parameters"]
        for index, (path, track) in enumerate(self.generated):
            remote = audio_root / path.name
            remote.write_bytes(path.read_bytes())
            entries.append({"file": "/v1/audio?" + urlencode({"path": str(remote)}), "status": 1,
                "prompt": self.request.prompt, "lyrics": parameters["lyrics"],
                "seed_value": "8123,7429", "metas": {"bpm": 120},
                "dit_model": parameters["model"], "lm_model": parameters["lm_model_path"]})
        with sqlite3.connect(cache) as connection:
            connection.execute("CREATE TABLE Cache (key TEXT, mode INTEGER, filename TEXT, value TEXT)")
            connection.execute("INSERT INTO Cache VALUES (?, 1, NULL, ?)",
                ("ace_step_v1.5_real-task", json.dumps(entries)))
        self.job["operations"]["prepared_groups"] = {key: str(path) for key, path in self.originals.items()}
        receipt, raw = legacy_receipt(cache, self.job, self.source, None, self.request, 2, self.settings)
        self.assertEqual([entry["track"]["seed"] for entry in receipt["tracks"]], [8123, 7429])
        self.assertEqual(raw, entries)
        self.generated[0][0].write_bytes(b"corrupt local wav")
        with self.assertRaisesRegex(ValueError, "byte por byte"):
            legacy_receipt(cache, self.job, self.source, None, self.request, 2, self.settings)

    async def test_offline_process_guard_distinguishes_musicia_from_other_main(self):
        from scripts import complete_downloaded_remix as cli
        other = {"ProcessId": 999999, "CommandLine": "C:\\ComfyUI\\python.exe main.py",
                 "ExecutablePath": "C:\\ComfyUI\\python.exe"}
        with patch.object(cli.socket, "socket") as sockets, patch.object(cli.subprocess, "run") as query:
            sockets.return_value.__enter__.return_value.connect_ex.return_value = 1
            query.return_value = SimpleNamespace(stdout=json.dumps([other]))
            self.assertEqual(cli.require_offline(self.settings)["conflicting_processes"], [])
            for command_line, executable in (
                    (f'python "{cli.ROOT / "backend" / "main.py"}"', "C:\\Python\\python.exe"),
                    ("python main.py", str(cli.ROOT / "backend" / "venv" / "Scripts" / "python.exe")),
                    ("python -m acestep.api_server", str(cli.ROOT / "vendor" / "ACE-Step-1.5" / ".venv" / "Scripts" / "python.exe")),
                    (f'python "{cli.ROOT / "scripts" / "complete_downloaded_remix.py"}"', "C:\\Python\\python.exe")):
                query.return_value = SimpleNamespace(stdout=json.dumps([{
                    "ProcessId": 999999, "CommandLine": command_line, "ExecutablePath": executable}]))
                with self.subTest(command_line=command_line), self.assertRaisesRegex(ValueError, "PID"):
                    cli.require_offline(self.settings)

    async def test_offline_guard_only_excludes_verified_venv_launcher_parent(self):
        from scripts import complete_downloaded_remix as cli
        executable = str(cli.ROOT / "backend" / "venv" / "Scripts" / "python.exe")
        arguments = [str(cli.ROOT / "scripts" / "complete_downloaded_remix.py"),
                     "--job-id", "same-job", "--report", "same-report.json"]
        parent_pid, current_pid = 87654, 87655
        parent = {"ProcessId": parent_pid, "ParentProcessId": 87653,
                  "ExecutablePath": executable,
                  "CommandLine": cli.subprocess.list2cmdline([executable] + arguments)}
        current = {"ProcessId": current_pid, "ParentProcessId": parent_pid,
                   "ExecutablePath": "C:\\Python\\python.exe",
                   "CommandLine": cli.subprocess.list2cmdline(["C:\\Python\\python.exe"] + arguments)}
        with patch.object(cli.socket, "socket") as sockets, patch.object(cli.subprocess, "run") as query, \
                patch.object(cli.os, "getpid", return_value=current_pid), \
                patch.object(cli.os, "getppid", return_value=parent_pid):
            sockets.return_value.__enter__.return_value.connect_ex.return_value = 1
            query.return_value = SimpleNamespace(stdout=json.dumps([parent, current]))
            cli.require_offline(self.settings)
            for changed in ({"ProcessId": parent_pid + 2},
                            {"ExecutablePath": "C:\\Other\\python.exe"},
                            {"CommandLine": cli.subprocess.list2cmdline([executable] + arguments + ["--execute"])},
                            {"CommandLine": cli.subprocess.list2cmdline([executable] +
                                [str(cli.ROOT / "scripts" / "complete_downloaded_remix.py"),
                                 "--job-id", "other-job", "--report", "same-report.json"])}):
                other = {**parent, **changed}
                query.return_value = SimpleNamespace(stdout=json.dumps([other, current]))
                with self.subTest(changed=changed), self.assertRaisesRegex(ValueError, "PID"):
                    cli.require_offline(self.settings)


if __name__ == "__main__":
    unittest.main()
