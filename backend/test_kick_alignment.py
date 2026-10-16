"""Cuadre de la base nueva con el bombo original.

El corte de hombro sigue en la configuración. Una lectura que no se puede
medir no se convierte en el BPM pedido.
"""
import array
import json
import tempfile
import unittest
import wave
from pathlib import Path

from config import AppSettings
from mixer_service import MixerService
from remix_project import (
    groups_tempo_ratio,
    require_measured_tempo,
    required_measured_tempo,
    square_mix_on_original_kick,
    verify_requested_tempo,
    whole_song_repeat_plan,
)


def _write_clicks(path: Path, bpm: float, seconds: float, offset_s: float = 0.0, rate: int = 8000) -> None:
    count = int(rate * seconds)
    samples = array.array("h", bytes(count * 2))
    step = rate * 60.0 / bpm
    position = offset_s * rate
    while position < count - 8:
        start = int(position)
        for offset in range(6):
            samples[start + offset] = int(8000 * (1 - offset / 6))
        position += step
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes(samples.tobytes())


class KickAlignmentTest(unittest.TestCase):
    def setUp(self):
        self.config = AppSettings().remix
        self.assertEqual(self.config.groove_shoulder_ratio, 1.25)
        self.assertEqual(self.config.groove_peak_evidence_ratio, 0.5)
        self.assertEqual(self.config.groove_hit_preference_ratio, 2.0)
        self.assertEqual(self.config.tempo_verify_tolerance_bpm, 2.0)

    def test_a_short_loop_opens_to_the_whole_song_and_a_full_one_stays(self):
        plan = {"natural_duration_seconds": 79.25, "mapped_repeat_start": 23.59,
                "mapped_repeat_end": 27.40, "source_duration_seconds": 81.4,
                "target_duration_seconds": 240.0, "target_bpm": 170}
        widened = whole_song_repeat_plan(plan, self.config)
        self.assertEqual(widened["mapped_repeat_start"], 0.0)
        self.assertEqual(widened["mapped_repeat_end"], 79.25)
        self.assertEqual(widened["repeat_start"], 0.0)
        self.assertEqual(widened["repeat_end"], 81.4)
        self.assertEqual(widened["target_duration_seconds"], 240.0)
        self.assertEqual(plan["mapped_repeat_start"], 23.59)
        already = dict(plan, mapped_repeat_start=0.0, mapped_repeat_end=79.25)
        self.assertIsNone(whole_song_repeat_plan(already, self.config))
        self.assertIsNone(whole_song_repeat_plan({"mapped_repeat_start": 0, "mapped_repeat_end": 4}, self.config))

    def test_offset_kicks_are_squared_onto_the_reference_and_remeasured(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            reference = root / "reference.wav"
            fresh = root / "fresh.wav"
            _write_clicks(reference, 170, 12)
            _write_clicks(fresh, 176, 12, offset_s=0.14)
            output = root / "mezcla-cuadrada.wav"
            result = square_mix_on_original_kick(
                [(reference, 0.0), (fresh, 0.0)], [fresh], reference, fresh,
                output, root / "work", 1, 12, self.config)
            self.assertIsNotNone(result)
            self.assertTrue(output.is_file())
            self.assertGreater(output.stat().st_size, 0)
            self.assertIsNotNone(result["tempo_ratio"])
            self.assertLess(result["tempo_ratio"], 1)
            measured = required_measured_tempo(output)
            bpm = require_measured_tempo(measured, self.config, "en la mezcla cuadrada")
            self.assertLessEqual(abs(bpm - 170), self.config.tempo_verify_tolerance_bpm)
            self.assertGreaterEqual(measured["bpm_confidence"], self.config.timeline_min_groove_confidence)
            self.assertIsNone(groups_tempo_ratio(bpm, 170, self.config))

    def test_unmeasurable_kick_returns_nothing_and_writes_no_mix(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            reference = root / "reference.wav"
            fresh = root / "fresh.wav"
            _write_clicks(reference, 170, 12)
            _write_clicks(fresh, 170, 0.4)
            output = root / "mezcla-cuadrada.wav"
            result = square_mix_on_original_kick(
                [(reference, 0.0), (fresh, 0.0)], [fresh], reference, fresh,
                output, root / "work", 1, 12, self.config)
            self.assertIsNone(result)
            self.assertFalse(output.exists())

    def test_saved_group_remix_squares_without_touching_its_files(self):
        """Lee los WAV del trabajo que falló y comprueba solo la mezcla cuadrada.

        No publica. No cubre la ampliación: repetir el tramo corto hasta 240 s
        vuelve a dejar el pulso por debajo del corte.
        """
        source = (Path(__file__).resolve().parents[1] / "backend" / "outputs" / "_remix"
                  / "3f662ec43e4b4beeae3c93b279b3dcd8")
        vocals = source / "tempo-vocals.wav"
        bed = source / "base-transformada-1.wav"
        reference = source / "tempo-drums.wav"
        fresh = source / "transformada-1-drums.wav"
        if not all(path.is_file() for path in (vocals, bed, reference, fresh)):
            self.skipTest("los WAV de ese trabajo no están en este equipo")
        before = {path: path.stat().st_mtime_ns for path in (vocals, bed, reference, fresh)}
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            duration = MixerService.inspect_pcm(vocals)["duration_seconds"]
            output = root / "mezcla-cuadrada.wav"
            result = square_mix_on_original_kick(
                [(vocals, 0.0), (bed, 0.0)], [bed], reference, fresh,
                output, root / "work", 1, duration, self.config)
            self.assertIsNotNone(result)
            measured = required_measured_tempo(output)
            bpm = require_measured_tempo(measured, self.config, "en la mezcla cuadrada")
            verify_requested_tempo(measured, 170, self.config, "después del cuadre")
            self.assertGreater(output.stat().st_size, 0)
            self.assertGreater(MixerService.inspect_pcm(output)["duration_seconds"], 0)
            exported = root / "exportada.mp3"
            mastering = MixerService.export_remix(output, exported, self.config)
            self.assertGreater(exported.stat().st_size, 0)
            exported_measured = required_measured_tempo(exported)
            verify_requested_tempo(exported_measured, 170, self.config, "después de exportar")
            self.assertGreater(mastering["loudness"]["input_i"], -70)
        for path, stamp in before.items():
            self.assertEqual(path.stat().st_mtime_ns, stamp)

    def test_short_loop_of_the_saved_remix_fails_and_the_whole_song_reaches_240(self):
        """El tramo de 4 s no pasa; la canción entera, repetida, sí llega a 240 s."""
        source = (Path(__file__).resolve().parents[1] / "backend" / "outputs" / "_remix"
                  / "3f662ec43e4b4beeae3c93b279b3dcd8")
        vocals = source / "tempo-vocals.wav"
        bed = source / "base-transformada-1.wav"
        reference = source / "tempo-drums.wav"
        fresh = source / "transformada-1-drums.wav"
        history_path = Path(__file__).resolve().parents[1] / "backend" / "job_history.json"
        if not all(path.is_file() for path in (vocals, bed, reference, fresh, history_path)):
            self.skipTest("los WAV de ese trabajo no están en este equipo")
        before = {path: path.stat().st_mtime_ns for path in (vocals, bed, reference, fresh)}
        history = json.loads(history_path.read_text(encoding="utf-8"))
        plan = dict(next(job["operations"]["timeline"] for job in history["remix"]
                         if job.get("job_id") == "3f662ec43e4b4beeae3c93b279b3dcd8"))
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            mixed = root / "mezcla.wav"
            result = square_mix_on_original_kick(
                [(vocals, 0.0), (bed, 0.0)], [bed], reference, fresh,
                mixed, root / "work", 1, plan["natural_duration_seconds"], self.config)
            self.assertIsNotNone(result)
            mix = required_measured_tempo(mixed)
            plan["beat_clock_bpm"] = mix["bpm_measured"]
            plan["beat_clock_origin"] = "generated_measurement"
            short = root / "arreglo-corto.wav"
            short_arrangement = MixerService.extend_timeline(mixed, short, plan, self.config)
            with self.assertRaisesRegex(ValueError, "tempos vecinos"):
                required_measured_tempo(short, short_arrangement, self.config)
            widened = whole_song_repeat_plan(plan, self.config)
            self.assertIsNotNone(widened)
            extended = root / "arreglo.wav"
            arrangement = MixerService.extend_timeline(mixed, extended, widened, self.config)
            self.assertAlmostEqual(arrangement["duration_seconds"], 240.0, delta=self.config.duration_tolerance_seconds)
            self.assertLess(arrangement["repetitions"], 10)
            exported = root / "exportada.mp3"
            MixerService.export_remix(extended, exported, self.config)
            self.assertGreater(exported.stat().st_size, 0)
            self.assertAlmostEqual(MixerService.inspect_pcm(exported)["duration_seconds"], 240.0,
                                   delta=self.config.duration_tolerance_seconds)
            measured = required_measured_tempo(exported, arrangement, self.config)
            verify_requested_tempo(measured, 170, self.config, "después de repetir la canción entera")
        for path, stamp in before.items():
            self.assertEqual(path.stat().st_mtime_ns, stamp)
