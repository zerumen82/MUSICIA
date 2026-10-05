"""Lógica del remix sin GPU: resolución de archivo e intención de melodía.

Se ejecuta con el venv del backend, sin motor ni ventana:
    backend\\venv\\Scripts\\python.exe -m unittest backend.test_remix_logic -v
"""

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


class VozRealQuiereMasLargaTest(unittest.TestCase):
    """El camino largo solo sale cuando los minutos dejan la voz claramente corta."""

    def test_sin_minutos_no_alarga(self):
        self.assertFalse(main.voz_real_quiere_mas_larga(None, 81.4))

    def test_mas_minutos_alarga(self):
        self.assertTrue(main.voz_real_quiere_mas_larga(180.0, 81.4))

    def test_misma_duracion_no_alarga(self):
        self.assertFalse(main.voz_real_quiere_mas_larga(81.4, 81.4))

    def test_fuente_cero_no_alarga(self):
        self.assertFalse(main.voz_real_quiere_mas_larga(180.0, 0))


if __name__ == "__main__":
    unittest.main()
