"""Lógica del remix sin GPU: resolución de archivo, intención de melodía
y elección de modelo/pasos/guidance (spec/02 [M1]).

Se ejecuta con el venv del backend, sin motor ni ventana:
    backend\\venv\\Scripts\\python.exe -m unittest backend.test_remix_logic -v
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import main  # noqa: E402
from fastapi import HTTPException  # noqa: E402


class FindAudioTest(unittest.TestCase):
    """_find_audio: la lista que dice la UI manda; la otra es reserva."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="musicia-kind-")
        self.outputs = Path(self.tmp.name) / "outputs"
        self.uploads = self.outputs / "uploads"
        self.outputs.mkdir(parents=True)
        self.uploads.mkdir(parents=True)
        self._old = main.settings.paths.outputs_dir
        main.settings.paths.outputs_dir = str(self.outputs)
        (self.outputs / "tema.mp3").write_bytes(b"MEZCLA-180s")
        (self.uploads / "tema.mp3").write_bytes(b"SUBIDA-81s")
        (self.outputs / "solo-bib.mp3").write_bytes(b"BIB")
        (self.uploads / "solo-sub.mp3").write_bytes(b"SUB")

    def tearDown(self):
        main.settings.paths.outputs_dir = self._old
        self.tmp.cleanup()

    def _bytes(self, name, kind=None):
        return main._find_audio(name, kind).read_bytes()

    def test_upload_manda_subida(self):
        self.assertEqual(self._bytes("tema.mp3", "upload"), b"SUBIDA-81s")

    def test_output_manda_mezcla(self):
        self.assertEqual(self._bytes("tema.mp3", "output"), b"MEZCLA-180s")

    def test_sin_kind_orden_viejo(self):
        self.assertEqual(self._bytes("tema.mp3"), b"MEZCLA-180s")

    def test_upload_recurre_a_outputs(self):
        self.assertEqual(self._bytes("solo-bib.mp3", "upload"), b"BIB")

    def test_output_recurre_a_uploads(self):
        self.assertEqual(self._bytes("solo-sub.mp3", "output"), b"SUB")

    def test_kind_invalido_400(self):
        with self.assertRaises(HTTPException) as ctx:
            main._find_audio("tema.mp3", "biblioteca")
        self.assertEqual(ctx.exception.status_code, 400)

    def test_ausente_404(self):
        with self.assertRaises(HTTPException) as ctx:
            main._find_audio("no-existe.mp3", "upload")
        self.assertEqual(ctx.exception.status_code, 404)


class RemixCoverStrengthTest(unittest.TestCase):
    """remix_cover_strength_for: el prompt elige la fuerza (config, no magia)."""

    def _strength(self, prompt):
        return main.remix_cover_strength_for(prompt)

    def test_sin_melodias_fuerza_baja(self):
        strength, note = self._strength("BATERIAS CONTUNDENTES DE TECHNO HARDCORE, SIN MELODIAS")
        self.assertEqual(strength, main.settings.generation.remix_cover_strength_no_melody)
        self.assertLess(strength, main.settings.generation.remix_cover_strength)
        self.assertIsNone(note)

    def test_solo_bateria_fuerza_baja(self):
        strength, _ = self._strength("solo bateria y bajo, no melody")
        self.assertEqual(strength, main.settings.generation.remix_cover_strength_no_melody)

    def test_como_la_original_fuerza_alta_con_aviso(self):
        strength, note = self._strength("MELODIAS SIMILARES A LA ORIGINAL CON SINTES ROLAND")
        self.assertEqual(strength, main.settings.generation.remix_cover_strength_like_original)
        self.assertGreater(strength, main.settings.generation.remix_cover_strength)
        self.assertEqual(note, "like-original")

    def test_neutro_fuerza_base_sin_aviso(self):
        strength, note = self._strength("TECHNO HARDBOUNCE, OSCURO, CONTUNDENTE")
        self.assertEqual(strength, main.settings.generation.remix_cover_strength)
        self.assertIsNone(note)

    def test_prompt_vacio_fuerza_base(self):
        strength, note = self._strength("")
        self.assertEqual(strength, main.settings.generation.remix_cover_strength)
        self.assertIsNone(note)

    def test_glosa_inglesa_sin_melodias_fuerza_baja(self):
        # La UI glosa el prompt: la intención tiene que seguir leyéndose.
        strength, note = self._strength(
            "baterias hardcore techno de rotterdam, sin melodias (drums, without melody)"
        )
        self.assertEqual(strength, main.settings.generation.remix_cover_strength_no_melody)
        self.assertIsNone(note)


class ModeloRemixTest(unittest.TestCase):
    """model_for + build_payload: el remix va al modelo con CFG, CREAR al otro.

    Los valores salen de config; el test solo comprueba que el camino
    decide por modelo y que las dos tablas no son la misma.
    """

    def setUp(self):
        from music_service import GenerationRequest, MusicService

        self.request = GenerationRequest
        self.service = MusicService(main.settings)
        self.gen = main.settings.generation

    def test_cover_y_repaint_van_al_modelo_de_remix(self):
        self.assertEqual(self.gen.model_for("cover"), self.gen.remix_model)
        self.assertEqual(self.gen.model_for("repaint"), self.gen.remix_model)

    def test_text2music_se_queda_en_el_configurado(self):
        self.assertEqual(self.gen.model_for("text2music"), self.gen.model)

    def test_lo_que_pide_el_cliente_manda(self):
        self.assertEqual(
            self.gen.model_for("cover", self.gen.model),
            self.gen.model,
        )

    def test_payload_del_remix_usa_su_modelo_y_sus_parametros(self):
        payload = self.service.build_payload(
            self.request(prompt="hardcore", task_type="cover", source_path="orig.wav")
        )
        self.assertEqual(payload["model"], self.gen.remix_model)
        self.assertEqual(payload["inference_steps"], self.gen.steps_by_model[self.gen.remix_model])
        self.assertEqual(payload["guidance_scale"], self.gen.guidance_by_model[self.gen.remix_model])
        self.assertEqual(payload["src_audio_path"], "orig.wav")

    def test_payload_de_crear_usa_el_modelo_configurado(self):
        payload = self.service.build_payload(self.request(prompt="lofi suave"))
        self.assertEqual(payload["model"], self.gen.model)
        self.assertEqual(payload["inference_steps"], self.gen.steps_by_model[self.gen.model])
        self.assertEqual(payload["guidance_scale"], self.gen.guidance_by_model[self.gen.model])

    def test_las_dos_tablas_no_son_la_misma(self):
        self.assertIn(self.gen.remix_model, self.gen.allowed_models)
        self.assertIn(self.gen.model, self.gen.allowed_models)
        self.assertNotEqual(
            self.gen.steps_by_model.get(self.gen.model),
            self.gen.steps_by_model.get(self.gen.remix_model),
        )
        self.assertLess(
            self.gen.guidance_by_model.get(self.gen.model, 0.0),
            self.gen.guidance_by_model.get(self.gen.remix_model, 0.0),
        )

    def test_modelo_fuera_de_la_allowlist_se_rechaza(self):
        from music_service import MusicEngineError

        with self.assertRaises(MusicEngineError):
            self.service.build_payload(
                self.request(prompt="x", model="acestep-v15-xl-turbo", task_type="cover", source_path="o.wav")
            )


class RememberJobsTest(unittest.TestCase):
    """_remember: el historial no crece sin límite; los activos no se tocan."""

    def test_poda_terminados_y_respeta_activos(self):
        store = {}
        for i in range(main.settings.job_history + 5):
            main._remember(store, f"j{i:02d}", {
                "job_id": f"j{i:02d}", "status": "succeeded",
                "created_at": f"2026-10-06T00:{i:02d}:00",
            })
        self.assertEqual(len(store), main.settings.job_history)
        self.assertNotIn("j00", store)
        main._remember(store, "run", {"job_id": "run", "status": "running"})
        for i in range(5):
            main._remember(store, f"k{i}", {
                "job_id": f"k{i}", "status": "failed",
                "created_at": f"2026-10-06T01:0{i}:00",
            })
        self.assertIn("run", store)
        self.assertLessEqual(
            len([j for j in store.values() if j["status"] not in ("queued", "running")]),
            main.settings.job_history,
        )


class CancelAndHistoryTest(unittest.TestCase):
    """Cancel y persistencia (spec/02 [Q1][Q2]): sin GPU ni motor."""

    def test_uses_motor_solo_si_trabaja(self):
        run = {"status": "running", "phase": "Sintetizando..."}
        self.assertTrue(main._job_uses_motor(run, "music"))
        self.assertTrue(main._job_uses_motor(run, "remix"))
        self.assertFalse(main._job_uses_motor(run, "separate"))
        self.assertFalse(main._job_uses_motor({"status": "queued", "phase": "En cola"}, "music"))
        self.assertFalse(main._job_uses_motor(
            {"status": "running", "phase": "Separando la voz..."}, "remix"))
        self.assertFalse(main._job_uses_motor({"status": "failed"}, "music"))

    def test_snapshot_solo_campos_declarados(self):
        job = {"job_id": "x", "status": "succeeded", "prompt": "p",
               "started": 123.4, "engine_task_id": "no-sale",
               "events": [{"t": 1, "text": "a"}]}
        snap = main._snapshot_job(main._MUSIC_KEPT, job)
        self.assertNotIn("started", snap)
        self.assertNotIn("engine_task_id", snap)
        self.assertTrue(snap["restored"])
        self.assertEqual(snap["events"], [{"t": 1, "text": "a"}])

    def test_save_load_roundtrip_marca_interrumpidos(self):
        import json
        import tempfile
        old_file, old_jobs = main.HISTORY_FILE, dict(main.jobs)
        tmp = Path(tempfile.mkdtemp(prefix="musicia-hist-")) / "job_history.json"
        try:
            main.HISTORY_FILE = tmp
            main.jobs.clear()
            main.jobs["ok1"] = {"job_id": "ok1", "status": "succeeded",
                                "prompt": "p", "created_at": "2026-10-06T00:00:00",
                                "events": []}
            main.jobs["run1"] = {"job_id": "run1", "status": "running",
                                 "prompt": "q", "created_at": "2026-10-06T00:01:00",
                                 "events": []}
            main._save_history()
            self.assertTrue(tmp.exists())
            main.jobs.clear()
            main._load_history()
            self.assertEqual(main.jobs["ok1"]["status"], "succeeded")
            self.assertTrue(main.jobs["ok1"]["restored"])
            self.assertEqual(main.jobs["run1"]["status"], "failed")
            self.assertEqual(main.jobs["run1"]["phase"], "Interrumpido")
        finally:
            main.jobs.clear()
            main.jobs.update(old_jobs)
            main.HISTORY_FILE = old_file

    def test_cancel_endpoint_404_y_409(self):
        from fastapi.testclient import TestClient
        client = TestClient(main.app)
        self.assertEqual(client.post("/music/jobs/no-existe/cancel").status_code, 404)
        main.jobs["viejo"] = {"job_id": "viejo", "status": "succeeded", "prompt": "p",
                              "created_at": "2026-10-06T00:00:00", "events": []}
        try:
            r = client.post("/music/jobs/viejo/cancel")
            self.assertEqual(r.status_code, 409)
        finally:
            main.jobs.pop("viejo", None)


class LibraryVersionTest(unittest.TestCase):
    """_library_version (spec/02 [R1]): huella del mismo glob que /music/library."""

    def test_vacia_es_cero_y_un_mp3_la_mueve(self):
        import tempfile
        from unittest.mock import PropertyMock, patch
        tmp = Path(tempfile.mkdtemp(prefix="musicia-libver-"))
        with patch.object(type(main.settings), "outputs_dir", new_callable=PropertyMock) as mock_dir:
            mock_dir.return_value = tmp
            self.assertEqual(main._library_version(), 0.0)
            first = tmp / "a.mp3"
            first.write_bytes(b"x")
            v1 = main._library_version()
            self.assertGreater(v1, 0.0)
            second = tmp / "b.mp3"
            second.write_bytes(b"y")
            os.utime(second, (v1 + 10, v1 + 10))
            v2 = main._library_version()
            self.assertGreater(v2, v1)
            second.unlink()
            self.assertEqual(main._library_version(), v1)

    def test_jobs_responde_con_la_huella(self):
        from fastapi.testclient import TestClient
        client = TestClient(main.app)
        data = client.get("/music/jobs").json()
        self.assertIn("library_version", data)
        self.assertIsInstance(data["library_version"], float)


class CoverNativoTest(unittest.TestCase):
    """Cover nativo del remix (spec/02 [R2][R3]): la fuerza viaja y el
    formato/batch salen de la config salvo petición explícita."""

    def test_payload_cover_lleva_origen_y_fuerza(self):
        from music_service import GenerationRequest
        payload = main.music.build_payload(GenerationRequest(
            prompt="hardcore", lyrics=None, instrumental=True,
            task_type="cover", source_path="tema.mp3", cover_strength=0.4,
            model=main.settings.generation.remix_model,
        ))
        self.assertEqual(payload["task_type"], "cover")
        self.assertEqual(payload["src_audio_path"], "tema.mp3")
        self.assertEqual(payload["audio_cover_strength"], 0.4)
        self.assertEqual(payload["audio_duration"], -1)

    def test_use_format_sale_de_config_y_se_puede_apagar(self):
        from music_service import GenerationRequest
        base = dict(prompt="x", lyrics=None, instrumental=True)
        # Default false desde 2026-10-06: el LM inventa en español (LXIV).
        self.assertFalse(main.music.build_payload(GenerationRequest(**base))["use_format"])
        self.assertTrue(
            main.music.build_payload(GenerationRequest(use_format=True, **base))["use_format"]
        )
        self.assertFalse(
            main.music.build_payload(GenerationRequest(use_format=False, **base))["use_format"]
        )

    def test_fuerza_fuera_de_rango_se_rechaza(self):
        from music_service import GenerationRequest, MusicEngineError
        with self.assertRaises(MusicEngineError):
            main.music.build_payload(GenerationRequest(
                prompt="x", lyrics=None, instrumental=True, task_type="cover",
                source_path="t.mp3", cover_strength=1.5,
                model=main.settings.generation.remix_model,
            ))

    def test_modo_remix_solo_reestilar_o_voz(self):
        from fastapi.testclient import TestClient
        client = TestClient(main.app)
        body = {"file_name": "x.mp3", "prompt": "hardcore en 4x4", "mode": "raro"}
        self.assertEqual(client.post("/audio/remix/ai", json=body).status_code, 422)
        body["mode"] = "voz"
        # Pasa la validación y cae en el 404 del audio (sin GPU ni ficheros).
        self.assertEqual(client.post("/audio/remix/ai", json=body).status_code, 404)


if __name__ == "__main__":
    unittest.main()
