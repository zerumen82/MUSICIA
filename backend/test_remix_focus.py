"""Regresiones del foco Batería por paso: corte y empalme sin desincronizar.

No llaman al motor ni a Demucs: comprueban la parte determinista que sostiene
el foco, que el tramo se corta por muestras y que el empalme conserva la
duración exacta del audio. La fidelidad musical sigue pendiente de una
generación real y de la escucha del usuario.
"""
import math
import tempfile
import unittest
from array import array
from pathlib import Path

from config import get_settings
from mixer_service import MixerService


class SegmentCutAndSpliceTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)
        self.settings = get_settings().remix
        self.rate = self.settings.sample_rate
        self.original = self._tone(440, 1.0, "original")

    def _tone(self, frequency: float, seconds: float, name: str) -> Path:
        samples = array("f")
        for index in range(int(round(seconds * self.rate))):
            value = 0.2 * math.sin(2 * math.pi * frequency * index / self.rate)
            samples.extend((value, value))
        path = self.folder / f"{name}.wav"
        MixerService._write_float_wav(path, samples, self.rate, 2)
        return path

    def _mix(self, parts: list[tuple[float, float]], seconds: float, name: str) -> Path:
        samples = array("f")
        for index in range(int(round(seconds * self.rate))):
            value = sum(amplitude * math.sin(2 * math.pi * frequency * index / self.rate)
                        for frequency, amplitude in parts)
            samples.extend((value, value))
        path = self.folder / f"{name}.wav"
        MixerService._write_float_wav(path, samples, self.rate, 2)
        return path

    def test_extract_keeps_the_requested_duration(self):
        output = self.folder / "tramo.wav"
        info = MixerService.extract_segment(self.original, output, 0.25, 0.75, self.settings)
        self.assertAlmostEqual(info["duration_seconds"], 0.5, places=6)
        self.assertAlmostEqual(
            MixerService.inspect_pcm(output)["duration_seconds"], 0.5, places=3)

    def test_splice_preserves_the_length_and_replaces_only_the_segment(self):
        replacement = self._tone(880, 0.5, "nueva")
        output = self.folder / "empalmado.wav"
        info = MixerService.splice_segment(
            self.original, replacement, 0.25, 0.75, output, self.settings)
        self.assertAlmostEqual(info["duration_seconds"], 1.0, places=6)
        pcm = MixerService.inspect_pcm(output)
        original = MixerService.inspect_pcm(self.original)
        self.assertEqual(len(pcm["samples"]), len(original["samples"]))
        channels = pcm["channels"]
        self.assertAlmostEqual(pcm["samples"][0], original["samples"][0], places=5)
        start = int(0.4 * self.rate) * channels
        end = int(0.6 * self.rate) * channels
        difference = sum(abs(new - old) for new, old in
                         zip(pcm["samples"][start:end], original["samples"][start:end]))
        self.assertGreater(difference, 1.0)

    def test_a_rounded_end_past_the_last_sample_is_clamped(self):
        short = self._tone(440, 0.9996, "casi-uno")
        output = self.folder / "recorte.wav"
        info = MixerService.extract_segment(short, output, 0.0, 1.0, self.settings)
        total = len(MixerService.inspect_pcm(short)["samples"]) // 2
        self.assertEqual(info["end_sample"], total)
        self.assertAlmostEqual(info["duration_seconds"], total / self.rate, places=6)

    def test_a_segment_really_outside_the_audio_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "duración real"):
            MixerService.extract_segment(self.original, self.folder / "fuera.wav",
                                         0.0, 1.5, self.settings)

    def test_splice_accepts_the_rounded_end_of_the_plan(self):
        short = self._tone(440, 0.9996, "casi-uno")
        replacement = self._tone(880, 0.9996, "nueva")
        info = MixerService.splice_segment(short, replacement, 0.0, 1.0,
                                           self.folder / "empalmado-corto.wav", self.settings)
        total = len(MixerService.inspect_pcm(short)["samples"]) // 2
        self.assertEqual(info["end_sample"], total)
        self.assertAlmostEqual(info["duration_seconds"], total / self.rate, places=6)

    def test_drum_threshold_does_not_reject_a_quiet_drum_track(self):
        vocals = self._mix([(300, 0.2)], 1.0, "voz")
        bass = self._mix([(100, 0.2)], 1.0, "bajo")
        other = self._mix([(150, 0.2)], 1.0, "resto")
        drums = self._mix([(60, 0.06)], 1.0, "bateria")
        generated = self._mix([(300, 0.2), (100, 0.2), (150, 0.2), (60, 0.06)], 1.0, "nueva")
        actions = {"drums": "transform", "vocals": "remove",
                   "bass": "remove", "other": "remove"}
        stems = {"vocals": vocals, "bass": bass, "other": other, "drums": drums}
        default = MixerService.render_single_transform(
            generated, stems, actions, drums, self.folder / "default.wav", self.settings)
        self.assertTrue(default["used_full_generation"])
        drums_only = MixerService.render_single_transform(
            generated, stems, actions, drums, self.folder / "bateria-sola.wav", self.settings,
            min_remaining_ratio=self.settings.drum_focus_min_remaining_ratio)
        self.assertFalse(drums_only["used_full_generation"])
        self.assertGreater(drums_only["remaining_ratio"],
                           self.settings.drum_focus_min_remaining_ratio)
        self.assertLess(drums_only["remaining_ratio"],
                        self.settings.single_transform_min_remaining_ratio)
        self.assertAlmostEqual(
            MixerService.inspect_pcm(self.folder / "bateria-sola.wav")["duration_seconds"],
            1.0, places=3)

    def test_a_replacement_with_another_duration_is_rejected(self):
        shorter = self._tone(880, 0.2, "corta")
        with self.assertRaisesRegex(ValueError, "duración"):
            MixerService.splice_segment(
                self.original, shorter, 0.25, 0.75, self.folder / "mala.wav", self.settings)


if __name__ == "__main__":
    unittest.main()
