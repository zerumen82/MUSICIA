"""Real PCM boundaries for continuation screening and honest preserved lyrics."""
from __future__ import annotations

import array
import ast
import asyncio
import math
from dataclasses import replace
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
import wave

from loguru import logger

from config import AppSettings
from mixer_service import TARGET_LUFS, MixerService
from remix_project import screen_continuation_chunk
from test_kick_coverage import _write_signal


def stereo_copy(source: Path, target: Path) -> None:
    with wave.open(str(source), "rb") as handle:
        rate = handle.getframerate()
        mono = array.array("h", handle.readframes(handle.getnframes()))
    stereo = array.array("h", (value for sample in mono for value in (sample, sample)))
    with wave.open(str(target), "wb") as handle:
        handle.setnchannels(2)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes(stereo.tobytes())


class ContinuationFrameDurationTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="musicia-frame-screen-")
        self.addCleanup(self.temporary.cleanup)
        self.work = Path(self.temporary.name)
        self.mono = self.work / "mono.wav"
        self.stereo = self.work / "stereo.wav"
        _write_signal(self.mono, 120.0, 12.0)
        stereo_copy(self.mono, self.stereo)
        self.config = replace(AppSettings().remix, continuation_min_seconds=6.0)

    def test_mono_and_stereo_eight_second_regions_pass_the_same_real_screen(self):
        for channels, source in ((1, self.mono), (2, self.stereo)):
            with self.subTest(channels=channels):
                stem = f"usable-{channels}"
                notice = screen_continuation_chunk(
                    source, {"start": 2.0, "end": 10.0}, 120.0,
                    self.config, self.work, stem,
                )
                self.assertIsNone(notice)
                clipped = MixerService.inspect_pcm(self.work / f"{stem}-pulso.wav")
                original = MixerService.inspect_pcm(source)
                self.assertEqual(clipped["channels"], channels)
                self.assertEqual(len(clipped["samples"]) // channels, 8 * clipped["sample_rate"])
                start = 2 * original["sample_rate"] * channels
                end = 10 * original["sample_rate"] * channels
                self.assertEqual(clipped["samples"], original["samples"][start:end])

    def test_the_configured_duration_gate_is_independent_of_channel_count(self):
        # The groove detector still requires eight seconds. This checks whether
        # a region reaches that real detector, not whether six seconds is music.
        for channels, source in ((1, self.mono), (2, self.stereo)):
            for seconds, reaches_detector in ((5.5, False), (6.0, True), (6.5, True)):
                with self.subTest(channels=channels, seconds=seconds):
                    stem = f"gate-{channels}-{seconds}"
                    notice = screen_continuation_chunk(
                        source, {"start": 0.0, "end": seconds}, 120.0,
                        self.config, self.work, stem,
                    )
                    self.assertIsNotNone(notice)
                    self.assertEqual((self.work / f"{stem}-pulso.wav").exists(), reaches_detector)

    def test_outside_limits_are_clamped_to_actual_frames(self):
        notice = screen_continuation_chunk(
            self.stereo, {"start": -2.0, "end": 20.0}, 120.0,
            self.config, self.work, "clamped",
        )
        self.assertIsNone(notice)
        clipped = MixerService.inspect_pcm(self.work / "clamped-pulso.wav")
        original = MixerService.inspect_pcm(self.stereo)
        self.assertEqual(clipped["samples"], original["samples"])


class PreservedLyricsContractTest(unittest.TestCase):
    def test_written_phrases_remain_literal_without_calling_engine_or_claiming_structure(self):
        source = Path(__file__).with_name("main.py")
        definition = next(node for node in ast.parse(source.read_text(encoding="utf-8-sig")).body
                          if isinstance(node, ast.AsyncFunctionDef) and node.name == "music_write_lyrics")
        definition.decorator_list = []
        definition.returns = None
        for argument in definition.args.args:
            argument.annotation = None
        namespace = {"logger": logger}
        exec(compile(ast.Module(body=[definition], type_ignores=[]), str(source), "exec"), namespace)
        phrases = "La ciudad sigue despierta\nConservo mis palabras"
        result = asyncio.run(namespace["music_write_lyrics"](SimpleNamespace(
            lyrics=phrases, prompt="a melodic song", language="es",
        )))
        self.assertEqual(result["lyrics"], phrases)
        self.assertEqual(result["source"], "tus_frases")
        self.assertEqual(result["caption"], "a melodic song")
        self.assertEqual(result["vocal_language"], "es")
        self.assertNotIn("construido", result["warning"].lower())
        for section in ("verso", "estribillo", "puente"):
            self.assertNotIn(section, result["warning"].lower())
        self.assertIn("conserv", result["warning"].lower())


class RemixMasterLoudnessTest(unittest.TestCase):
    """[R20.L] La exportación de remix lleva master real, no solo pico."""

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="musicia-remix-master-")
        self.addCleanup(self.temporary.cleanup)
        self.work = Path(self.temporary.name)
        self.config = AppSettings().remix

    def _sine(self, path: Path, dbfs: float, seconds: float = 8.0) -> None:
        amplitude = round((10 ** (dbfs / 20)) * 32767)
        rate = self.config.sample_rate
        mono = array.array(
            "h",
            (round(amplitude * math.sin(2 * math.pi * 220 * index / rate))
             for index in range(round(rate * seconds))),
        )
        stereo = array.array("h", (value for sample in mono for value in (sample, sample)))
        with wave.open(str(path), "wb") as handle:
            handle.setnchannels(2)
            handle.setsampwidth(2)
            handle.setframerate(rate)
            handle.writeframes(stereo.tobytes())

    def test_weak_and_loud_sources_reach_the_streaming_master(self):
        # Dos niveles muy distintos: el master no puede depender de cómo
        # llegue el intermedio (antes, el débil se entregaba 19 dB bajo).
        for dbfs in (-30.0, -6.0):
            with self.subTest(source_dbfs=dbfs):
                source = self.work / f"fuente-{abs(int(dbfs))}.wav"
                self._sine(source, dbfs)
                output = self.work / f"salida-{abs(int(dbfs))}.mp3"
                result = MixerService.export_remix(source, output, self.config)
                self.assertGreater(output.stat().st_size, 0)
                self.assertAlmostEqual(result["loudness"]["input_i"], TARGET_LUFS, delta=1.0)
                self.assertLessEqual(
                    result["loudness"]["input_tp"], self.config.peak_limit_dbfs + 0.1)
                self.assertEqual(result["target_lufs"], TARGET_LUFS)
                self.assertNotEqual(result["normalization"], "peak attenuation only")


if __name__ == "__main__":
    unittest.main()
