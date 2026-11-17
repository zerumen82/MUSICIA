"""Classification is advisory and grounded in audio-derived genre metadata."""
import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import httpx

from music_service import MusicEngineError, MusicService
from source_understanding import (
    SourceAnalysisSettings,
    _make_clip,
    analyze_source,
    classify_metadata,
    visible_analysis_phase,
)


class _FakeMusic:
    """Cliente mínimo del motor: registra cada sondeo y devuelve lo guionizado."""

    def __init__(self, polls):
        self.engine = SimpleNamespace(submit_path="/release_task", result_path="/query_result")
        self.calls = []
        self._polls = list(polls)

    def build_payload(self, _request):
        return {}

    async def _request(self, _method, path, *, check_alive=True, **_kwargs):
        self.calls.append((path, check_alive))
        if path == self.engine.submit_path:
            return {"task_id": "task-1"}
        item = self._polls.pop(0)
        if isinstance(item, BaseException):
            raise item
        return [item]

    @staticmethod
    def poll_interrupted(error):
        return MusicService.poll_interrupted(error)


def _engine_error(cause):
    error = MusicEngineError("El motor ACE-Step no responde (/query_result)")
    error.__cause__ = cause
    return error


class SourceUnderstandingTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = json.loads(Path(__file__).with_name("source_categories.json").read_text(encoding="utf-8"))

    def test_audio_genre_electronic(self):
        result = classify_metadata({"genre": "Hardstyle hardcore techno"}, self.catalog)
        self.assertEqual(result["classification"], "electronic")
        self.assertIsNone(result["confidence"])
        self.assertTrue(result["evidence"]["electronic"])

    def test_audio_genre_non_electronic(self):
        result = classify_metadata({"metas": {"genres": "Acoustic jazz"}}, self.catalog)
        self.assertEqual(result["classification"], "non_electronic")

    def test_hybrid_does_not_force_binary_result(self):
        result = classify_metadata({"genre": "Electronic jazz fusion"}, self.catalog)
        self.assertEqual(result["classification"], "mixed")

    def test_unavailable_genre_does_not_guess_from_description(self):
        result = classify_metadata({"prompt": "no electronic instruments", "metas": None}, self.catalog)
        self.assertEqual(result["classification"], "unknown")
        self.assertEqual(result["description"], "no electronic instruments")

    def test_unmapped_ambiguous_genre_is_unknown(self):
        self.assertEqual(classify_metadata({"genre": "pop"}, self.catalog)["classification"], "unknown")

    def test_glossary_genre_is_only_a_whole_vocab_line(self):
        known = classify_metadata({"genre": "gabber, hardstyle, hardcore"}, self.catalog)
        self.assertEqual(known["glossary_genre"], "gabber, hardstyle, hardcore")
        unknown = classify_metadata({"genre": "esto no es una linea del glosario"}, self.catalog)
        self.assertIsNone(unknown["glossary_genre"])
        self.assertEqual(unknown["genres"], "esto no es una linea del glosario")

    def test_analysis_phase_hides_engine_log(self):
        raw = "12:04:01 | INFO | Extracting Audio Codes...\nStarting Deep Analysis..."
        shown = visible_analysis_phase(raw)
        self.assertEqual(shown, "El modelo local analiza el audio")
        self.assertNotIn("INFO", shown)
        self.assertNotIn("|", shown)
        self.assertEqual(visible_analysis_phase("Extracting Audio Codes..."), shown)

    def _analyze(self, music):
        settings = SourceAnalysisSettings(poll_interval=0.0, timeout_seconds=5.0)
        clip = {"start": 0.0, "end": 30.0, "source_duration": 30.0}
        with patch("source_understanding._make_clip", return_value=clip), \
                patch("source_understanding.category_catalog", return_value=self.catalog):
            return asyncio.run(analyze_source(
                music, Path("fuente.mp3"), settings, lambda _phase: None,
            ))

    def test_analysis_poll_skips_health_and_survives_a_broken_connection(self):
        """Regresión 2026-11-13: ReadError('') mató un análisis en curso."""
        music = _FakeMusic([
            _engine_error(httpx.ReadError("")),
            {"status": 1, "result": json.dumps([{"genre": "techno"}])},
        ])
        result = self._analyze(music)
        self.assertEqual(result["classification"], "electronic")
        self.assertEqual(music.calls[0], ("/release_task", True))
        polls = [call for call in music.calls if call[0] == "/query_result"]
        self.assertEqual(len(polls), 2)
        self.assertTrue(all(check_alive is False for _path, check_alive in polls))

    def test_analysis_still_fails_on_a_real_engine_error(self):
        failure = MusicEngineError("El análisis del motor falló: error real")
        failure.__cause__ = RuntimeError("fallo del motor")
        music = _FakeMusic([failure])
        with self.assertRaises(MusicEngineError):
            self._analyze(music)
        self.assertEqual([call for call in music.calls if call[0] == "/query_result"],
                         [("/query_result", False)])

    def test_analysis_listens_the_whole_track_up_to_the_configured_limit(self):
        """Ya no se analiza solo un fragmento central de 30 s."""
        import tempfile
        from pydub import AudioSegment

        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "fuente.wav"
            clip = Path(folder) / "clip.wav"
            AudioSegment.silent(duration=3000).export(source, format="wav")
            whole = _make_clip(source, clip, 240.0)
            self.assertEqual(whole["source_duration"], 3.0)
            self.assertEqual(whole["start"], 0.0)
            self.assertEqual(whole["end"], 3.0)
            centered = _make_clip(source, clip, 1.0)
            self.assertEqual(centered["start"], 1.0)
            self.assertEqual(centered["end"], 2.0)

    def test_analysis_limit_must_be_positive(self):
        with self.assertRaisesRegex(ValueError, "max_seconds"):
            _make_clip(Path("fuente.mp3"), Path("clip.wav"), 0)

    def _three_seconds(self, folder):
        from pydub import AudioSegment

        source = Path(folder) / "fuente.wav"
        AudioSegment.silent(duration=3000).export(source, format="wav")
        return source

    def test_analysis_uses_the_region_chosen_on_the_waveform(self):
        import tempfile
        from pydub import AudioSegment

        with tempfile.TemporaryDirectory() as folder:
            source = self._three_seconds(folder)
            clip = Path(folder) / "clip.wav"
            chosen = _make_clip(source, clip, 240.0, 1.0, 2.0)
            self.assertEqual(chosen["start"], 1.0)
            self.assertEqual(chosen["end"], 2.0)
            self.assertFalse(chosen["truncated"])
            self.assertAlmostEqual(len(AudioSegment.from_file(clip)) / 1000, 1.0, places=2)
            from_start = _make_clip(source, clip, 240.0, 2.0, None)
            self.assertEqual((from_start["start"], from_start["end"]), (2.0, 3.0))

    def test_a_region_longer_than_the_limit_is_cut_and_declared(self):
        import tempfile
        from pydub import AudioSegment

        with tempfile.TemporaryDirectory() as folder:
            source = self._three_seconds(folder)
            clip = Path(folder) / "clip.wav"
            cut = _make_clip(source, clip, 1.0, 0.0, 3.0)
            self.assertEqual(cut["start"], 0.0)
            self.assertEqual(cut["end"], 1.0)
            self.assertTrue(cut["truncated"])
            self.assertAlmostEqual(len(AudioSegment.from_file(clip)) / 1000, 1.0, places=2)

    def test_a_region_without_audio_is_rejected(self):
        import tempfile

        with tempfile.TemporaryDirectory() as folder:
            source = self._three_seconds(folder)
            clip = Path(folder) / "clip.wav"
            with self.assertRaisesRegex(ValueError, "después del final"):
                _make_clip(source, clip, 240.0, 5.0, 6.0)
            with self.assertRaisesRegex(ValueError, "no tiene duración"):
                _make_clip(source, clip, 240.0, 2.0, 2.0)
            with self.assertRaisesRegex(ValueError, "negativo"):
                _make_clip(source, clip, 240.0, -1.0, None)

    def test_analysis_forwards_the_chosen_region_to_the_clip(self):
        music = _FakeMusic([{"status": 1, "result": json.dumps([{"genre": "techno"}])}])
        settings = SourceAnalysisSettings(poll_interval=0.0, timeout_seconds=5.0)
        clip = {"start": 1.0, "end": 2.0, "source_duration": 3.0, "truncated": False}
        with patch("source_understanding._make_clip", return_value=clip) as make_clip, \
                patch("source_understanding.category_catalog", return_value=self.catalog):
            asyncio.run(analyze_source(music, Path("fuente.mp3"), settings,
                                       lambda _phase: None, 1.0, 2.0))
        self.assertEqual(make_clip.call_args.args[2], settings.max_seconds)
        self.assertEqual(make_clip.call_args.args[3:], (1.0, 2.0))

    def test_analysis_does_not_mutate_model_metadata(self):
        metadata = {"genre": "techno", "prompt": "a description", "metas": {"bpm": 40}}
        before = json.dumps(metadata)
        classify_metadata(metadata, self.catalog)
        self.assertEqual(json.dumps(metadata), before)


if __name__ == "__main__":
    unittest.main()
