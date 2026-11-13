"""R20.F regressions: truthful repeated pattern measurement and caption identity."""
import asyncio
import inspect
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
from pydub import AudioSegment

sys.path.insert(0, str(Path(__file__).resolve().parent))
import audio_analysis
import remix_project
import remix_sequence
from config import AppSettings


class PatternContractTest(unittest.TestCase):
    def setUp(self):
        self.settings = AppSettings()
        self.config = self.settings.remix

    def pattern(self, marks=(1, 5, 9, 13), **rows):
        rows.setdefault("kick", marks)
        count = self.config.pattern_steps
        return remix_sequence.SequencePattern(**{
            name: [index + 1 in positions for index in range(count)]
            for name, positions in rows.items()
        })

    def check(self, pattern, onsets, bpm=120, duration=8, beats=4):
        # Supports the old signature only to preserve executable red evidence.
        extra = {}
        signature = inspect.signature(remix_sequence.check_kick_pattern).parameters
        for key, value in {"duration_seconds": duration, "beats_per_bar": beats,
                           "config": self.config}.items():
            if key in signature:
                extra[key] = value
        return remix_sequence.check_kick_pattern(pattern, onsets, bpm, **extra)

    def test_first_bar_only_cannot_credit_four_bars(self):
        result = self.check(self.pattern(), [0, .5, 1, 1.5])
        self.assertEqual(result["coverage"], .25)
        self.assertEqual(result["expected_count"], 16)
        self.assertEqual(result["hit_count"], 4)
        self.assertEqual(len(result["missed_events"]), 12)

    def test_perfect_repeat_has_no_extra_hits(self):
        result = self.check(self.pattern(), [index * .5 for index in range(16)])
        self.assertEqual(result["extra_onsets_s"], [])
        self.assertEqual(result["expected_count"], 16)
        self.assertEqual(result["hit_count"], 16)
        self.assertEqual(result["coverage"], 1)

    def test_one_onset_never_satisfies_two_targets(self):
        result = self.check(self.pattern((1, 2)), [.03125], bpm=240, duration=1)
        self.assertLessEqual(len(result["hit"]), 1)
        self.assertLessEqual(result["coverage"], .5)

    def test_partial_last_bar_is_counted_only_before_section_end(self):
        result = self.check(self.pattern(), [0, .5, 1, 1.5, 2, 2.5, 3], duration=3.1)
        self.assertEqual(result["expected_count"], 7)
        self.assertEqual(result["hit_count"], 7)
        self.assertEqual(result["hit_events"][-1]["bar"], 2)
        self.assertEqual(result["hit_events"][-1]["step"], 9)

    def test_configurable_resolution_instruments_and_meter_agree(self):
        self.config.pattern_steps = 8
        self.config.pattern_instruments = ["kick", "hihat"]
        pattern = self.pattern((1, 5), hihat=(3, 7))
        step = remix_sequence.SequenceStep(index=0, prompt="drums", pattern=pattern)
        remix_sequence.validate_steps([step], self.config)
        result = self.check(pattern, [0, .75, 1.5, 2.25], duration=3, beats=3)
        self.assertEqual(result["expected_count"], 4)
        self.assertEqual(result["coverage"], 1)
        caption = remix_sequence.compile_pattern_text(pattern, config=self.config, beats_per_bar=3)
        self.assertIn("8", caption)
        self.assertIn("3/4", caption)

    def test_cymbal_hihat_and_legacy_clap_have_distinct_identity(self):
        pattern = self.pattern((), hihat=(2,), cymbal=(4,), clap=(6,))
        remix_sequence.validate_steps([remix_sequence.SequenceStep(index=0, prompt="drums", pattern=pattern)], self.config)
        caption = remix_sequence.compile_pattern_text(pattern)
        self.assertIn("hihat", caption)
        self.assertIn("cymbal", caption)
        self.assertIn("clap", caption)
        self.assertNotIn("whistle", caption)

    def test_caption_declares_unit_repetition_priority_and_keeps_details(self):
        caption = remix_sequence.step_caption("No drums; my own detail", self.pattern((1,)))
        self.assertTrue(caption.startswith("Drums:"))
        self.assertIn("16", caption)
        self.assertIn("4/4", caption)
        self.assertIn("repeat", caption.lower())
        self.assertIn("priorit", caption.lower())
        self.assertIn("conflict", caption.lower())
        self.assertIn("No drums; my own detail", caption)

    def test_preview_and_execution_share_post_translation_pattern_caption(self):
        pattern = self.pattern((1,), hihat=tuple(range(1, 17)))
        step = remix_sequence.SequenceStep(index=0, prompt="sin voz", pattern=pattern)
        request = remix_project.RemixProjectRequest(source_name="original.wav", scope="sequence", steps=[step])
        timeline = remix_sequence.sequence_timeline(8, 120, [step], self.config, 4)
        source = Path("original.wav")
        seen = []

        def translate(text, _settings):
            seen.append(text)
            return text.replace("sin voz", "without vocals").replace("hihat", "whistle")

        with patch.object(remix_project, "style_for_engine", side_effect=translate):
            preview = remix_project.sequence_preview_request(request, timeline, source, None, self.settings)
            if hasattr(remix_project, "sequence_step_generation"):
                execution = remix_project.sequence_step_generation(request, timeline["steps"][0], source, None, self.settings, position=0)
            else:
                execution = remix_project.project_generation(request.model_copy(update={
                    "scope": "region", "prompt": remix_sequence.step_caption(step.prompt, pattern),
                    "region_start": 0, "region_end": 8, "batch_size": 1}), source, None, self.settings)
        self.assertEqual(preview.prompt, execution.prompt)
        self.assertIn("hihat", execution.prompt)
        self.assertNotIn("whistle", execution.prompt)
        self.assertTrue(all("hihat" not in text for text in seen))
        self.assertIn("without vocals", execution.prompt)

    def test_the_pattern_is_measured_on_the_final_output(self):
        """La rejilla se mide sobre el archivo publicado, no sobre el intermedio."""
        config = self.config
        # Se marcan los pasos 5 y 9: un golpe en 0,000 s no lo ve el detector
        # (necesita una ventana previa), y esta prueba es de la medición final.
        pattern = self.pattern((5, 9))
        bpm = 120.0
        rate = self.settings.remix.sample_rate
        spacing = 60 / bpm * self.settings.mixer.beats_per_bar / config.pattern_steps
        duration = 8.0
        samples = np.zeros(int(rate * duration))
        for bar in range(4):
            for step in (5, 9):
                start = int((bar * 2 + (step - 1) * spacing) * rate)
                time = np.arange(int(.05 * rate)) / rate
                burst = .8 * np.sin(2 * np.pi * 70 * time) * np.exp(-time * 80)
                samples[start:start + len(burst)] += burst
        audio = AudioSegment((np.clip(samples, -1, 1) * 32767).astype("<i2").tobytes(),
                              sample_width=2, channels=1, frame_rate=rate)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "final.wav"
            audio.export(path, format="wav")
            job = {"steps": [{"index": 0, "start": 0.0, "end": duration, "status": "done"}]}
            plan = {"steps": [{"index": 0, "pattern": pattern.model_dump(mode="json")}],
                    "source_bpm": bpm}
            runtime = SimpleNamespace(settings=self.settings)
            asyncio.run(remix_project.RemixProjectRuntime._measure_final_patterns(
                runtime, job, path, plan, config))
        check = job["steps"][0]["pattern_check"]
        self.assertTrue(check["measured"], check)
        self.assertEqual(check["measurement_stage"], "final_output")
        self.assertEqual(check["expected_count"], 8)
        self.assertEqual(check["hit_count"], 8, check)
        self.assertEqual(check["coverage"], 1, check)

    def test_a_step_that_was_not_redone_is_declared_without_measuring(self):
        config = self.config
        pattern = self.pattern((1,))
        job = {"steps": [{"index": 0, "start": 0.0, "end": 4.0, "status": "kept"}]}
        plan = {"steps": [{"index": 0, "pattern": pattern.model_dump(mode="json")}],
                "source_bpm": 120.0}
        runtime = SimpleNamespace(settings=self.settings)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "final.wav"
            AudioSegment.silent(duration=4000, frame_rate=self.settings.remix.sample_rate).export(path, format="wav")
            asyncio.run(remix_project.RemixProjectRuntime._measure_final_patterns(
                runtime, job, path, plan, config))
        check = job["steps"][0]["pattern_check"]
        self.assertFalse(check["measured"])
        self.assertEqual(check["measurement_stage"], "final_output")
        self.assertIn("material original", check["reason"])

    def test_dense_grid_detector_resolves_real_160bpm_kick_bursts(self):
        bpm = 160
        rate = self.settings.remix.sample_rate
        spacing = 60 / bpm * self.settings.mixer.beats_per_bar / self.config.pattern_steps
        duration = 1.9
        samples = np.zeros(int(rate * duration))
        for index in range(16):
            start = int((.15 + index * spacing) * rate)
            time = np.arange(int(.045 * rate)) / rate
            burst = .8 * np.sin(2 * np.pi * 80 * time) * np.exp(-time * 90)
            samples[start:start + len(burst)] += burst
        audio = AudioSegment((np.clip(samples, -1, 1) * 32767).astype("<i2").tobytes(), frame_rate=rate, sample_width=2, channels=1)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "dense.wav"
            audio.export(path, format="wav")
            kwargs = {}
            if hasattr(remix_sequence, "pattern_onset_gap_ms"):
                kwargs["min_gap_ms"] = remix_sequence.pattern_onset_gap_ms(bpm, self.settings.mixer.beats_per_bar, self.config)
            onsets = audio_analysis.kick_onset_times(path, **kwargs)
        self.assertGreaterEqual(len(onsets), 15, onsets)


if __name__ == "__main__":
    unittest.main()
