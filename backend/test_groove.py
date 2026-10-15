"""Regresión B6: picos armónicos y detección sobre WAV reales."""
import math
import random
import struct
import tempfile
import unittest
import wave
from pathlib import Path

from audio_analysis import (
    _autocorr_scores, _fold_groove, _multi_period_evidence, _prefer_supported_octave,
    _refine_groove_detail, _refine_groove_period, _reject_flat_shoulder,
    _reject_unprominent_period,
    _score_supported_grooves, _select_groove_peak, detect_groove,
)
from remix_project import required_measured_tempo
from config import AppSettings


class GrooveTest(unittest.TestCase):
    def setUp(self):
        self.settings = AppSettings().remix

    def scores(self, peaks):
        return [(lag, peaks.get(lag, 0.0)) for lag in range(10, 121)]

    def test_short_nonharmonic_peak_cannot_win(self):
        # Reproducción mínima de Arroja: 353 BPM vs máximo 120 BPM.
        chosen = _select_groove_peak(self.scores({17: 0.3964, 50: 0.4122}), self.settings)
        self.assertEqual(chosen[0], 50)

    def test_octave_requires_local_peak_and_score_from_original_anchor(self):
        scores = self.scores({25: 0.83, 50: 0.91, 100: 1.0})
        self.assertEqual(_select_groove_peak(scores, self.settings)[0], 50)
        # No se exige que el medio compás sea fuerte si el pulso /4 lo es.
        self.assertEqual(_select_groove_peak(self.scores({25: 0.95, 50: 0.5, 100: 1.0}),
                                           self.settings)[0], 25)
        # El punto previo al máximo local no debe elegirse aunque alcance 90%.
        scores = self.scores({24: 0.91, 25: 0.96, 100: 1.0})
        self.assertEqual(_select_groove_peak(scores, self.settings)[0], 25)

    def test_insufficient_double_tempo_evidence_remains_half_tempo(self):
        self.assertEqual(_select_groove_peak(self.scores({30: 0.4872, 60: 0.6908}),
                                           self.settings)[0], 60)

    def test_search_window_endpoint_cannot_hide_an_interior_peak(self):
        rows = []
        for lag in range(11, 86):
            score = 0.30
            if lag == 11:
                score = 0.50
            elif lag == 27:
                score = 0.40
            elif lag in (26, 28):
                score = 0.35
            rows.append((lag, score))
        self.assertEqual(_select_groove_peak(rows, self.settings)[0], 27)
        edge = [(lag, 0.5 - lag * 0.001) for lag in range(11, 40)]
        with self.assertRaisesRegex(ValueError, "pico de período interior"):
            _select_groove_peak(edge, self.settings)

    def test_supported_octave_uses_refined_evidence(self):
        # 199 tiene más evidencia sostenida que su mitad; no manda el diente suelto.
        chosen = _prefer_supported_octave([(60.35, 0.68), (30.125, 0.91), (34.275, 0.71)], self.settings)
        self.assertAlmostEqual(chosen, 30.125)
        # La octava rápida no llega al 90 % del pulso lento: se queda el lento.
        chosen = _prefer_supported_octave([(60.0, 1.01), (30.0, 0.41)], self.settings)
        self.assertAlmostEqual(chosen, 60.0)
        # Un /2 débil no tapa el /4 del ancla original, ni se recentra la búsqueda.
        chosen = _prefer_supported_octave([(100.0, 1.0), (50.0, 0.5), (25.0, 0.95)], self.settings)
        self.assertAlmostEqual(chosen, 25.0)
        chosen = _prefer_supported_octave([(100.0, 1.0), (51.0, 0.95), (24.0, 0.95)], self.settings)
        self.assertAlmostEqual(chosen, 24.0)
        invalid = AppSettings().remix
        invalid.groove_octave_score_ratio = 0
        with self.assertRaisesRegex(ValueError, "Configuración de octava"):
            _prefer_supported_octave([(60.0, 1.0)], invalid)

    def test_invalid_refinement_configuration_and_excessive_cost_are_rejected(self):
        rms = [1 + math.cos(2 * math.pi * index / 60) for index in range(1200)]
        for key, value in (("groove_smooth_frames", 0), ("groove_smooth_frames", 2),
                           ("groove_refine_periods", 1), ("groove_refine_periods", 1000),
                           ("groove_refine_radius_frames", float("nan")),
                           ("groove_refine_step_frames", 0),
                           ("groove_refine_step_frames", float("inf")),
                           ("groove_refine_max_candidates", 1)):
            settings = AppSettings().remix
            setattr(settings, key, value)
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                _refine_groove_period(rms, 60, settings)

    def test_multi_period_refinement_preserves_anchor_octave_and_known_period(self):
        rms = [1 + math.cos(2 * math.pi * index / 60) for index in range(1200)]
        self.assertAlmostEqual(_refine_groove_period(rms, 59, self.settings), 60, places=2)
        period = _refine_groove_period(rms, 120, self.settings)
        self.assertAlmostEqual(period, 120, places=2)
        with self.assertRaisesRegex(ValueError, "Audio insuficiente"):
            _refine_groove_period(rms[:100], 60, self.settings)

    def test_refinement_boundary_is_not_accepted_as_a_supported_period_peak(self):
        rms = [1 + math.cos(2 * math.pi * index / 60) for index in range(1200)]
        # El período real queda fuera de esta vecindad. Una pendiente hacia
        # él no acredita el extremo de la búsqueda como otro BPM.
        with self.assertRaisesRegex(ValueError, "máximo.*borde"):
            _refine_groove_period(rms, 56, self.settings)

    def test_fractional_phase_fold_does_not_accumulate_rounding_drift(self):
        period, phase = 6000 / 166.25, 4.5
        onset = []
        for index in range(6000):
            delta = (index - phase + period / 2) % period - period / 2
            onset.append(math.exp(-delta * delta))
        phase_ms, confidence = _fold_groove(onset, period, 100)
        self.assertAlmostEqual(phase_ms, phase * 10, delta=6)
        self.assertGreater(confidence, 0.9)
        _, rounded_confidence = _fold_groove(onset, round(period), 100)
        self.assertGreater(confidence, rounded_confidence)

    def test_blurred_fast_period_does_not_replace_a_clear_pulse(self):
        # Textura a 268 con evidencia algo mayor y golpe flojo, frente al
        # pulso a 197. La mitad lejana no gana aunque su pliegue sea mayor.
        chosen = _score_supported_grooves(
            [(22.40, 0.4098, 0.205), (30.50, 0.3926, 0.510)], self.settings)
        self.assertAlmostEqual(6000 / chosen, 196.72, delta=0.1)
        chosen = _score_supported_grooves(
            [(30.0, 0.70, 0.45), (60.0, 0.43, 0.58)], self.settings)
        self.assertAlmostEqual(chosen, 30.0, delta=0.01)
        # El pliegue apenas mayor de un período lento no desbanca al pulso.
        chosen = _score_supported_grooves(
            [(30.17, 1.994, 0.817), (150.9, 1.85, 0.833)], self.settings)
        self.assertAlmostEqual(chosen, 30.17, delta=0.01)
        invalid = AppSettings().remix
        invalid.groove_hit_preference_ratio = 1
        with self.assertRaisesRegex(ValueError, "preferencia de golpe"):
            _score_supported_grooves([(30.0, 1.0, 0.5)], invalid)
        # Octava rápida por debajo de la confianza mínima: se queda el pulso usable.
        chosen = _score_supported_grooves(
            [(24.7, 0.440, 0.099), (49.5, 0.456, 0.143)], self.settings)
        self.assertAlmostEqual(6000 / chosen, 121.21, delta=0.1)

    def test_single_lag_evidence_matches_the_refiner(self):
        rms = [1 + math.cos(2 * math.pi * index / 60) for index in range(1200)]
        period, evidence = _refine_groove_detail(rms, 60, self.settings)
        self.assertAlmostEqual(
            _multi_period_evidence(rms, period, self.settings.groove_refine_periods,
                                   self.settings.groove_smooth_frames),
            evidence, places=6)

    def test_decay_ripple_is_not_a_measurable_tempo(self):
        # 0,20 frente a 1,65 es el pliegue lento de una envolvente sin golpe.
        # 0,44 frente a 0,58 es el pulso real de una canción suave: se queda.
        with self.assertRaisesRegex(ValueError, "caída de la autocorrelación"):
            _reject_unprominent_period(0.204, 1.651, self.settings)
        _reject_unprominent_period(0.443, 0.582, self.settings)
        _reject_unprominent_period(0.35, -0.09, self.settings)
        for bad in (0, 1.5, float("nan"), float("inf"), True):
            invalid = AppSettings().remix
            invalid.groove_peak_evidence_ratio = bad
            with self.subTest(bad=bad):
                with self.assertRaisesRegex(ValueError, "evidencia de pico"):
                    _reject_unprominent_period(1.0, 1.0, invalid)

    def test_flat_shoulder_is_not_a_measurable_tempo(self):
        # 0,286 frente a 0,248 es la meseta que el ajuste llevó a 226.
        # 0,393 frente a 0,282 es el pulso de 196,72 que ya se aceptaba.
        # Un hombro negativo es un pico por encima de esa zona.
        with self.assertRaisesRegex(ValueError, "tempos vecinos"):
            _reject_flat_shoulder(0.286, 0.248, self.settings)
        _reject_flat_shoulder(0.393, 0.282, self.settings)
        _reject_flat_shoulder(1.167, 0.094, self.settings)
        _reject_flat_shoulder(0.824, -0.071, self.settings)
        for bad in (1, 0.5, float("nan"), True):
            invalid = AppSettings().remix
            invalid.groove_shoulder_ratio = bad
            with self.subTest(bad=bad):
                with self.assertRaisesRegex(ValueError, "hombro de groove"):
                    _reject_flat_shoulder(1.0, 0.5, invalid)

    def test_smooth_envelope_without_a_hit_is_uncertain(self):
        rng = random.Random(1)
        rate = 8000
        env = 0.4
        values = []
        for index in range(rate * 12):
            if index % 80 == 0:
                env = 0.97 * env + 0.03 * rng.random()
            sample = 28000 * env * rng.uniform(-1, 1)
            values.append(int(max(-32767, min(32767, sample))))
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "smooth.wav"
            with wave.open(str(path), "wb") as stream:
                stream.setnchannels(1)
                stream.setsampwidth(2)
                stream.setframerate(rate)
                stream.writeframes(struct.pack(f"<{len(values)}h", *values))
            with self.assertRaisesRegex(ValueError, "caída de la autocorrelación"):
                detect_groove(path)

    def test_slow_tremolo_remains_a_tempo(self):
        rate, period = 8000, 1.4
        env = 0.2
        values = []
        for index in range(rate * 12):
            env = 0.9995 * env + 0.0005 * (0.3 + 0.7 * (0.5 + 0.5 * math.sin(2 * math.pi * index / rate / period)))
            sample = env * math.sin(2 * math.pi * 110 * index / rate)
            values.append(int(max(-32767, min(32767, 28000 * sample))))
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "tremolo.wav"
            with wave.open(str(path), "wb") as stream:
                stream.setnchannels(1)
                stream.setsampwidth(2)
                stream.setframerate(rate)
                stream.writeframes(struct.pack(f"<{len(values)}h", *values))
            groove = detect_groove(path)
            self.assertAlmostEqual(groove["bpm"], 60 / period, delta=2)

    def test_required_measured_tempo_reports_the_detector_reason(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "short.wav"
            with wave.open(str(path), "wb") as stream:
                stream.setnchannels(1)
                stream.setsampwidth(2)
                stream.setframerate(8000)
                stream.writeframes(b"\x00\x00" * 8000)
            with self.assertRaisesRegex(ValueError, "demasiado corto"):
                required_measured_tempo(path)

    def test_autocorr_window_keeps_configured_bpm_limits_inside(self):
        lags = [lag for lag, _score in _autocorr_scores([0.0] * 400, 100, 30, 300)]
        self.assertEqual(lags[0], 19)
        self.assertEqual(lags[-1], 201)
        self.assertIn(20, lags)
        self.assertIn(200, lags)

    def test_coarse_subharmonic_cannot_hide_a_legal_fast_pulse(self):
        # Acento cada tres golpes: el estimado de 60-180 cae en el tercio
        # (~66) y la ventana antigua, 0,35 veces ese período, empezaba
        # después del pulso de 199. El rango configurado sí lo incluye.
        rate, bpm = 8000, 199
        period = 60 / bpm
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "triple.wav"
            values = []
            for index in range(rate * 12):
                beat_time = (index / rate) % period
                beat_index = int((index / rate) / period)
                accent = 0.95 if beat_index % 3 == 0 else 0.65
                amplitude = accent if beat_time < 0.035 else 0.02
                values.append(int(28000 * amplitude * math.sin(2 * math.pi * 180 * index / rate)))
            with wave.open(str(path), "wb") as stream:
                stream.setnchannels(1)
                stream.setsampwidth(2)
                stream.setframerate(rate)
                stream.writeframes(struct.pack(f"<{len(values)}h", *values))
            groove = detect_groove(path)
            self.assertAlmostEqual(groove["bpm"], bpm, delta=2)
            self.assertGreaterEqual(groove["confidence"], self.settings.timeline_min_groove_confidence)

    def test_real_pulsed_wav_preserves_tempo_and_phase(self):
        rate, bpm, phase = 8000, 150, 0.04
        period = 60 / bpm
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "pulse.wav"
            values = []
            for index in range(rate * 12):
                beat_time = (index / rate - phase) % period
                amplitude = 0.8 if beat_time < 0.03 else 0.02
                values.append(int(30000 * amplitude * math.sin(2 * math.pi * 220 * index / rate)))
            with wave.open(str(path), "wb") as stream:
                stream.setnchannels(1)
                stream.setsampwidth(2)
                stream.setframerate(rate)
                stream.writeframes(struct.pack(f"<{len(values)}h", *values))
            groove = detect_groove(path)
            self.assertAlmostEqual(groove["bpm"], bpm, delta=1)
            self.assertAlmostEqual(groove["phase_ms"], phase * 1000, delta=20)
            self.assertGreater(groove["confidence"], 0.5)
