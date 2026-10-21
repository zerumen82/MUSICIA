"""Cobertura de bombo (B8c, 2026-10-20).

El oído del usuario oyó trozos «sin batería» que el detector de pulso daba
por buenos. Aquí se mide la banda 40-120 Hz con la rejilla del BPM pedido:
un golpe por tiempo. Los tests generan bombos sintéticos reales (60 Hz con
decaimiento) y comprueban la cobertura, no un mock.
"""
import array
import math
import sys
import tempfile
import unittest
import wave
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from audio_analysis import kick_coverage  # noqa: E402
from config import AppSettings  # noqa: E402
from remix_project import (  # noqa: E402
    audio_has_no_usable_groove,
    kick_coverage_screen,
    screen_continuation_chunk,
)


def _write_signal(path: Path, bpm: float, seconds: float, *, freq: float = 60.0,
                  decay_ms: float = 60.0, gain: float = 12000, rate: int = 48000) -> None:
    """Tren de golpes de `freq` Hz con decaimiento, a `bpm`. Silencio si bpm<=0."""
    count = int(rate * seconds)
    samples = array.array("h", bytes(count * 2))
    if bpm and bpm > 0:
        period = rate * 60.0 / bpm
        burst = int(rate * decay_ms / 1000)
        position = 0.0
        while position < count - burst:
            start = int(position)
            for offset in range(burst):
                t = offset / rate
                samples[start + offset] = int(gain * math.exp(-t * 40.0)
                                             * math.sin(2.0 * math.pi * freq * t))
            position += period
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes(samples.tobytes())


class KickCoverageTest(unittest.TestCase):
    def setUp(self):
        self.config = AppSettings().remix
        self.assertEqual(self.config.timeline_min_kick_coverage, 0.5)

    def test_bombo_en_cada_tiempo_da_cobertura_alta(self):
        with tempfile.TemporaryDirectory() as tmp:
            ruta = Path(tmp) / "bombo.wav"
            _write_signal(ruta, 120.0, 8.0)
            result = kick_coverage(ruta, bpm=120.0)
        self.assertGreaterEqual(result["coverage"], 0.9)
        self.assertGreaterEqual(result["kicks"], 14)  # ~16 tiempos en 8 s
        self.assertGreater(result["beats"], 0)

    def test_sin_bombo_da_cobertura_cero(self):
        with tempfile.TemporaryDirectory() as tmp:
            ruta = Path(tmp) / "silencio.wav"
            _write_signal(ruta, 0, 8.0)
            result = kick_coverage(ruta, bpm=120.0)
        self.assertEqual(result["coverage"], 0.0)
        self.assertEqual(result["kicks"], 0)

    def test_fuera_de_la_rejilla_del_bpm_pide_otro_tempo(self):
        with tempfile.TemporaryDirectory() as tmp:
            ruta = Path(tmp) / "bombo.wav"
            _write_signal(ruta, 120.0, 8.0)
            # Los golpes caen cada 0,5 s pero la rejilla pedida es de 0,333 s:
            # la mitad de los tiempos se queda sin bombo.
            result = kick_coverage(ruta, bpm=180.0)
        self.assertLessEqual(result["coverage"], 0.6)
        self.assertGreaterEqual(result["coverage"], 0.3)

    def test_bpm_invalido_se_rechaza(self):
        with tempfile.TemporaryDirectory() as tmp:
            ruta = Path(tmp) / "bombo.wav"
            _write_signal(ruta, 120.0, 2.0)
            with self.assertRaises(ValueError):
                kick_coverage(ruta, bpm=0)

    def test_audio_corto_se_rechaza(self):
        with tempfile.TemporaryDirectory() as tmp:
            ruta = Path(tmp) / "corto.wav"
            _write_signal(ruta, 120.0, 0.5)
            with self.assertRaises(ValueError):
                kick_coverage(ruta, bpm=120.0)


class KickScreenTest(unittest.TestCase):
    def setUp(self):
        self.config = AppSettings().remix

    def test_por_debajo_del_umbral_da_motivo_y_encima_no(self):
        with tempfile.TemporaryDirectory() as tmp:
            bueno = Path(tmp) / "bueno.wav"
            malo = Path(tmp) / "malo.wav"
            _write_signal(bueno, 120.0, 8.0)
            _write_signal(malo, 0, 8.0)
            self.assertIsNone(kick_coverage_screen(bueno, 120.0, self.config, Path(tmp), "x"))
            motivo = kick_coverage_screen(malo, 120.0, self.config, Path(tmp), "x")
            self.assertIsNotNone(motivo)
            self.assertIn("el bombo cubre", motivo)

    def test_umbral_cero_desactiva_el_cribado(self):
        with tempfile.TemporaryDirectory() as tmp:
            malo = Path(tmp) / "malo.wav"
            _write_signal(malo, 0, 8.0)
            config = AppSettings().remix
            config.timeline_min_kick_coverage = 0.0
            self.assertIsNone(kick_coverage_screen(malo, 120.0, config, Path(tmp), "x"))

    def test_motivo_de_bombo_es_reconocido_como_regenerable(self):
        self.assertTrue(audio_has_no_usable_groove(
            ValueError("el bombo cubre 0.10 de los tiempos del compás y el mínimo "
                       "configurado es 0.50")))
        self.assertFalse(audio_has_no_usable_groove(
            ValueError("El BPM final medido 180 no cumple el pedido 120")))

    def test_trozo_con_bombo_en_sus_tiempos_pasa_el_cribado(self):
        # Integración: el cribado de trozos acepta una región con bombo a negras.
        config = AppSettings().remix
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            ruta = work / "trozo.wav"
            _write_signal(ruta, 120.0, 10.0)
            motivo = screen_continuation_chunk(
                ruta, {"start": 0.0, "end": 10.0}, 120.0, config, work, "trozo")
        self.assertIsNone(motivo)


if __name__ == "__main__":
    unittest.main()
