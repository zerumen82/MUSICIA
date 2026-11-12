"""B9c: fichas exactas con procedencia y aplicación efectiva, sin GPU ni red."""
from __future__ import annotations

import hashlib
import json
import sys
import unittest
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import genre_glossary  # noqa: E402
from prompt_enhancer import MAX_PROMPT_CHARS, enhance_prompt  # noqa: E402
from prompt_style import (  # noqa: E402
    DOCUMENTED_DESCRIPTIONS, STYLE_RULES, find_styles, style_description,
    without_catalog_descriptions,
)
from test_realism import _captions, _generos, _prosa_ausente  # noqa: E402

LABEL = "techno hard house"
APPROVED_TEXT = (
    "A high-energy electronic track with a steady four-on-the-floor rhythm, "
    "hard kicks, driving basslines and hypnotic synth patterns."
)


class DocumentedDescriptionTest(unittest.TestCase):
    def test_exact_ficha_preserves_approved_text_and_editorial_provenance(self):
        description = style_description("  Techno  Hard House ")
        self.assertEqual(description["text"], APPROVED_TEXT)
        provenance = description["provenance"]
        self.assertEqual(provenance["kind"], "musicia_editorial")
        self.assertEqual(provenance["approved_at"], "2026-11-12")
        self.assertEqual(len(provenance["sources"]), 2)
        for source in provenance["sources"]:
            self.assertTrue(source["title"])
            self.assertTrue(source["url"].startswith("https://"))
            self.assertTrue(source["accessed_at"])
        self.assertIn("no es una definición oficial", provenance["note"])

    def test_no_partial_fallback_or_new_detection_rule(self):
        self.assertEqual(len(STYLE_RULES), 29)
        for label in ("acid jazz", "minimal techno hard house", "techno hard house deluxe"):
            with self.subTest(label=label):
                self.assertIsNone(style_description(label))
        self.assertFalse(any(rule["name"] == LABEL for rule in find_styles(LABEL)))
        self.assertFalse(without_catalog_descriptions(APPROVED_TEXT).strip())
        self.assertNotIn(APPROVED_TEXT, enhance_prompt(LABEL)["enhanced"])

    def test_existing_catalog_fichas_keep_their_text_and_honest_origin(self):
        for rule in STYLE_RULES:
            with self.subTest(rule=rule["name"]):
                description = style_description(rule["name"])
                self.assertEqual(description["text"], rule["style"])
                self.assertEqual(description["provenance"]["kind"], "musicia_catalog")
                self.assertEqual(description["provenance"]["sources"], [])

    def test_returned_provenance_cannot_mutate_catalog(self):
        style_description(LABEL)["provenance"]["sources"].clear()
        self.assertEqual(len(style_description(LABEL)["provenance"]["sources"]), 2)

    @unittest.skipUnless(genre_glossary.VOCAB_PATH.exists(), "falta vocabulario local")
    def test_local_source_hash_label_and_caption_words_are_real(self):
        self.assertEqual(genre_glossary.glossary_line(LABEL), LABEL)
        captions, genre_tokens = _captions(), _generos()
        for description in DOCUMENTED_DESCRIPTIONS:
            self.assertIsNotNone(genre_glossary.glossary_line(description["label"]))
            self.assertEqual([word for word in _prosa_ausente(description["text"], captions)
                              if word not in genre_tokens], [])
            for source in description["provenance"]["sources"]:
                if "local_path" in source:
                    path = BACKEND_DIR.parent / source["local_path"]
                    self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), source["sha256"])
                    self.assertIsInstance(json.loads(path.read_text(encoding="utf-8")), dict)


@unittest.skipUnless(genre_glossary.VOCAB_PATH.exists(), "falta vocabulario local")
class AppliedDescriptionTest(unittest.TestCase):
    def test_main_adds_exact_description_and_metadata_without_new_bpm(self):
        result = enhance_prompt("sin voz", main_style=LABEL)
        self.assertEqual(result["selection"]["main_style"], LABEL)
        self.assertIn("Predominantly techno hard house.", result["enhanced"])
        self.assertIn("sin voz", result["enhanced"])
        self.assertIn(APPROVED_TEXT, result["enhanced"])
        self.assertEqual(result["applied_descriptions"], [{"label": LABEL, **style_description(LABEL)}])
        self.assertEqual(result["additions"].count(APPROVED_TEXT), 1)
        self.assertIsNone(result["suggested_bpm"])
        self.assertEqual(result["warnings"], [])

    def test_off_keeps_details_and_roles_but_no_applied_metadata(self):
        result = enhance_prompt("sin voz", main_style=LABEL, include_descriptions=False)
        self.assertIn(LABEL, result["enhanced"])
        self.assertIn("sin voz", result["enhanced"])
        self.assertNotIn(APPROVED_TEXT, result["enhanced"])
        self.assertEqual(result["applied_descriptions"], [])

    def test_influence_does_not_add_its_description_or_provenance(self):
        result = enhance_prompt("", main_style="techno", influence_styles=[LABEL])
        self.assertNotIn(APPROVED_TEXT, result["enhanced"])
        self.assertIn(LABEL, result["enhanced"])
        self.assertEqual([item["label"] for item in result["applied_descriptions"]], ["techno"])

    def test_exclusions_block_plural_kicks_basslines_and_synths(self):
        for detail in ("sin bombo", "sin batería", "sin bajo", "sin sintetizadores", "sin meditación"):
            with self.subTest(detail=detail):
                result = enhance_prompt(detail, main_style=LABEL)
                self.assertNotIn(APPROVED_TEXT, result["enhanced"])
                self.assertEqual(result["applied_descriptions"], [])
                self.assertTrue(result["warnings"])
                self.assertIn(detail, result["enhanced"])
        for exclusion in ("sin bombo", "sin bajo"):
            with self.subTest(other_track=exclusion):
                result = enhance_prompt("sin voz", main_style=LABEL, exclusion_source=exclusion)
                self.assertNotIn(APPROVED_TEXT, result["enhanced"])
                self.assertEqual(result["applied_descriptions"], [])

    def test_negated_selection_is_rejected_and_unknown_stays_without_ficha(self):
        with self.assertRaises(ValueError):
            enhance_prompt(f"sin {LABEL}", main_style=LABEL)
        result = enhance_prompt("", main_style="acid jazz")
        self.assertEqual(result["applied_descriptions"], [])
        self.assertTrue(result["warnings"])
        self.assertNotIn(style_description("jazz")["text"], result["enhanced"])

    def test_existing_or_length_omitted_description_is_not_marked_added(self):
        for details in (APPROVED_TEXT, "x" * MAX_PROMPT_CHARS):
            with self.subTest(details=details[:20]):
                result = enhance_prompt(details, main_style=LABEL)
                self.assertEqual(result["applied_descriptions"], [])
                self.assertLessEqual(result["enhanced"].count(APPROVED_TEXT), 1)
        first = enhance_prompt("sin voz", main_style=LABEL)
        second = enhance_prompt(first["enhanced"], main_style=LABEL)
        self.assertEqual(second["enhanced"], first["enhanced"])
        self.assertEqual(second["applied_descriptions"], [])


@unittest.skipUnless(genre_glossary.VOCAB_PATH.exists(), "falta vocabulario local")
class GlossaryDescriptionsTest(unittest.TestCase):
    def test_search_metadata_only_covers_returned_exact_labels(self):
        result = genre_glossary.search(LABEL)
        self.assertIn(LABEL, result["items"])
        self.assertEqual(result["descriptions"][LABEL], style_description(LABEL))
        self.assertLessEqual(set(result["descriptions"]), set(result["items"]))
        result = genre_glossary.search("acid jazz")
        self.assertIn("acid jazz", result["items"])
        self.assertNotIn("acid jazz", result["descriptions"])
        self.assertEqual(genre_glossary.search("no-real-genre-zzqq")["descriptions"], {})

    def test_combine_uses_same_exact_metadata_and_respects_limit(self):
        result = genre_glossary.combine("techno", "hard house", limit=2)
        self.assertIn(LABEL, result["items"])
        self.assertEqual(result["descriptions"], {LABEL: style_description(LABEL)})
        limited = genre_glossary.combine("techno", "hard house", limit=1)
        self.assertEqual(len(limited["items"]), 1)
        self.assertLessEqual(set(limited["descriptions"]), set(limited["items"]))
        self.assertEqual(genre_glossary.combine("techno", "techno")["descriptions"], {})
        self.assertEqual(genre_glossary.combine("", "techno")["descriptions"], {})


if __name__ == "__main__":
    unittest.main()
