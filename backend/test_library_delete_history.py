"""Regresiones B1/B2 (2026-10-12): borrado honesto e historial del modo voz.

Archivos e historial en directorios temporales; sin motor, GPU ni datos del
usuario. Los fallos OS y el trabajo de audio se aíslan en estos tests. La
verificación real del bloqueo Windows y del remix pertenece al tester.
"""

from __future__ import annotations

import asyncio
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import main  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


class LibraryDeleteTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="musicia-delete-")
        self.outputs = Path(self.tmp.name)
        self.output_patch = patch.object(main.settings.paths, "outputs_dir", str(self.outputs))
        self.output_patch.start()
        self.addCleanup(self.output_patch.stop)
        self.addCleanup(self.tmp.cleanup)
        self.client = TestClient(main.app, raise_server_exceptions=False)

    def _track(self, name):
        path = self.outputs / name
        path.write_bytes(b"isolated deletion fixture")
        main._ficha_path(path).write_text(json.dumps({"name": name}), encoding="utf-8")
        return path

    def _error(self, path, winerror=None, error_type=PermissionError):
        error = error_type(13 if error_type is PermissionError else 5, "error OS de prueba", str(path))
        if winerror is not None:
            error.winerror = winerror
        return error

    def _patch_unlink(self, failures):
        original = Path.unlink

        def unlink(path, *args, **kwargs):
            if path in failures:
                raise failures[path]
            return original(path, *args, **kwargs)

        return patch.object(Path, "unlink", unlink)

    def test_ocupado_devuelve_conflicto_y_conserva_audio_y_ficha(self):
        path = self._track("ocupado.mp3")
        with self._patch_unlink({path: self._error(path, winerror=32)}):
            response = self.client.delete(f"/music/audio/{path.name}")
        self.assertEqual(response.status_code, 409)
        self.assertIn("otro proceso", response.json()["detail"])
        self.assertTrue(path.exists())
        self.assertTrue(main._ficha_path(path).exists())

    def test_lote_continua_y_separa_bloqueo_ausencia_y_otros_errores(self):
        locked = self._track("ocupado.mp3")
        free = self._track("libre.mp3")
        denied = self._track("denegado.mp3")
        broken = self._track("error-os.mp3")
        failures = {
            locked: self._error(locked, winerror=33),
            denied: self._error(denied),
            broken: self._error(broken, error_type=OSError),
        }
        with self._patch_unlink(failures):
            response = self.client.post("/music/audio/delete_many", json={
                "names": [locked.name, free.name, "ausente.mp3", denied.name, broken.name],
            })
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["deleted"], [free.name])
        self.assertEqual(result["blocked"], [locked.name])
        self.assertEqual(result["not_found"], ["ausente.mp3"])
        self.assertEqual([item["name"] for item in result["failed"]], [denied.name, broken.name])
        self.assertEqual([item["status_code"] for item in result["failed"]], [403, 500])
        self.assertTrue(all("error OS de prueba" in item["detail"] for item in result["failed"]))
        self.assertFalse(free.exists())
        self.assertFalse(main._ficha_path(free).exists())
        for path in (locked, denied, broken):
            self.assertTrue(path.exists())
            self.assertTrue(main._ficha_path(path).exists())

    def test_individual_informa_otros_errores_os_sin_inventar_bloqueo(self):
        for error_type, status in ((PermissionError, 403), (OSError, 500)):
            with self.subTest(error_type=error_type):
                path = self._track("fallo.mp3")
                with self._patch_unlink({path: self._error(path, error_type=error_type)}):
                    response = self.client.delete(f"/music/audio/{path.name}")
                self.assertEqual(response.status_code, status)
                self.assertIn("error OS de prueba", response.json()["detail"])
                self.assertTrue(path.exists())

    def test_ficha_bloqueada_no_anuncia_exito_completo(self):
        path = self._track("ficha-ocupada.mp3")
        ficha = main._ficha_path(path)
        with self._patch_unlink({ficha: self._error(ficha, winerror=32)}):
            response = self.client.delete(f"/music/audio/{path.name}")
        self.assertEqual(response.status_code, 500)
        self.assertIn("ficha", response.json()["detail"])
        self.assertFalse(path.exists())
        self.assertTrue(ficha.exists())

    def test_borrado_normal_y_ausente(self):
        path = self._track("normal.mp3")
        response = self.client.delete(f"/music/audio/{path.name}")
        self.assertEqual(response.json(), {"status": "deleted", "name": path.name})
        self.assertFalse(path.exists())
        self.assertFalse(main._ficha_path(path).exists())
        self.assertEqual(self.client.delete(f"/music/audio/{path.name}").status_code, 404)


class LongOutputNameTest(unittest.TestCase):
    def test_renombrado_admite_ultimo_ordinal_configurado_y_respeta_limite(self):
        with tempfile.TemporaryDirectory(prefix="musicia-rename-limit-") as directory:
            with patch.object(main.settings.paths, "outputs_dir", directory), patch.object(main.settings.generation, "max_name_versions", 2):
                folder = Path(directory)
                (folder / "destino.mp3").write_bytes(b"original target")
                (folder / "origen.mp3").write_bytes(b"source")
                client = TestClient(main.app, raise_server_exceptions=False)
                request = {"new_name": "destino", "source_kind": "output"}
                second = client.patch("/music/audio/origen.mp3", json=request)
                self.assertEqual(second.status_code, 200)
                self.assertEqual(second.json()["name"], "destino (2).mp3")
                (folder / "tercero.mp3").write_bytes(b"third source")
                blocked = client.patch("/music/audio/tercero.mp3", json=request)
                self.assertEqual(blocked.status_code, 409)
                self.assertTrue((folder / "tercero.mp3").exists())
                self.assertEqual((folder / "destino.mp3").read_bytes(), b"original target")

    def test_colisiones_largas_preservan_ordinal_sin_pisar_archivos(self):
        with tempfile.TemporaryDirectory(prefix="musicia-long-name-") as directory:
            with patch.object(main.settings.paths, "outputs_dir", directory), patch.object(main.settings.generation, "max_slug_chars", 40):
                stem = "nombre de diagnóstico muy largo " * 3
                first = main._unique_output_path(stem, ".mp3")
                first.write_bytes(b"first filename fixture")
                second = main._unique_output_path(stem, ".mp3")
                second.write_bytes(b"second filename fixture")
                third = main._unique_output_path(stem, ".mp3")
                self.assertEqual(first.read_bytes(), b"first filename fixture")
                self.assertTrue(second.stem.endswith(" (2)"))
                self.assertTrue(third.stem.endswith(" (3)"))
                self.assertEqual(len({first, second, third}), 3)
                self.assertTrue(all(len(p.stem) <= main.settings.generation.max_slug_chars for p in (first, second, third)))


class VoiceRemixHistoryTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="musicia-remix-history-")
        self.addCleanup(self.tmp.cleanup)
        self.history = Path(self.tmp.name) / "job_history.json"
        self.job_id = "test-voz"
        self.job = {"job_id": self.job_id, "status": "running", "events": [], "prompt": "gabber"}
        for name, value in (
            ("HISTORY_FILE", self.history), ("jobs", {}),
            ("remix_jobs", {self.job_id: self.job}), ("separate_jobs", {}),
        ):
            patcher = patch.object(main, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def _run(self, mode="voz"):
        asyncio.run(main._run_ai_remix(
            self.job_id, Path("origen.mp3"),
            main.AiRemixRequest(file_name="origen.mp3", prompt="gabber", mode=mode),
            {}, "resultado",
        ))

    def _restored(self):
        self.assertTrue(self.history.exists(), "el retorno del modo voz evitó guardar el historial")
        data = json.loads(self.history.read_text(encoding="utf-8"))
        self.assertEqual(len(data["remix"]), 1)
        main.remix_jobs.clear()
        main._load_history()
        return main.remix_jobs[self.job_id]

    def test_exito_del_modo_voz_sobrevive_al_reinicio_con_variantes(self):
        async def finished(*args):
            self.job.update(status="succeeded", phase="Listo", result={
                "mix": "voz-v1.mp3", "variants": ["voz-v1.mp3", "voz-v2.mp3"], "mode": "voz",
            })

        with patch.object(main, "_modo_conservar_voz", new=AsyncMock(side_effect=finished)):
            self._run()
        restored = self._restored()
        self.assertEqual(restored["status"], "succeeded")
        self.assertEqual(restored["result"]["variants"], ["voz-v1.mp3", "voz-v2.mp3"])

    def test_fallo_del_modo_voz_persiste_el_error_real(self):
        with patch.object(main, "_modo_conservar_voz", new=AsyncMock(side_effect=main.MusicEngineError("fallo real"))):
            self._run()
        restored = self._restored()
        self.assertEqual(restored["status"], "failed")
        self.assertEqual(restored["error"], "fallo real")

    def test_cancelacion_durante_voz_no_se_convierte_en_exito(self):
        async def cancelled(*args):
            self.job["cancelled"] = True
            main._throw_if_cancelled(self.job)

        with patch.object(main, "_modo_conservar_voz", new=AsyncMock(side_effect=cancelled)):
            self._run()
        restored = self._restored()
        self.assertEqual(restored["status"], "failed")
        self.assertEqual(restored["phase"], "Cancelado")
        self.assertEqual(restored["error"], main.CANCELLED_MESSAGE)

    def test_cover_sigue_persistiendo_su_error(self):
        with patch.object(main.music, "submit", new=AsyncMock(side_effect=main.MusicEngineError("fallo cover"))):
            self._run(mode="reestilar")
        self.assertEqual(self._restored()["error"], "fallo cover")


if __name__ == "__main__":
    unittest.main()
