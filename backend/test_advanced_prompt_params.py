"""Los parámetros avanzados del panel llegan de verdad a /release_task.

Comprueba el cableado completo: RemixProjectRequest (lo que manda la UI)
-> project_generation (preparación del remix) -> build_payload (cuerpo
real que viaja al motor). Si algún paso suelta el valor, el panel de
«Parámetros avanzados» mentiría y el usuario creería estar controlando
guidance/pasos/lote cuando no lo está.
"""
import sys
import unittest
from pathlib import Path

from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import AppSettings
from music_service import GenerationRequest, MusicService
from remix_project import RemixProjectRequest, project_generation


class AdvancedParamsReachEnginePayloadTest(unittest.TestCase):
    def setUp(self):
        self.settings = AppSettings()
        self.music = MusicService(self.settings)

    def project(self, **overrides):
        request = RemixProjectRequest(
            source_name="original.wav", prompt="hardcore en 4x4 con doble bombo",
            scope="full", **overrides)
        return project_generation(request, Path("original.wav"), None, self.settings)

    def test_valores_explicitos_sobrescriben_la_config(self):
        generation = self.project(guidance_scale=12.5, inference_steps=33,
                                  batch_size=1, use_format=True)
        payload = self.music.build_payload(generation)
        self.assertEqual(payload["guidance_scale"], 12.5)
        self.assertEqual(payload["inference_steps"], 33)
        self.assertEqual(payload["batch_size"], 1)
        self.assertTrue(payload["use_format"])

    def test_sin_tocar_nada_vale_la_config_del_sft(self):
        generation = self.project()
        payload = self.music.build_payload(generation)
        self.assertEqual(payload["guidance_scale"],
                         self.settings.generation.guidance_by_model["acestep-v15-sft"])
        self.assertEqual(payload["inference_steps"],
                         self.settings.generation.steps_by_model["acestep-v15-sft"])
        self.assertEqual(payload["batch_size"], self.settings.generation.batch_size)
        self.assertEqual(payload["use_format"], self.settings.generation.use_format)

    def test_el_modelo_del_remix_es_el_sft_que_siempre_activa_cfg(self):
        payload = self.music.build_payload(self.project())
        self.assertEqual(payload["model"], self.settings.generation.remix_model)
        self.assertGreater(payload["guidance_scale"], 1.0)

    def test_invalid_overrides_are_rejected_in_both_api_schemas(self):
        from main import MusicGenRequest
        for schema in (MusicGenRequest, RemixProjectRequest):
            base = {"prompt": "techno"}
            if schema is RemixProjectRequest:
                base["source_name"] = "original.wav"
            for field, values in {
                "batch_size": (0, -1, 1.5),
                "inference_steps": (0, -1, 1.5),
                "guidance_scale": (-1, float("nan"), float("inf"), -float("inf")),
            }.items():
                for value in values:
                    with self.subTest(schema=schema.__name__, field=field, value=value):
                        with self.assertRaises(ValidationError):
                            schema(**base, **{field: value})

    def test_guidance_zero_and_explicit_batch_three_remain_valid(self):
        generation = self.project(guidance_scale=0, inference_steps=1, batch_size=3)
        payload = self.music.build_payload(generation)
        self.assertEqual(payload["guidance_scale"], 0)
        self.assertEqual(payload["inference_steps"], 1)
        self.assertEqual(payload["batch_size"], 3)


if __name__ == "__main__":
    unittest.main()
