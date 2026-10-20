"""Contratos R11 y PCM real: tempo común y ampliación sin cola de silencio."""
import math
import asyncio
import tempfile
import unittest
from array import array
from pathlib import Path

from config import AppSettings
from mixer_service import MixerService, stems_kept_out_of_single_transform, stems_peeled_from_transformed_bed
from music_service import MusicService
from remix_project import (RemixProjectRequest, RemixProjectRuntime, timeline_plan, validate_project,
                           accept_measured_draw, accept_verified_draw, audio_has_no_usable_groove, full_groove_retries,
                           full_variant_failure, unmeasured_variant_notice, unpublished_batch_error,
                           full_bpm_preview_notice,
                           full_variant_plan, project_generation, replacement_request_seed,
                           groups_tempo_ratio, apply_groups_mix_tempo, tempo_after_repetition,
                           continuation_spans, continuation_generation, continuation_limits,
                           uncertain_extension_fallback,
                           uncertain_mix_notice, mark_uncertain_mix_tempo,
                           verify_requested_tempo, require_measured_tempo)
from separator_service import SeparatorService


class RemixTimelineTest(unittest.TestCase):
    def test_repetition_period_keeps_the_pulse_already_measured(self):
        config = self.settings.remix
        measured = {"bpm_measured": 39.47, "bpm_confidence": 0.732}
        periods = [{"bpm": 39.47, "evidence": 0.8268, "confidence": 0.732},
                   {"bpm": 199.00, "evidence": 0.5683, "confidence": 0.130}]
        arrangement = {"method": "repeat_crossfade", "beats_per_repetition": 15,
                       "repetition_stride_seconds": 15 * 60 / 197.37, "beat_clock_bpm": 197.37}
        result = tempo_after_repetition(measured, periods, arrangement, config)
        self.assertEqual(result["bpm_measured"], 199.0)
        self.assertEqual(result["repetition_bpm_measured"], 39.47)
        verify_requested_tempo(result, 199, config, "después del arreglo")

    def test_repetition_rule_does_not_invent_a_pulse_or_chase_the_request(self):
        config = self.settings.remix
        weak = tempo_after_repetition(
            {"bpm_measured": 39.47, "bpm_confidence": 0.732},
            [{"bpm": 39.47, "evidence": 0.8268, "confidence": 0.732},
             {"bpm": 199.00, "evidence": 0.5683, "confidence": 0.05}],
            {"method": "repeat_crossfade", "beats_per_repetition": 15,
             "repetition_stride_seconds": 15 * 60 / 197.37, "beat_clock_bpm": 197.37}, config)
        self.assertEqual(weak["bpm_measured"], 39.47)
        self.assertNotIn("repetition_bpm_measured", weak)
        other = tempo_after_repetition(
            {"bpm_measured": 50.0, "bpm_confidence": 0.8},
            [{"bpm": 50.0, "evidence": 0.9, "confidence": 0.8},
             {"bpm": 199.0, "evidence": 0.7, "confidence": 0.4}],
            {"method": "repeat_crossfade", "beats_per_repetition": 4,
             "repetition_stride_seconds": 4 * 60 / 100, "beat_clock_bpm": 100.0}, config)
        self.assertEqual(other["bpm_measured"], 50.0)
        unrelated = tempo_after_repetition(
            {"bpm_measured": 80.0, "bpm_confidence": 0.4},
            [{"bpm": 80.0, "evidence": 0.5, "confidence": 0.4},
             {"bpm": 197.37, "evidence": 0.7, "confidence": 0.5}],
            {"method": "repeat_crossfade", "beats_per_repetition": 15,
             "repetition_stride_seconds": 15 * 60 / 197.37, "beat_clock_bpm": 197.37}, config)
        self.assertEqual(unrelated["bpm_measured"], 80.0)


    def setUp(self):
        self.settings = AppSettings()
        self.groups = {group["id"]: "keep" for group in self.settings.remix.groups}

    def request(self, **kwargs):
        return RemixProjectRequest(source_name="source.wav", scope="groups", groups=self.groups, **kwargs)

    def test_manual_tempo_maps_section_and_duration_once(self):
        request = self.request(bpm=150, source_bpm=120, duration_seconds=35,
                               repeat_start=2, repeat_end=8, transition_seconds=0.1)
        validate_project(request, 20, self.settings)
        plan = timeline_plan(request, 20, self.settings)
        self.assertEqual(plan["source_bpm_origin"], "manual")
        self.assertEqual(plan["natural_duration_seconds"], 16)
        self.assertEqual(plan["mapped_repeat_start"], 1.6)
        self.assertEqual(plan["mapped_repeat_end"], 6.4)
        self.assertEqual(plan["target_duration_seconds"], 35)
        self.assertEqual(plan["method"], "continue_bed")

    def test_short_duration_reports_concrete_rounded_minimum(self):
        request = self.request(bpm=199, source_bpm=166.25, duration_seconds=60)
        with self.assertRaisesRegex(ValueError, r"mínimo 69 s \(1:09\)"):
            timeline_plan(request, 81.4, self.settings)

    def test_full_preview_waits_for_independent_generated_tempo(self):
        request = RemixProjectRequest(source_name="source.wav", prompt="A track with techno", bpm=199,
                                      duration_seconds=30, repeat_start=2, repeat_end=8)
        preview = timeline_plan(request, 20, self.settings)
        self.assertIsNone(preview["tempo_ratio"])
        self.assertIsNone(preview["natural_duration_seconds"])
        self.assertIsNone(preview["mapped_repeat_start"])
        self.assertEqual(preview["status"], "pending_generated_audio")
        measured = {"bpm_measured": 100, "bpm_confidence": 0.5}
        plan = full_variant_plan(request, 20, 20.1, self.settings, measured)
        self.assertAlmostEqual(plan["tempo_ratio"], 1.99)
        self.assertAlmostEqual(plan["natural_duration_seconds"], 20.1 / 1.99)
        self.assertAlmostEqual(plan["mapped_repeat_start"], 2 * 20.1 / 20 / 1.99)
        other = full_variant_plan(request, 20, 19.9, self.settings,
                                  {"bpm_measured": 150, "bpm_confidence": 0.5})
        self.assertNotEqual(other["natural_duration_seconds"], plan["natural_duration_seconds"])
        self.assertIsNone(preview["tempo_ratio"])
        self.assertEqual(plan["tempo_method"], "measured_pcm_atempo")

    def test_full_uncertainty_and_wrong_final_tempo_are_errors(self):
        request = RemixProjectRequest(source_name="source.wav", prompt="A track with techno", bpm=199)
        for measured in (None, {}, {"bpm_measured": 100, "bpm_confidence": 0.01},
                         {"bpm_measured": float("nan"), "bpm_confidence": 0.5}):
            with self.subTest(measured=measured), self.assertRaisesRegex(ValueError, "BPM fiable"):
                full_variant_plan(request, 20, 20, self.settings, measured)
        with self.assertRaisesRegex(ValueError, "no cumple"):
            verify_requested_tempo({"bpm_measured": 100, "bpm_confidence": 0.9},
                                   199, self.settings.remix, "tras exportar")

    def test_full_dsp_changes_real_pulses_without_changing_carrier_pitch(self):
        from audio_analysis import detect_groove
        rate, seconds, bpm, carrier = 8000, 12, 120, 220
        config = self.settings.remix
        config.sample_rate = rate
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            source, output = directory / "source.wav", directory / "tempo.wav"
            samples = array("f", ((0.6 if (frame / rate) % (60 / bpm) < 0.10 else 0.04)
                                 * math.sin(2 * math.pi * carrier * frame / rate)
                                 for frame in range(rate * seconds) for _ in range(2)))
            MixerService._write_float_wav(source, samples, rate, 2)
            before = detect_groove(source)
            request = RemixProjectRequest(source_name="source.wav", prompt="A track with techno", bpm=150)
            plan = full_variant_plan(request, seconds, seconds, self.settings,
                                     {"bpm_measured": before["bpm"], "bpm_confidence": before["confidence"]})
            MixerService.tempo_audio(source, output, plan["tempo_ratio"], plan["natural_duration_seconds"], config)
            after = detect_groove(output)
            verify_requested_tempo({"bpm_measured": after["bpm"], "bpm_confidence": after["confidence"]},
                                   request.bpm, config, "tras DSP")
            pcm = MixerService.inspect_pcm(output)
            self.assertAlmostEqual(pcm["duration_seconds"], plan["natural_duration_seconds"], places=3)
            # Cruces positivos de una portadora continua, en una ventana interior.
            mono = pcm["samples"][rate * 2:rate * 4:2]
            crossings = sum(a <= 0 < b for a, b in zip(mono, mono[1:]))
            self.assertAlmostEqual(crossings, carrier, delta=3)

    def test_marked_cut_is_placed_once_at_the_start_of_the_extra(self):
        rate = 8000
        config = self.settings.remix
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            bed, continued, output = directory / "bed.wav", directory / "continued.wav", directory / "out.wav"
            frames = rate * 2
            samples = array("f")
            for frame in range(frames):
                value = 0.4 if rate // 2 <= frame < rate else 0.05
                samples.extend((value, value))
            MixerService._write_float_wav(bed, samples, rate, 2)
            tail = array("f", samples)
            tail.extend([0.0] * (rate * 2 * 2))
            MixerService._write_float_wav(continued, tail, rate, 2)
            info = MixerService.finish_continuation(
                continued, bed, output, {"start": 0.5, "end": 1.0}, 2.0, 4.0, config)
            pcm = MixerService.inspect_pcm(output)
            self.assertAlmostEqual(pcm["duration_seconds"], 4.0, places=3)
            self.assertTrue(info["sample"]["placed"])
            self.assertAlmostEqual(info["sample"]["seconds"], 0.5, places=3)
            self.assertEqual(info["repetitions"], 0)
            heard = pcm["samples"]
            self.assertEqual(heard[:frames * 2], samples)
            extra = heard[frames * 2:]
            self.assertEqual(extra[:rate], array("f", [0.4] * rate))
            self.assertEqual(max(abs(value) for value in extra[rate:]), 0.0)

    def test_short_sample_is_rejected_and_an_unmarked_extension_has_no_window(self):
        with self.assertRaisesRegex(ValueError, "demasiado corto"):
            timeline_plan(self.request(bpm=120, source_bpm=120, duration_seconds=8,
                                       repeat_start=0, repeat_end=0.4), 4, self.settings)
        full = RemixProjectRequest(source_name="source.wav", prompt="A track with techno", bpm=120,
                                   duration_seconds=8)
        plan = full_variant_plan(full, 4, 4, self.settings, {"bpm_measured": 120, "bpm_confidence": 0.9})
        self.assertEqual(plan["method"], "continue_bed")
        self.assertIsNone(plan["repeat_start"])
        self.assertIsNone(plan["repeat_end"])
        self.assertIsNone(plan["mapped_repeat_start"])
        self.assertIsNone(plan["mapped_repeat_end"])

    def test_continuation_spans_follow_the_configured_chunk_and_do_not_retile_the_cut(self):
        config = self.settings.remix
        spans = continuation_spans(79.0, 240.0, config)
        self.assertEqual([item["start"] for item in spans], [79.0, 169.0])
        self.assertEqual(spans[-1]["end"], 240.0)
        for item in spans:
            width = item["end"] - item["start"]
            self.assertGreaterEqual(width, config.continuation_min_seconds)
            self.assertLessEqual(width, config.continuation_max_seconds)
        self.assertEqual(continuation_spans(10.0, 10.4, config), [{"start": 10.0, "end": 13.0}])
        with self.assertRaisesRegex(ValueError, "trozos"):
            continuation_spans(1.0, 200.0, type("Cfg", (), {
                "continuation_min_seconds": 3.0, "continuation_max_seconds": 90.0,
                "continuation_max_chunks": 1, "continuation_batch_size": 1,
            })())

    def test_continuation_payload_repaints_the_end_of_the_created_bed(self):
        request = RemixProjectRequest(source_name="source.wav", prompt="A track with techno", bpm=170)
        generation = continuation_generation(
            request, Path("bed.wav"), {"start": 79.25, "end": 169.25}, 42, self.settings)
        payload = MusicService(self.settings).build_payload(generation)
        self.assertEqual(payload["task_type"], "repaint")
        self.assertEqual(payload["src_audio_path"], "bed.wav")
        self.assertEqual(payload["repainting_start"], 79.25)
        self.assertEqual(payload["repainting_end"], 169.25)
        self.assertEqual(payload["batch_size"], 1)
        self.assertEqual(payload["audio_duration"], -1)
        self.assertFalse(payload["thinking"])
        self.assertFalse(payload["use_format"])
        self.assertFalse(payload["use_cot_caption"])
        self.assertEqual(payload["bpm"], 170)
        self.assertEqual(payload["prompt"], "A track with techno")
        self.assertNotIn("audio_cover_strength", payload)
        self.assertEqual(payload["model"], self.settings.generation.remix_model)
        with self.assertRaisesRegex(ValueError, "texto de estilo"):
            continuation_generation(
                RemixProjectRequest(source_name="source.wav", prompt="  "),
                Path("bed.wav"), {"start": 1.0, "end": 4.0}, None, self.settings)
        limits = continuation_limits(self.settings.remix)
        self.assertEqual(limits, (3.0, 90.0, 200, 1))

    def test_invalid_scope_and_nonfinite_or_short_sections_rejected(self):
        for kwargs in ({"duration_seconds": float("nan")}, {"source_bpm": float("inf"), "bpm": 150},
                       {"duration_seconds": 25, "repeat_start": 1},
                       {"duration_seconds": 25, "transition_seconds": 0},
                       {"duration_seconds": 25, "repeat_start": -1, "repeat_end": 8}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                validate_project(self.request(**kwargs), 20, self.settings)
        for kwargs in ({"duration_seconds": 10}, {"duration_seconds": 20, "repeat_start": 1, "repeat_end": 8},
                       {"duration_seconds": 25, "repeat_start": 1, "repeat_end": 1.1}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                timeline_plan(self.request(**kwargs), 20, self.settings)
        kept = timeline_plan(self.request(duration_seconds=25, repeat_start=1, repeat_end=3, transition_seconds=1),
                             20, self.settings)
        self.assertEqual(kept["method"], "continue_bed")
        self.assertEqual(kept["transition_seconds"], 0.0)
        with self.assertRaises(ValueError):
            validate_project(RemixProjectRequest(source_name="a.wav", scope="region", prompt="Cambio",
                             region_start=1, region_end=2, duration_seconds=25), 20, self.settings)

    def test_pcm_common_tempo_keeps_relative_channels_and_extends_real_samples(self):
        rate, seconds = 8000, 4
        config = self.settings.remix
        config.sample_rate = rate
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            groups, expected = {}, []
            for index, name in enumerate(self.groups):
                # Misma forma, distinta ganancia: un atempo multicanal debe
                # conservar proporcionalidad muestra a muestra, no solo BPM.
                gain = (index + 1) / 10
                samples = array("f", (gain * math.sin(2 * math.pi * 220 * frame / rate)
                                      for frame in range(rate * seconds) for _ in range(2)))
                path = directory / f"{name}.wav"
                MixerService._write_float_wav(path, samples, rate, 2)
                groups[name] = path
            changed = MixerService.tempo_groups(groups, directory, 1.25, 3.2, config)
            for path in changed.values():
                pcm = MixerService.inspect_pcm(path)
                self.assertAlmostEqual(pcm["duration_seconds"], 3.2, places=3)
                expected.append(pcm["samples"])
            for index in range(1, 4):
                error = max(abs(expected[index][frame] - expected[0][frame] * (index + 1))
                            for frame in range(len(expected[0])))
                self.assertLess(error, 1e-6)
            mixed = directory / "mix.wav"
            MixerService.mix_groups([(path, 0) for path in changed.values()], mixed, 3.2, rate)
            request = self.request(bpm=150, source_bpm=120, duration_seconds=8,
                                   repeat_start=1, repeat_end=3, transition_seconds=0.1)
            plan = timeline_plan(request, seconds, self.settings)
            self.assertEqual(plan["method"], "continue_bed")
            spans = continuation_spans(plan["natural_duration_seconds"], plan["target_duration_seconds"], config)
            self.assertEqual(spans[0]["start"], plan["natural_duration_seconds"])
            self.assertLessEqual(spans[0]["end"] - spans[0]["start"], config.continuation_max_seconds)
            mix = MixerService.inspect_pcm(mixed)
            continued = directory / "continued.wav"
            tail = array("f", mix["samples"])
            extra = round((8 - mix["duration_seconds"]) * rate)
            tail.extend([0.2] * (extra * 2))
            MixerService._write_float_wav(continued, tail, rate, 2)
            extended = directory / "extended.wav"
            result = MixerService.finish_continuation(
                continued, mixed, extended,
                {"start": plan["mapped_repeat_start"], "end": plan["mapped_repeat_end"]},
                plan["natural_duration_seconds"], 8, config)
            pcm = MixerService.inspect_pcm(extended)
            self.assertEqual(result["repetitions"], 0)
            self.assertTrue(result["sample"]["placed"])
            self.assertAlmostEqual(pcm["duration_seconds"], 8, places=3)
            prefix = round(plan["natural_duration_seconds"] * rate) * 2
            self.assertEqual(pcm["samples"][:prefix], mix["samples"][:prefix])

    def test_cache_rejects_wrong_signature_incomplete_groups_and_nonfinite_samples(self):
        config = self.settings.remix
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            entries = []
            for name in self.groups:
                path = directory / f"{name}.wav"
                MixerService._write_float_wav(path, array("f", [0.1] * 16000), 8000, 2)
                entries.append({"id": name, "file_name": path.name})
            result = {"groups": entries, "separation_signature": SeparatorService.signature(config)}
            self.assertEqual(set(SeparatorService.validate_groups(result, directory, 1, config)), set(self.groups))
            for bad in ({**result, "separation_signature": "old"}, {**result, "groups": entries[:-1]},
                        {**result, "groups": [entries[0]] * 4}):
                with self.assertRaises(ValueError):
                    SeparatorService.validate_groups(bad, directory, 1, config)
            MixerService._write_float_wav(directory / entries[0]["file_name"], array("f", [float("nan")] * 16000), 8000, 2)
            with self.assertRaisesRegex(ValueError, "no finitas"):
                SeparatorService.validate_groups(result, directory, 1, config)

    def test_keep_remove_continuation_asks_for_style_before_separating(self):
        from fastapi import HTTPException
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "source.wav"
            MixerService._write_float_wav(source, array("f", [0.1] * 64000), 8000, 2)
            runtime = RemixProjectRuntime.__new__(RemixProjectRuntime)
            runtime.settings = self.settings
            runtime.find_audio = lambda name, kind: source
            request = self.request(bpm=150, source_bpm=120, duration_seconds=8,
                                   repeat_start=1, repeat_end=3, transition_seconds=0.1)
            request.groups["vocals"] = "remove"
            with self.assertRaises(HTTPException) as caught:
                asyncio.run(runtime.preview(request))
            self.assertEqual(caught.exception.status_code, 422)
            self.assertIn("texto de estilo", caught.exception.detail)
            request.prompt = "A track with techno"
            prepared = asyncio.run(runtime.preview(request))
            self.assertTrue(prepared["operations"]["engine_required"])
            self.assertEqual(prepared["effective_parameters"], {})
            self.assertEqual(prepared["pending_material"], [])
            self.assertEqual(len(prepared["operations"]["source_digest"]), 64)
            self.assertFalse(any("determinista" in item for item in prepared["warnings"]))
            self.assertTrue(any("continúa el final" in item for item in prepared["warnings"]))
            self.assertEqual(prepared["operations"]["timeline"]["method"], "continue_bed")
            self.assertEqual(prepared["operations"]["timeline"]["natural_duration_seconds"], 3.2)
            self.assertEqual(prepared["operations"]["timeline"]["target_duration_seconds"], 8)
            plain = self.request(bpm=150, source_bpm=120)
            plain.groups["vocals"] = "remove"
            kept = asyncio.run(runtime.preview(plain))
            self.assertFalse(kept["operations"]["engine_required"])
            self.assertTrue(any("determinista" in item for item in kept["warnings"]))

    def test_one_transformed_group_keeps_the_style_filed_outside_that_stem(self):
        actions = {"vocals": "keep", "drums": "transform", "bass": "remove", "other": "keep"}
        target, peeled = stems_kept_out_of_single_transform(actions)
        self.assertEqual(target, "drums")
        self.assertEqual(peeled, ("vocals", "bass"))
        with self.assertRaisesRegex(ValueError, "única"):
            stems_kept_out_of_single_transform({"drums": "transform", "other": "transform"})
        rate = 8000
        frames = rate // 10
        config = self.settings.remix

        def tone(value):
            return array("f", [value] * (frames * 2))

        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            parts = {"drums": tone(0.10), "other": tone(0.20), "vocals": tone(0.05), "bass": tone(0.0)}
            engine = array("f", (sum(values) for values in zip(*(parts[name] for name in parts))))
            paths = {}
            for name, samples in parts.items():
                path = directory / f"{name}.wav"
                MixerService._write_float_wav(path, samples, rate, 2)
                paths[name] = path
            engine_path = directory / "engine.wav"
            MixerService._write_float_wav(engine_path, engine, rate, 2)
            replaced = directory / "old-drums.wav"
            MixerService._write_float_wav(replaced, tone(0.04), rate, 2)
            output = directory / "pista.wav"
            info = MixerService.render_single_transform(
                engine_path, paths, actions, replaced, output, config)
            self.assertFalse(info["used_full_generation"])
            self.assertEqual(info["gain"], 1.0)
            heard = MixerService.inspect_pcm(output)["samples"]
            self.assertLess(max(abs(value - 0.30) for value in heard), 1e-3)

            quiet = {name: tone(0.01 if name == "drums" else 0.0) for name in parts}
            quiet_engine = directory / "quiet.wav"
            MixerService._write_float_wav(quiet_engine, quiet["drums"], rate, 2)
            for name, samples in quiet.items():
                MixerService._write_float_wav(paths[name], samples, rate, 2)
            MixerService._write_float_wav(replaced, tone(0.20), rate, 2)
            raised = directory / "raised.wav"
            louder = MixerService.render_single_transform(
                quiet_engine, paths, actions, replaced, raised, config)
            cap = 10 ** (config.parameters["gain_db"]["max"] / 20)
            self.assertAlmostEqual(louder["gain"], cap, places=3)
            raised_pcm = MixerService.inspect_pcm(raised)["samples"]
            self.assertLess(max(abs(value - 0.01 * cap) for value in raised_pcm), 1e-3)

            voice = tone(0.20)
            voice_path = directory / "voice-engine.wav"
            MixerService._write_float_wav(voice_path, voice, rate, 2)
            for name in parts:
                MixerService._write_float_wav(paths[name], voice if name == "vocals" else tone(0.0), rate, 2)
            fallback = directory / "fallback.wav"
            whole = MixerService.render_single_transform(
                voice_path, paths, actions, replaced, fallback, config)
            self.assertTrue(whole["used_full_generation"])
            kept = MixerService.inspect_pcm(fallback)["samples"]
            self.assertLess(max(abs(value - 0.20) for value in kept), 1e-3)

    def test_several_transformed_groups_keep_the_hit_filed_outside_drums(self):
        actions = {"vocals": "keep", "drums": "transform", "bass": "transform", "other": "transform"}
        targets, peeled = stems_peeled_from_transformed_bed(actions)
        self.assertEqual(targets, ("drums", "bass", "other"))
        self.assertEqual(peeled, ("vocals",))
        rate = 8000
        frames = rate // 10
        config = self.settings.remix

        def tone(value):
            return array("f", [value] * (frames * 2))

        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            parts = {"drums": tone(0.02), "bass": tone(0.02), "other": tone(0.30), "vocals": tone(0.05)}
            engine = array("f", (sum(values) for values in zip(*(parts[name] for name in parts))))
            paths = {}
            for name, samples in parts.items():
                path = directory / f"{name}.wav"
                MixerService._write_float_wav(path, samples, rate, 2)
                paths[name] = path
            engine_path = directory / "engine.wav"
            replaced = directory / "replaced.wav"
            output = directory / "bed.wav"
            MixerService._write_float_wav(engine_path, engine, rate, 2)
            MixerService._write_float_wav(replaced, tone(0.04), rate, 2)
            info = MixerService.render_transformed_bed(
                engine_path, paths, actions, replaced, output, config)
            self.assertFalse(info["used_full_generation"])
            heard = MixerService.inspect_pcm(output)["samples"]
            self.assertLess(max(abs(value - 0.34) for value in heard), 1e-3)

    def test_groups_tempo_ratio_uses_the_measurement_and_the_configured_tolerance(self):
        config = self.settings.remix
        self.assertIsNone(groups_tempo_ratio(171.4, 170, config))
        self.assertAlmostEqual(groups_tempo_ratio(100, 170, config), 1.7)
        self.assertIsNone(groups_tempo_ratio(168, 170, config))
        with self.assertRaisesRegex(ValueError, "BPM medido"):
            groups_tempo_ratio(float("nan"), 170, config)
        with self.assertRaisesRegex(ValueError, "BPM fiable"):
            require_measured_tempo({"bpm_measured": 100, "bpm_confidence": 0.01},
                                   config, "en la mezcla de grupos")

    def test_groups_mix_tempo_keeps_the_requested_duration(self):
        config = self.settings.remix
        longer = timeline_plan(self.request(bpm=150, source_bpm=120, duration_seconds=35,
                                            repeat_start=2, repeat_end=8, transition_seconds=0.1),
                               20, self.settings)
        adjusted = apply_groups_mix_tempo(longer, 16, 1.6, 35, config)
        self.assertAlmostEqual(adjusted["natural_duration_seconds"], 10)
        self.assertEqual(adjusted["target_duration_seconds"], 35)
        self.assertEqual(adjusted["method"], "continue_bed")
        self.assertAlmostEqual(adjusted["tempo_ratio"], 1.6)
        self.assertAlmostEqual(adjusted["mapped_repeat_start"], 1.0)
        self.assertAlmostEqual(adjusted["mapped_repeat_end"], 4.0)
        self.assertEqual(adjusted["transition_seconds"], 0.0)
        self.assertEqual(longer["natural_duration_seconds"], 16)
        self.assertEqual(longer["target_duration_seconds"], 35)
        self.assertAlmostEqual(longer["tempo_ratio"], 1.25)
        plain = timeline_plan(self.request(bpm=150, source_bpm=120), 20, self.settings)
        settled = apply_groups_mix_tempo(plain, 16, 2, None, config)
        self.assertAlmostEqual(settled["natural_duration_seconds"], 8)
        self.assertAlmostEqual(settled["target_duration_seconds"], 8)
        self.assertEqual(settled["method"], "original")
        self.assertEqual(settled["transition_seconds"], 0.0)
        filled = apply_groups_mix_tempo(plain, 16, 2, 30, config)
        self.assertEqual(filled["method"], "continue_bed")
        self.assertEqual(filled["target_duration_seconds"], 30)
        self.assertEqual(filled["transition_seconds"], 0.0)
        self.assertIsNone(filled["mapped_repeat_start"])
        with self.assertRaisesRegex(ValueError, r"mínimo 32 s \(0:32\)"):
            apply_groups_mix_tempo(plain, 16, 0.5, 10, config)

    def test_full_preview_says_one_unmeasured_variant_does_not_drop_the_lot(self):
        notice = full_bpm_preview_notice()
        self.assertIn("la variante sin pulso no se publica", notice)
        self.assertIn("detiene todo el lote", notice)
        self.assertNotIn("produce un error", notice)
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "source.wav"
            MixerService._write_float_wav(source, array("f", [0.1] * 16000), 8000, 2)
            runtime = RemixProjectRuntime.__new__(RemixProjectRuntime)
            runtime.settings = self.settings
            runtime.music = MusicService(self.settings)
            runtime.find_audio = lambda _name, _kind: source
            full = RemixProjectRequest(source_name=source.name, prompt="A track with techno",
                                       bpm=170, scope="full")
            prepared = asyncio.run(runtime.preview(full))
            groups = asyncio.run(runtime.preview(self.request(
                bpm=150, source_bpm=120, prompt="A track with techno")))
        self.assertIn(notice, prepared["warnings"])
        self.assertFalse(any("produce un error" in item for item in prepared["warnings"]))
        self.assertFalse(any(item == notice for item in groups["warnings"]))

    def test_uncertain_mix_delivers_with_notice_only_for_groove_errors(self):
        groove = ValueError("El groove es incierto: el período elegido no destaca "
                            "sobre los tempos vecinos")
        notice = uncertain_mix_notice(groove, 170)
        self.assertIn("no se ajustó al BPM pedido", notice)
        self.assertIn("170", notice)
        self.assertIn("no queda garantizado", notice)
        self.assertIsNone(uncertain_mix_notice(groove, None))
        self.assertIsNone(uncertain_mix_notice(
            ValueError("El BPM final medido 99.42 no cumple el pedido 170 (tolerancia 2 BPM)"), 170))
        self.assertIsNone(uncertain_mix_notice(
            ValueError("Configuración de evidencia de pico de groove inválida"), 170))
        self.assertIsNone(uncertain_mix_notice(RuntimeError("El groove es incierto"), 170))

    def test_uncertain_mix_marks_the_plan_without_inventing_a_bpm(self):
        plan = {"natural_duration_seconds": 16, "method": "repeat_crossfade"}
        mark_uncertain_mix_tempo(plan, ValueError("El groove es incierto: meseta"))
        self.assertIsNone(plan["beat_clock_bpm"])
        self.assertEqual(plan["beat_clock_origin"], "unverified_uncertain_groove")
        self.assertEqual(plan["tempo_verification"], "uncertain_at_mix")
        self.assertIn("meseta", plan["tempo_verification_error"])
        self.assertNotIn("bpm_measured", plan)

    def test_groups_preview_announces_delivery_when_the_mix_has_no_reliable_pulse(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "source.wav"
            MixerService._write_float_wav(source, array("f", [0.1] * 16000), 8000, 2)
            runtime = RemixProjectRuntime.__new__(RemixProjectRuntime)
            runtime.settings = self.settings
            runtime.music = MusicService(self.settings)
            runtime.find_audio = lambda _name, _kind: source
            with_bpm = asyncio.run(runtime.preview(self.request(
                bpm=150, source_bpm=120, prompt="A track with techno")))
            without_bpm = asyncio.run(runtime.preview(self.request(
                prompt="A track with techno")))
        self.assertTrue(any("no queda garantizado" in item for item in with_bpm["warnings"]))
        self.assertFalse(any("no queda garantizado" in item for item in without_bpm["warnings"]))


class UnmeasuredVariantRetryTest(unittest.TestCase):
    def test_retry_count_comes_from_configuration(self):
        self.assertEqual(full_groove_retries(AppSettings().remix), 2)
        for bad in (True, -1, 1.5, None):
            with self.subTest(bad=bad):
                with self.assertRaisesRegex(ValueError, "reintentos"):
                    full_groove_retries(type("Cfg", (), {"full_groove_retries": bad})())

    def test_only_an_unmeasurable_draw_asks_for_another_sample(self):
        decay = ValueError("El groove es incierto: el período interior no destaca "
                           "sobre la caída de la autocorrelación")
        self.assertTrue(audio_has_no_usable_groove(decay))
        self.assertTrue(audio_has_no_usable_groove(
            ValueError("No hay un BPM fiable en la variante generada; no se puede verificar")))
        self.assertFalse(audio_has_no_usable_groove(
            ValueError("El BPM final medido 99.42 no cumple el pedido 199 (tolerancia 2 BPM)")))
        self.assertFalse(audio_has_no_usable_groove(ValueError("Configuración de evidencia de pico de groove inválida")))
        self.assertFalse(audio_has_no_usable_groove(RuntimeError("El groove es incierto")))

    def test_replacement_seed_skips_the_batch_already_heard(self):
        self.assertEqual(replacement_request_seed(42, 2, 1, 2147483647), 44)
        self.assertEqual(replacement_request_seed(42, 2, 2, 2147483647), 46)
        self.assertIsNone(replacement_request_seed(None, 2, 1, 2147483647))
        self.assertIsNone(replacement_request_seed(True, 2, 1, 2147483647))
        self.assertIsNone(replacement_request_seed(42, 2, 1, 43))

    def test_replacement_payload_is_one_track_and_the_batch_stays_two(self):
        settings = AppSettings()
        request = RemixProjectRequest(source_name="source.wav", prompt="A track with gabber", bpm=199, seed=42)
        music = MusicService(settings)
        batch = music.build_payload(project_generation(request, Path("source.wav"), None, settings))
        self.assertEqual(batch["batch_size"], 2)
        self.assertEqual(batch["seed"], 42)
        single = project_generation(request, Path("source.wav"), None, settings)
        single.batch_size = 1
        single.seed = replacement_request_seed(42, settings.generation.batch_size, 1, settings.remix.parameters["seed"]["max"])
        single.use_random_seed = False
        payload = music.build_payload(single)
        self.assertEqual(payload["batch_size"], 1)
        self.assertEqual(payload["seed"], 44)
        self.assertFalse(payload["use_random_seed"])
        self.assertEqual(payload["bpm"], 199)
        self.assertEqual(batch["batch_size"], 2)

    def test_a_pulseless_draw_is_replaced_and_the_new_measurement_is_kept(self):
        calls = {"measure": 0}

        async def measure():
            calls["measure"] += 1
            if calls["measure"] == 1:
                raise ValueError("El groove es incierto: el período interior no destaca "
                                 "sobre la caída de la autocorrelación")
            return {"bpm_measured": 99.79, "bpm_confidence": 0.642}

        replaced = []

        async def replace(draw):
            replaced.append(draw)

        measured, draws = asyncio.run(accept_measured_draw(measure, replace, 2))
        self.assertEqual(measured["bpm_measured"], 99.79)
        self.assertEqual(draws, 1)
        self.assertEqual(replaced, [1])

    def test_exhausted_draws_keep_the_detector_error(self):
        replaced = []

        async def measure():
            raise ValueError("El groove es incierto: el período interior no destaca "
                             "sobre la caída de la autocorrelación")

        async def replace(draw):
            replaced.append(draw)

        with self.assertRaisesRegex(ValueError, "caída de la autocorrelación"):
            asyncio.run(accept_measured_draw(measure, replace, 1))
        self.assertEqual(replaced, [1])

    def test_a_tempo_change_too_short_to_measure_asks_for_another_sample(self):
        calls = {"adjust": 0}

        async def measure():
            return {"bpm_measured": 50.0, "bpm_confidence": 0.868}

        async def adjust(_measured):
            calls["adjust"] += 1
            if calls["adjust"] == 1:
                raise ValueError("Audio demasiado corto para detectar el groove")
            return {"bpm_measured": 199.17, "bpm_confidence": 0.656}

        replaced = []

        async def replace(draw, exc):
            replaced.append((draw, str(exc)))

        before, after, draws = asyncio.run(accept_verified_draw(measure, adjust, replace, 2))
        self.assertEqual(before["bpm_measured"], 50.0)
        self.assertEqual(after["bpm_measured"], 199.17)
        self.assertEqual(draws, 1)
        self.assertEqual(replaced, [(1, "Audio demasiado corto para detectar el groove")])

    def test_a_missed_target_bpm_does_not_generate_again(self):
        async def measure():
            raise ValueError("El BPM final medido 99.42 no cumple el pedido 199 (tolerancia 2 BPM)")

        async def replace(_draw):
            raise AssertionError("un BPM fuera de tolerancia no pide otra muestra")

        with self.assertRaisesRegex(ValueError, "no cumple el pedido"):
            asyncio.run(accept_measured_draw(measure, replace, 2))

        async def measured():
            return {"bpm_measured": 99.42, "bpm_confidence": 0.8}

        async def adjust(_measured):
            raise ValueError("El BPM final medido 99.42 no cumple el pedido 199 (tolerancia 2 BPM)")

        async def replace_verified(_draw, _exc):
            raise AssertionError("un BPM fuera de tolerancia no pide otra muestra")

        with self.assertRaisesRegex(ValueError, "no cumple el pedido"):
            asyncio.run(accept_verified_draw(measured, adjust, replace_verified, 2))

    def test_an_unmeasurable_full_variant_stays_out_and_names_itself(self):
        for text in (
            "El groove es incierto: el período elegido no destaca sobre los tempos vecinos",
            "Audio demasiado corto para detectar el groove",
            "No se ha detectado un tempo",
            "No hay un BPM fiable en la variante generada",
        ):
            self.assertEqual(full_variant_failure(ValueError(text)), "withhold")
        self.assertEqual(
            unmeasured_variant_notice(0),
            "La variante 1 no tenía un pulso medible; no se publicó.")
        second = unmeasured_variant_notice(1)
        self.assertIn("no se publicó", second)
        self.assertIn("2", second)
        groove = ValueError("El groove es incierto: meseta")
        self.assertIs(unpublished_batch_error(0, [groove]), groove)
        self.assertIsNone(unpublished_batch_error(1, [groove]))
        self.assertIsNone(unpublished_batch_error(0, []))

    def test_a_measured_bpm_outside_tolerance_is_not_left_out(self):
        missed = ValueError("El BPM final medido 104.7 no cumple el pedido 199 (tolerancia 2 BPM)")
        self.assertEqual(full_variant_failure(missed), "raise")
        self.assertEqual(full_variant_failure(ValueError("Configuración de groove inválida")), "raise")
        self.assertEqual(full_variant_failure(RuntimeError("El groove es incierto")), "raise")


class UncertainExtensionTest(unittest.TestCase):
    """[R17] Una ampliación incierta en Por pistas conserva el tempo de la base verificada."""

    def setUp(self):
        self.config = AppSettings().remix
        self.bed = {"bpm_measured": 169.85, "bpm_confidence": 0.417}
        self.plan = {"method": "continue_bed"}
        self.uncertain = ValueError(
            "El groove es incierto: el período elegido no destaca sobre los tempos vecinos")

    def test_uncertain_groupsextension_keeps_the_verified_bed_measurement(self):
        fallback = uncertain_extension_fallback(
            self.uncertain, "groups", self.plan, self.bed, self.config)
        self.assertEqual(fallback, self.bed)
        verify_requested_tempo(fallback, 170, self.config, "después del arreglo y exportación")

    def test_a_conclusive_final_tempo_still_stops_the_job(self):
        conclusive = ValueError(
            "El BPM final medido 136.36 no cumple el pedido 170 (tolerancia 2 BPM)")
        self.assertIsNone(uncertain_extension_fallback(
            conclusive, "groups", self.plan, self.bed, self.config))

    def test_only_por_pistas_continuing_the_bed_qualifies(self):
        self.assertIsNone(uncertain_extension_fallback(
            self.uncertain, "full", self.plan, self.bed, self.config))
        self.assertIsNone(uncertain_extension_fallback(
            self.uncertain, "groups", {"method": "original"}, self.bed, self.config))
        self.assertIsNone(uncertain_extension_fallback(
            self.uncertain, "groups", None, self.bed, self.config))
        self.assertIsNone(uncertain_extension_fallback(
            ValueError("Configuración de hombro de groove inválida"), "groups",
            self.plan, self.bed, self.config))
        self.assertIsNone(uncertain_extension_fallback(
            RuntimeError("El motor falló"), "groups", self.plan, self.bed, self.config))

    def test_without_a_fiable_bed_measurement_there_is_nothing_to_credit(self):
        for bed in (None, {}, {"bpm_measured": 169.85, "bpm_confidence": 0.05},
                    {"bpm_measured": float("nan"), "bpm_confidence": 0.4}):
            with self.subTest(bed=bed):
                self.assertIsNone(uncertain_extension_fallback(
                    self.uncertain, "groups", self.plan, bed, self.config))


if __name__ == "__main__":
    unittest.main()
