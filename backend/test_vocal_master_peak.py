"""Pico real del master de «conservar voz» y cierre de handles (2026-11-17).

El master de MEZCLA/conservar voz publicaba el MP3 sin volver a medir el true
peak: la codificación podía dejarlo por encima del límite (se entregó un
fichero a +0,14 dBTP). Estas pruebas cubren la corrección y el cierre de los
descriptores que pydub deja abiertos.
"""

from __future__ import annotations

import gc
import json
import math
import sys
import tempfile
import unittest
import warnings
import wave
from array import array
from pathlib import Path
from unittest.mock import patch

BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from audio_service import process_audio  # noqa: E402
from mixer_service import (  # noqa: E402
    TARGET_TP,
    MixerService,
    master_peak_guard,
    normalize_track,
    peak_correction_db,
)
from music_service import MusicService  # noqa: E402


def _write_sine(path: Path, dbfs: float, seconds: float, rate: int = 48000) -> None:
    amplitude = round((10 ** (dbfs / 20)) * 32767)
    frames = array("h")
    for index in range(round(rate * seconds)):
        sample = round(amplitude * math.sin(2 * math.pi * 220 * index / rate))
        frames.extend((sample, sample))
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(2)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes(frames.tobytes())


class PeakCorrectionTest(unittest.TestCase):
    """La atenuación sale de la medida real, nunca de un valor inventado."""

    def test_correction_is_the_distance_to_the_limit(self):
        self.assertEqual(peak_correction_db({"input_tp": 0.14}, -1.0), -1.14)
        self.assertEqual(peak_correction_db({"input_tp": -1.0}, -1.0), 0.0)
        self.assertEqual(peak_correction_db({"input_tp": -2.5}, -1.0), 0.0)

    def test_unmeasurable_peak_fails_instead_of_publishing(self):
        for measured in ({}, {"input_tp": float("nan")}):
            with self.subTest(measured=measured), self.assertRaisesRegex(RuntimeError, "pico"):
                peak_correction_db(measured, -1.0)

    @patch("mixer_service.measure_loudness")
    def test_guard_rerenders_the_mix_attenuated(self, measure):
        measure.side_effect = [
            {"input_i": -14.0, "input_tp": 0.14},
            {"input_i": -15.1, "input_tp": -1.0},
        ]
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder) / "master.mp3"
            out.write_bytes(b"x")
            filters: list[str] = []
            info, gain = master_peak_guard(filters.append, out, "loudnorm=measured", -1.0)
        self.assertEqual(gain, -1.14)
        self.assertEqual(filters, ["loudnorm=measured,volume=-1.14dB"])
        self.assertEqual(info["input_tp"], -1.0)

    @patch("mixer_service.measure_loudness")
    def test_second_pass_keeps_the_accumulated_attenuation(self, measure):
        measure.side_effect = [
            {"input_i": -14.0, "input_tp": 0.5},
            {"input_i": -15.0, "input_tp": -0.6},
            {"input_i": -15.4, "input_tp": -1.0},
        ]
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder) / "master.mp3"
            out.write_bytes(b"x")
            filters: list[str] = []
            _, gain = master_peak_guard(filters.append, out, "loudnorm=measured", -1.0)
        self.assertEqual(gain, -1.9)
        self.assertEqual(filters, [
            "loudnorm=measured,volume=-1.5dB",
            "loudnorm=measured,volume=-1.9dB",
        ])

    @patch("mixer_service.measure_loudness", return_value={"input_i": -14.0, "input_tp": 0.5})
    def test_guard_removes_the_output_when_it_cannot_reach_the_limit(self, _measure):
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder) / "master.mp3"
            out.write_bytes(b"x")
            with self.assertRaisesRegex(RuntimeError, "pico"):
                master_peak_guard(lambda _filter: None, out, "loudnorm=measured", -1.0)
            self.assertFalse(out.exists())


class VocalMasterPeakTest(unittest.TestCase):
    """ffmpeg real: el master publicado no pasa del pico configurado."""

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="musicia-master-pico-")
        self.addCleanup(self.temporary.cleanup)
        self.work = Path(self.temporary.name)
        self.base = self.work / "base.wav"
        self.vocal = self.work / "vocal.wav"
        _write_sine(self.base, -6.0, 4.0)
        _write_sine(self.vocal, -12.0, 2.0)
        self.plan = {"placements": [
            {"at": 0.0, "seconds": 2.0, "source_start": 0.0, "source_end": 2.0}]}

    def test_arrange_master_honours_a_stricter_limit(self):
        reference = MixerService.arrange_vocals(
            str(self.base), str(self.vocal), str(self.work / "arreglo-referencia.mp3"),
            self.plan, normalize_lufs=True, fade_s=0.02,
        )
        # 1 dB por debajo del pico real: la corrección tiene que activarse.
        limit = round(reference["loudness"]["input_tp"] - 1.0, 2)
        output = self.work / "arreglo.mp3"
        result = MixerService.arrange_vocals(
            str(self.base), str(self.vocal), str(output), self.plan,
            normalize_lufs=True, fade_s=0.02, peak_limit_dbfs=limit,
        )
        self.assertTrue(output.exists())
        self.assertLess(result["peak_gain_db"], 0.0)
        self.assertLessEqual(result["loudness"]["input_tp"], limit + 0.01)
        self.assertEqual(result["target_true_peak_dbtp"], limit)

    def test_mix_master_honours_a_stricter_limit(self):
        reference = MixerService.mix_tracks(
            str(self.base), str(self.vocal), str(self.work / "mezcla-referencia.mp3"),
            normalize_lufs=True,
        )
        limit = round(reference["loudness"]["input_tp"] - 1.0, 2)
        output = self.work / "mezcla.mp3"
        result = MixerService.mix_tracks(
            str(self.base), str(self.vocal), str(output),
            normalize_lufs=True, peak_limit_dbfs=limit,
        )
        self.assertTrue(output.exists())
        self.assertLess(result["peak_gain_db"], 0.0)
        self.assertLessEqual(result["loudness"]["input_tp"], limit + 0.01)
        self.assertEqual(result["target_true_peak_dbtp"], limit)

    def test_normalize_track_honours_a_stricter_limit(self):
        reference = normalize_track(self.base, self.work / "pista-referencia.mp3")
        # 1 dB por debajo del pico real: la corrección tiene que activarse.
        limit = round(reference["loudness"]["input_tp"] - 1.0, 2)
        output = self.work / "pista.mp3"
        measured = normalize_track(self.base, output, peak_limit_dbfs=limit)
        self.assertTrue(output.exists())
        self.assertLessEqual(measured["loudness"]["input_tp"], limit + 0.01)

    @patch("mixer_service.measure_loudness", return_value={
        "input_i": -14.0, "input_tp": 0.5, "input_lra": 2.0, "input_thresh": -25.0})
    def test_normalize_track_removes_the_output_when_limit_is_unreachable(self, _measure):
        with self.assertRaisesRegex(RuntimeError, "pico"):
            normalize_track(self.base, self.work / "pista-saturada.mp3")
        self.assertFalse((self.work / "pista-saturada.mp3").exists())

    def test_master_never_exceeds_the_streaming_limit(self):
        for name, call in (
            ("arreglo", lambda out: MixerService.arrange_vocals(
                str(self.base), str(self.vocal), str(out), self.plan,
                normalize_lufs=True, fade_s=0.02)),
            ("mezcla", lambda out: MixerService.mix_tracks(
                str(self.base), str(self.vocal), str(out), normalize_lufs=True)),
        ):
            with self.subTest(master=name):
                output = self.work / f"{name}.mp3"
                result = call(output)
                self.assertLessEqual(result["loudness"]["input_tp"], TARGET_TP + 0.1)
                self.assertEqual(result["target_true_peak_dbtp"], TARGET_TP)
                self.assertIn("peak_gain_db", result)


class FichaPeakTest(unittest.TestCase):
    """2026-11-17: la ficha del MP3 publicado lleva los datos de pico reales."""

    def test_write_ficha_records_the_published_peak(self):
        import main

        with tempfile.TemporaryDirectory() as folder:
            audio = Path(folder) / "tema.mp3"
            audio.write_bytes(b"x")
            main._write_ficha(audio, {
                "prompt": "gabber", "task_type": "text2music", "peak_gain_db": -0.27,
                "target_true_peak_dbtp": -1.0,
                "loudness": {"input_i": -14.2, "input_tp": -1.01},
            })
            data = json.loads(audio.with_suffix(".ficha.json").read_text(encoding="utf-8"))
        self.assertEqual(data["peak_gain_db"], -0.27)
        self.assertEqual(data["target_true_peak_dbtp"], -1.0)
        self.assertEqual(data["published_true_peak_dbtp"], -1.01)

    def test_carry_ficha_keeps_the_mix_peak_from_the_mixer(self):
        import main

        with tempfile.TemporaryDirectory() as folder:
            work = Path(folder)
            base, vocal, mixed = work / "base.wav", work / "vocal.wav", work / "mezcla.mp3"
            _write_sine(base, -6.0, 3.0)
            _write_sine(vocal, -12.0, 2.0)
            source = work / "fuente.mp3"
            _write_sine(source, -9.0, 1.0)
            info = MixerService.mix_tracks(str(base), str(vocal), str(mixed), normalize_lufs=True)
            main._carry_ficha(source, mixed, "remix",
                              peak_gain_db=info["peak_gain_db"],
                              target_true_peak_dbtp=info["target_true_peak_dbtp"],
                              published_true_peak_dbtp=info["loudness"]["input_tp"])
            data = json.loads(mixed.with_suffix(".ficha.json").read_text(encoding="utf-8"))
        self.assertEqual(data["peak_gain_db"], info["peak_gain_db"])
        self.assertEqual(data["target_true_peak_dbtp"], info["target_true_peak_dbtp"])
        self.assertEqual(data["published_true_peak_dbtp"], info["loudness"]["input_tp"])

    def test_library_exposes_the_peak_but_not_invented_values(self):
        """La biblioteca entrega el pico y la atenuación; sin ficha, None."""
        import asyncio
        import main

        with tempfile.TemporaryDirectory() as folder:
            outputs = Path(folder)
            with_peak = outputs / "con-pico.mp3"
            with_peak.write_bytes(b"x")
            main._write_ficha(with_peak, {
                "prompt": "gabber", "task_type": "remix", "peak_gain_db": -0.27,
                "target_true_peak_dbtp": -1.0,
                "loudness": {"input_i": -13.86, "input_tp": -1.09},
            })
            (outputs / "sin-ficha.mp3").write_bytes(b"y")
            with patch.object(main.settings.paths, "outputs_dir", str(outputs)):
                data = asyncio.run(main.music_library())
        items = {item["name"]: item for item in data["items"]}
        self.assertEqual(items["con-pico.mp3"]["published_true_peak_dbtp"], -1.09)
        self.assertEqual(items["con-pico.mp3"]["peak_gain_db"], -0.27)
        self.assertIsNone(items["sin-ficha.mp3"]["published_true_peak_dbtp"])
        self.assertIsNone(items["sin-ficha.mp3"]["peak_gain_db"])


class AudioHandleTest(unittest.IsolatedAsyncioTestCase):
    """2026-11-17: pydub deja el descriptor abierto al leer/exportar."""

    async def test_verify_audio_closes_the_file_it_reads(self):
        with tempfile.TemporaryDirectory() as folder:
            clip = Path(folder) / "clip.wav"
            _write_sine(clip, -20.0, 1.0)
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                duration = await MusicService.verify_audio(clip)
                gc.collect()
            self.assertAlmostEqual(duration, 1000.0, delta=60.0)
            self.assertEqual(
                [w for w in caught if issubclass(w.category, ResourceWarning)], [])

    def test_exported_audio_can_be_deleted_right_away(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "source.wav"
            output = Path(folder) / "salida.mp3"
            _write_sine(source, -12.0, 1.5)
            process_audio(source, output, gain_db=1.0)
            output.unlink()  # En Windows falla si el handle de export sigue abierto


if __name__ == "__main__":
    unittest.main()
