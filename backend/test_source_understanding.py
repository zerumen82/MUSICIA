"""Classification is advisory and grounded in audio-derived genre metadata."""
import json
from pathlib import Path
import unittest

from source_understanding import classify_metadata


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

    def test_analysis_does_not_mutate_model_metadata(self):
        metadata = {"genre": "techno", "prompt": "a description", "metas": {"bpm": 40}}
        before = json.dumps(metadata)
        classify_metadata(metadata, self.catalog)
        self.assertEqual(json.dumps(metadata), before)


if __name__ == "__main__":
    unittest.main()
