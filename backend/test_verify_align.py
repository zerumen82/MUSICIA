"""Verificación de audio y cuadre sin GPU (spec/02 [M3], spec/03 T6).

Lo que protege:
- `MusicService.verify_audio`: el guardián que decide si un MP3 del motor
  es real (existe, no vacío, duración > umbral) o un fallo.
- `plan_alignment` / `first_beat_seconds` / `bars_duration_seconds`: la
  lógica de cuadrar voz sobre base — mejor no cuadrar que destrozar.

Se ejecuta con el venv del backend, sin motor ni ventana:
    backend\\venv\\Scripts\\python.exe -m unittest backend.test_verify_align -v
"""

import asyncio
import math
import struct
import sys
import tempfile
import unittest
import wave
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from mixer_service import (  # noqa: E402
    MAX_TEMPO_RATIO,
    MIN_TEMPO_RATIO,
    bars_duration_seconds,
    first_beat_seconds,
    plan_alignment,
)
from music_service import MusicEngineError, MusicService  # noqa: E402


def _write_sine_wav(path: Path, seconds: float, freq: float = 440.0, rate: int = 8000) -> None:
    """WAV mono 16-bit generado con la stdlib (sin ffmpeg para escribirlo)."""
    n = int(rate * seconds)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        frames = b"".join(
            struct.pack("<h", int(20000 * math.sin(2 * math.pi * freq * i / rate)))
            for i in range(n)
        )
        w.writeframes(frames)


class VerifyAudioTest(unittest.TestCase):
    """verify_audio: existe + duración > umbral, o el error real."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="musicia-verify-")
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_archivo_inexistente_lanza_error_real(self):
        with self.assertRaises(MusicEngineError) as ctx:
            asyncio.run(MusicService.verify_audio(self.dir / "no-existe.mp3"))
        self.assertIn("no dejó el archivo", str(ctx.exception))

    def test_archivo_vacio_lanza_error_real(self):
        empty = self.dir / "vacio.mp3"
        empty.write_bytes(b"")
        with self.assertRaises(MusicEngineError) as ctx:
            asyncio.run(MusicService.verify_audio(empty))
        self.assertIn("vacío o corrupto", str(ctx.exception))

    def test_wav_valido_devuelve_su_duracion(self):
        real = self.dir / "ok.wav"
        _write_sine_wav(real, 0.5)
        duration = asyncio.run(MusicService.verify_audio(real))
        self.assertAlmostEqual(duration, 500.0, delta=10.0)

    def test_wav_bajo_el_umbral_lanza_error(self):
        short = self.dir / "corto.wav"
        _write_sine_wav(short, 0.5)
        with self.assertRaises(MusicEngineError):
            asyncio.run(MusicService.verify_audio(short, min_duration_ms=1000.0))


class PlanAlignmentTest(unittest.TestCase):
    """plan_alignment: cuadrar solo si el groove es fiable y el ajuste pequeño."""

    @staticmethod
    def _groove(bpm, conf=0.9, phase_ms=0.0, period_ms=None):
        return {
            "bpm": bpm,
            "confidence": conf,
            "phase_ms": phase_ms,
            "period_ms": period_ms or (60_000.0 / bpm),
        }

    def test_pista_en_tono_propone_cuadrar(self):
        plan = plan_alignment(self._groove(120), self._groove(120, phase_ms=100.0))
        self.assertIsNotNone(plan)
        self.assertAlmostEqual(plan["tempo_ratio"], 1.0)
        # La voz llega 100 ms tarde: hay que retrasarla 100 ms (fase negativa).
        self.assertAlmostEqual(plan["delay_ms"], -100.0, delta=0.1)

    def test_confianza_baja_no_cuadra(self):
        plan = plan_alignment(self._groove(120, conf=0.05), self._groove(120))
        self.assertIsNone(plan)

    def test_ajuste_demasiado_grande_no_cuadra(self):
        plan = plan_alignment(self._groove(180), self._groove(60))
        self.assertIsNone(plan)

    def test_ratio_en_los_limites_acepta(self):
        # 120 vs 100 → 1.2 (dentro de 0,8–1,25)
        plan = plan_alignment(self._groove(120), self._groove(100))
        self.assertIsNotNone(plan)
        self.assertTrue(MIN_TEMPO_RATIO <= plan["tempo_ratio"] <= MAX_TEMPO_RATIO)

    def test_ratio_fuera_de_los_limites_rechaza(self):
        self.assertIsNone(plan_alignment(self._groove(120), self._groove(90)))  # 1.33
        self.assertIsNone(plan_alignment(self._groove(90), self._groove(120)))  # 0.75

    def test_desfase_se_normaliza_al_intervalo_de_un_golpe(self):
        # Desfase de 0,8 periodos = más corto restando un periodo (−0,2).
        plan = plan_alignment(self._groove(120), self._groove(120, phase_ms=400.0))
        self.assertIsNotNone(plan)
        period = 500.0
        self.assertLessEqual(abs(plan["delay_ms"]), period / 2)


class TimingHelpersTest(unittest.TestCase):
    """first_beat_seconds y bars_duration_seconds: números con carga musical."""

    def test_fase_negativa_es_un_golpe_anterior(self):
        # −100 ms con periodo 500 ms → el golpe válido cae en 400 ms.
        self.assertAlmostEqual(
            first_beat_seconds({"phase_ms": -100.0, "period_ms": 500.0}), 0.4
        )

    def test_fase_positiva_se_queda(self):
        self.assertAlmostEqual(
            first_beat_seconds({"phase_ms": 150.0, "period_ms": 500.0}), 0.15
        )

    def test_cuatro_compases_de_cuatro_no_son_cuatro_golpes(self):
        # 4 compases 4/4 a 120 bpm = 16 golpes = 8 s.
        self.assertAlmostEqual(bars_duration_seconds(120, 4, 4), 8.0)

    def test_bpm_invalido_lanza(self):
        with self.assertRaises(ValueError):
            bars_duration_seconds(0, 4, 4)

    def test_loop_sin_compases_lanza(self):
        with self.assertRaises(ValueError):
            bars_duration_seconds(120, 0, 4)


class FichaMedidaTest(unittest.TestCase):
    """[M3] La ficha guarda el tempo medido; sin medición, no existe el campo."""

    def setUp(self):
        import main  # tarde: el import de main cuesta (carga config)

        self.main = main
        self.tmp = tempfile.TemporaryDirectory(prefix="musicia-ficha-m3-")
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_write_ficha_con_medicion_lleva_los_campos(self):
        out = self.dir / "pista.mp3"
        out.write_bytes(b"X")
        self.main._write_ficha(
            out, {"prompt": "techno", "bpm": 180},
            {"bpm_measured": 170.0, "bpm_confidence": 0.82},
        )
        ficha = self.main._read_ficha(out)
        self.assertEqual(ficha["bpm"], 180)          # lo pedido
        self.assertEqual(ficha["bpm_measured"], 170.0)  # lo medido
        self.assertEqual(ficha["bpm_confidence"], 0.82)

    def test_write_ficha_sin_medicion_no_inventa_campos(self):
        out = self.dir / "sin-medir.mp3"
        out.write_bytes(b"X")
        self.main._write_ficha(out, {"bpm": 180}, None)
        ficha = self.main._read_ficha(out)
        self.assertNotIn("bpm_measured", ficha)
        self.assertNotIn("bpm_confidence", ficha)

    def test_carry_ficha_no_arrastra_el_tempo_medido_del_origen(self):
        origin = self.dir / "origen.mp3"
        origin.write_bytes(b"X")
        target = self.dir / "remix.mp3"
        target.write_bytes(b"X")
        self.main._write_ficha(
            origin, {"bpm": 180}, {"bpm_measured": 170.0, "bpm_confidence": 0.9}
        )
        self.main._carry_ficha(origin, target, "remix")
        ficha = self.main._read_ficha(target)
        self.assertNotIn("bpm_measured", ficha)  # el del origen no le vale
        self.assertEqual(ficha["task_type"], "remix")

    def test_carry_ficha_acepta_medicion_fresca(self):
        origin = self.dir / "origen.mp3"
        origin.write_bytes(b"X")
        target = self.dir / "nuevo.mp3"
        target.write_bytes(b"X")
        self.main._write_ficha(
            origin, {"bpm": 180}, {"bpm_measured": 170.0, "bpm_confidence": 0.9}
        )
        self.main._carry_ficha(
            origin, target, "remix",
            bpm_measured=168.0, bpm_confidence=0.7,
        )
        ficha = self.main._read_ficha(target)
        self.assertEqual(ficha["bpm_measured"], 168.0)

    def test_measure_bpm_de_un_silencio_no_devuelve_nada(self):
        # 9 s de silencio: pasa la longitud mínima del detector, pero no hay
        # periodicidad → el detector lanza y _measure_bpm devuelve None.
        silence = self.dir / "silencio.wav"
        _write_sine_wav(silence, 9.0, freq=0.0)
        self.assertIsNone(self.main._measure_bpm(silence))

    def test_measure_bpm_de_audio_inexistente_no_lanza(self):
        # El fallo de medición no puede tumbar nada: devuelve None y ya.
        self.assertIsNone(self.main._measure_bpm(self.dir / "no-existe.mp3"))

    def test_original_measurement_preserves_groove_precision_for_tempo_duration(self):
        from audio_analysis import detect_groove
        from config import AppSettings
        from remix_project import RemixProjectRequest, timeline_plan
        path = self.dir / "fractional-pulse.wav"
        rate, bpm, seconds = 8000, 166.25, 20
        period = 60 / bpm
        with wave.open(str(path), "wb") as stream:
            stream.setnchannels(1)
            stream.setsampwidth(2)
            stream.setframerate(rate)
            stream.writeframes(b"".join(struct.pack("<h", int(
                (20000 if (index / rate) % period < 0.08 else 500)
                * math.sin(2 * math.pi * 220 * index / rate)))
                for index in range(rate * seconds)))
        groove = detect_groove(path)
        measured = self.main._measure_bpm(path)
        self.assertEqual(measured["bpm_measured"], groove["bpm"])
        self.assertNotEqual(measured["bpm_measured"], round(groove["bpm"], 1))
        settings = AppSettings()
        groups = {group["id"]: "keep" for group in settings.remix.groups}
        automatic = RemixProjectRequest(source_name=path.name, scope="groups", groups=groups, bpm=199)
        manual = automatic.model_copy(update={"source_bpm": groove["bpm"]})
        self.assertEqual(timeline_plan(automatic, seconds, settings, measured)["natural_duration_seconds"],
                         timeline_plan(manual, seconds, settings)["natural_duration_seconds"])


if __name__ == "__main__":
    unittest.main()
