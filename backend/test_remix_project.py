"""Contratos que evitan decisiones musicales y mezclas incompatibles."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import AppSettings, engine_launch_timeout_seconds
from music_service import GenerationRequest, MusicService
from remix_project import RemixProjectRequest, validate_project


class RemixContractTest(unittest.TestCase):
    def setUp(self):
        self.settings = AppSettings()

    def request(self, **overrides):
        return RemixProjectRequest(source_name="original.wav", prompt="Batería suave al fondo", **overrides)

    def groups(self, **overrides):
        actions = {group["id"]: "keep" for group in self.settings.remix.groups}
        actions.update(overrides)
        return actions

    def test_engine_launch_timeout_outlasts_the_factory_600s_cut(self):
        seconds = engine_launch_timeout_seconds(self.settings)
        self.assertGreater(seconds, 600)
        self.assertEqual(seconds, int(self.settings.acestep.job_timeout))

    def test_timeline_keyboard_step_comes_from_configuration(self):
        nudge = self.settings.remix.parameters["timeline_nudge_seconds"]
        self.assertGreater(nudge["step"], 0)
        self.assertLessEqual(nudge["step"], nudge["max"])

    def test_whole_prompt_and_absence_of_new_lyrics_do_not_order_instrumental(self):
        music = MusicService(self.settings)
        for task in ("cover", "repaint"):
            payload = music.build_payload(GenerationRequest(
                prompt="Mantén la voz; cambia únicamente la batería", task_type=task,
                source_path="original.wav", instrumental=None,
            ))
            self.assertEqual(payload["prompt"], "Mantén la voz; cambia únicamente la batería")
            self.assertEqual(payload["lyrics"], "")
            self.assertNotEqual(payload["lyrics"], self.settings.generation.instrumental_marker)
            self.assertEqual(payload["audio_duration"], -1)
            self.assertFalse(payload["thinking"])

    def test_explicit_instrumental_is_still_transmitted(self):
        payload = MusicService(self.settings).build_payload(GenerationRequest(
            prompt="Sin voz", task_type="cover", source_path="original.wav", instrumental=True))
        self.assertEqual(payload["lyrics"], self.settings.generation.instrumental_marker)

    def test_native_controls_reference_and_lossless_output_survive_payload(self):
        payload = MusicService(self.settings).build_payload(GenerationRequest(
            prompt="Cambio regional", task_type="repaint", source_path="original.wav",
            reference_path="reference.wav", repaint_start=2, repaint_end=4,
            cover_noise_strength=0.8, repaint_mode="conservative", repaint_strength=0.2,
            repaint_wav_crossfade_sec=0.15, repaint_latent_crossfade_frames=4,
            audio_format="wav32", seed=123))
        self.assertEqual(payload["reference_audio_path"], "reference.wav")
        self.assertEqual(payload["audio_format"], "wav32")
        self.assertEqual(payload["repainting_start"], 2)
        self.assertEqual(payload["repainting_end"], 4)
        self.assertEqual(payload["chunk_mask_mode"], "explicit")
        self.assertEqual(payload["repaint_mode"], "conservative")
        self.assertEqual(payload["repaint_wav_crossfade_sec"], AppSettings().remix.repaint_resolution_max_wav_seconds)
        self.assertNotEqual(payload["repaint_wav_crossfade_sec"], 0.15)
        self.assertFalse(payload["use_random_seed"])
        self.assertEqual(payload["batch_size"], 2)

    def test_classifier_category_never_changes_parameters(self):
        electronic = self.request(source_classification="electronic")
        acoustic = self.request(source_classification="non_electronic")
        validate_project(electronic, 30, self.settings)
        validate_project(acoustic, 30, self.settings)
        left, right = electronic.model_dump(), acoustic.model_dump()
        left.pop("source_classification")
        right.pop("source_classification")
        self.assertEqual(left, right)

    def test_imaginary_instrument_group_rejected(self):
        request = self.request(scope="groups", groups=self.groups(guitar="keep"))
        with self.assertRaisesRegex(ValueError, "grupo real"):
            validate_project(request, 30, self.settings)

    def test_region_must_be_inside_source(self):
        for start, end in ((-1, 2), (5, 5), (3, 31), (float("nan"), 20), (None, 20)):
            with self.subTest(start=start, end=end), self.assertRaises(ValueError):
                validate_project(self.request(scope="region", region_start=start, region_end=end), 30, self.settings)

    def test_common_tempo_accepts_retained_groups_and_requires_reliable_source_bpm(self):
        from remix_project import timeline_plan
        request = self.request(scope="groups", groups=self.groups(drums="transform"), bpm=180)
        validate_project(request, 30, self.settings)
        with self.assertRaisesRegex(ValueError, "BPM original fiable"):
            timeline_plan(request, 30, self.settings)
        plan = timeline_plan(request, 30, self.settings, {"bpm_measured": 120, "bpm_confidence": 0.9})
        self.assertEqual(plan["tempo_ratio"], 1.5)
        self.assertEqual(plan["natural_duration_seconds"], 20)

    def test_keep_voice_cannot_also_remove_voice_with_instrumental(self):
        request = self.request(scope="groups", groups=self.groups(drums="transform"), instrumental=True)
        with self.assertRaisesRegex(ValueError, "incompatibles"):
            validate_project(request, 30, self.settings)

    def test_all_removed_and_nonfinite_gains_rejected(self):
        with self.assertRaisesRegex(ValueError, "todos los grupos"):
            validate_project(self.request(scope="groups", groups=self.groups(**{
                group["id"]: "remove" for group in self.settings.remix.groups})), 30, self.settings)
        for value in (float("nan"), float("inf"), self.settings.remix.parameters["gain_db"]["max"] + 1):
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_project(self.request(scope="groups", groups=self.groups(), gains_db={"bass": value}), 30, self.settings)

    def test_deterministic_removal_does_not_require_a_generation_prompt(self):
        request = RemixProjectRequest(source_name="original.wav", scope="groups",
                                      groups=self.groups(vocals="remove"))
        validate_project(request, 30, self.settings)

    def test_regional_fields_not_silently_ignored_in_full_cover(self):
        with self.assertRaisesRegex(ValueError, "solo se aplica"):
            validate_project(self.request(region_start=3, region_end=5), 30, self.settings)

    def test_source_digest_runs_on_this_python_and_identifies_content(self):
        """Regresión 2026-10-12: `hashlib.file_digest` (3.11+) rompió un job real."""
        import tempfile
        from remix_project import source_digest

        with tempfile.TemporaryDirectory() as folder:
            first, second = Path(folder) / "a.wav", Path(folder) / "b.wav"
            first.write_bytes(b"musicia-origen")
            second.write_bytes(b"musicia-origen")
            digest = source_digest(first)
            self.assertEqual(len(digest), 64)
            self.assertEqual(digest, source_digest(second))
            second.write_bytes(b"musicia-distinto")
            self.assertNotEqual(digest, source_digest(second))


if __name__ == "__main__":
    unittest.main()
