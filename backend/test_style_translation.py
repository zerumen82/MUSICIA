"""El estilo sale en inglés. La letra no se traduce. Una caption inglesa no se reescribe."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from config import AppSettings
from style_translator import (
    correct_translated_terms,
    reset_style_translation_cache,
    stop_style_translation_worker,
    style_for_engine,
    translation_worker_running,
)


class EnglishStyleStaysTest(unittest.TestCase):
    def setUp(self):
        stop_style_translation_worker()
        reset_style_translation_cache()

    def test_empty_stays_empty(self):
        self.assertEqual(style_for_engine(""), "")
        self.assertEqual(style_for_engine("   "), "")

    def test_english_captions_are_not_rewritten(self):
        for prompt in (
            "gabber",
            "A track with gabber",
            "A track with gabber hardcore",
            "Original prompt",
            "powerful kicks with bounce",
            "a car battery",
            "double bumper",
            "120 bpm",
            "Techno 120 bpm",
            "medieval flutes",
        ):
            with self.subTest(prompt=prompt):
                reset_style_translation_cache()
                self.assertEqual(style_for_engine(prompt), prompt)
        self.assertFalse(translation_worker_running())

    def test_language_without_code_is_sent_unchanged(self):
        # Un idioma que el traductor no conoce (el latín, p. ej.) no corta
        # la generación: el texto escrito viaja tal cual al motor.
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        path = Path(folder.name) / "map.json"
        path.write_text(json.dumps({"codes": {"en": "eng_Latn"}}), encoding="utf-8")
        settings = AppSettings()
        settings.style_translation.language_map = str(path)
        self.assertEqual(
            style_for_engine("Cambia la batería", settings), "Cambia la batería"
        )
        self.assertFalse(translation_worker_running())

    def test_broken_language_map_still_stops(self):
        # El mapa ausente o vacío es instalación rota, no un idioma sin código:
        # eso sigue cortando, para no enviar el estilo sin traducir por accidente.
        missing = AppSettings()
        missing.style_translation.language_map = "backend/no-esta-nllb_languages.json"
        with self.assertRaisesRegex(ValueError, "mapa de idiomas"):
            style_for_engine("Cambia la batería", missing)
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        path = Path(folder.name) / "map.json"
        path.write_text(json.dumps({"codes": {}}), encoding="utf-8")
        empty = AppSettings()
        empty.style_translation.language_map = str(path)
        with self.assertRaisesRegex(ValueError, "vacío"):
            style_for_engine("Cambia la batería", empty)
        self.assertFalse(translation_worker_running())


class CorrectedTermsTest(unittest.TestCase):
    def setUp(self):
        stop_style_translation_worker()
        reset_style_translation_cache()

    def test_measured_untranslated_bombo_is_corrected_only_with_spanish_source(self):
        self.assertEqual(correct_translated_terms("sin bombo", "without bombo"), "without kick")
        self.assertEqual(correct_translated_terms("sin bombos", "without bombs"), "without kicks")
        self.assertEqual(correct_translated_terms("without bombs", "without bombs"), "without bombs")
        self.assertEqual(correct_translated_terms("without kick", "without kick"), "without kick")
        self.assertEqual(correct_translated_terms("without drums", "a bombo sample"), "a bombo sample")

    def test_measured_words_change_and_english_battery_does_not(self):
        self.assertEqual(
            correct_translated_terms("Batería suave al fondo", "Soft battery at the bottom"),
            "Soft drums at the bottom",
        )
        self.assertEqual(
            correct_translated_terms("baterías suaves", "soft batteries"),
            "soft drums",
        )
        self.assertEqual(
            correct_translated_terms("bateria suave", "soft battery"),
            "soft drums",
        )
        self.assertEqual(
            correct_translated_terms("hardcore en 4x4 con doble bombo", "4x4 hardcore with double bumper"),
            "4x4 hardcore with double kick",
        )
        self.assertEqual(correct_translated_terms("bombos", "Bumpers"), "Kicks")
        self.assertEqual(correct_translated_terms("BOMBO", "BUMPER"), "KICK")
        self.assertEqual(correct_translated_terms("bombo", "kick"), "kick")
        self.assertEqual(
            correct_translated_terms("la batería y el bombo", "the battery and the bumper"),
            "the drums and the kick",
        )
        self.assertEqual(
            correct_translated_terms("suave al fondo", "Soft battery at the bottom"),
            "Soft battery at the bottom",
        )
        self.assertEqual(
            correct_translated_terms("a car battery", "a car battery"),
            "a car battery",
        )
        once = correct_translated_terms("doble bombo", "double bumper")
        self.assertEqual(correct_translated_terms("doble bombo", once), once)
        self.assertFalse(translation_worker_running())

    def test_a_missing_or_empty_file_is_not_sent(self):
        missing = AppSettings()
        missing.style_translation.term_fixes = "backend/no-esta-style-term-fixes.json"
        with self.assertRaisesRegex(ValueError, "correcciones"):
            style_for_engine("Cambia la batería", missing)
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        path = Path(folder.name) / "fixes.json"
        path.write_text("{", encoding="utf-8")
        broken = AppSettings()
        broken.style_translation.term_fixes = str(path)
        with self.assertRaisesRegex(ValueError, "no se leen"):
            correct_translated_terms("batería", "battery", broken)
        path.write_text(json.dumps({"fixes": []}), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "vacías"):
            correct_translated_terms("batería", "battery", broken)
        self.assertFalse(translation_worker_running())


class LocalTranslationTest(unittest.TestCase):
    def test_structured_short_exclusions_use_local_translation_and_keep_roles(self):
        import main
        from fastapi.testclient import TestClient
        from prompt_style import selected_style_rule

        client = TestClient(main.app)
        evidence = []
        for raw, main_style, noun, compatible in (
                ("sin bombo", "gabber", r"kick|drum|bass", False),
                ("sin bajo", "trance", r"bass", False),
                ("sin voz", "techno", r"voice|vocal", True)):
            with self.subTest(raw=raw):
                # Reproduce una abstención ya cacheada del detector general;
                # la pista fiable B9b no debe reutilizarla como traducción.
                style_for_engine(raw)
                body = {"prompt": raw, "main_style": main_style, "include_descriptions": True}
                response = client.post("/music/enhance_prompt", json=body)
                self.assertEqual(response.status_code, 200, response.text)
                result = response.json()
                english = result["enhanced"].lower()
                evidence.append({"raw": raw, "result": result})
                self.assertEqual(result["original"], raw)
                self.assertIn(f"Predominantly {main_style}.", result["enhanced"])
                self.assertNotRegex(english, r"\b(?:sin|bombo|bajo|voz)\b")
                self.assertRegex(english, r"\b(?:no|without)\b")
                self.assertRegex(english, noun)
                clause = selected_style_rule(main_style)["style"]
                self.assertEqual(clause in result["enhanced"], compatible)
                shown = client.post("/music/style-english", json={"prompt": result["enhanced"]})
                self.assertEqual(shown.status_code, 200, shown.text)
                self.assertEqual(shown.json()["prompt"], result["enhanced"])
                self.assertEqual(client.post("/music/enhance_prompt", json=body).json(), result)
        self.assertEqual(client.post("/music/enhance_prompt", json={
            "prompt": "without bass", "main_style": "techno", "include_descriptions": False,
        }).json()["enhanced"], "Predominantly techno. without bass")
        print(json.dumps(evidence, ensure_ascii=False, indent=2))

    def test_structured_plural_exclusion_is_measured_with_real_translator(self):
        import main
        from fastapi.testclient import TestClient

        result = TestClient(main.app).post("/music/enhance_prompt", json={
            "prompt": "sin bombos", "main_style": "gabber", "include_descriptions": True,
        })
        self.assertEqual(result.status_code, 200, result.text)
        prepared = result.json()
        print(json.dumps({"plural_measured": prepared}, ensure_ascii=False, indent=2))
        self.assertNotRegex(prepared["enhanced"].lower(), r"\b(?:sin|bombos)\b")
        self.assertRegex(prepared["enhanced"].lower(), r"\b(?:no|without)\b")
        self.assertRegex(prepared["enhanced"].lower(), r"kick|drum")

    def test_structured_prompt_translates_details_before_english_roles(self):
        import main
        from fastapi.testclient import TestClient

        client = TestClient(main.app)
        body = {"prompt": "sin voz y sin guitarras", "main_style": "techno",
                "influence_styles": ["trance"], "include_descriptions": True}
        response = client.post("/music/enhance_prompt", json=body)
        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()
        self.assertEqual(result["original"], body["prompt"])
        self.assertIn("Predominantly techno, with subtle influences of trance.", result["enhanced"])
        self.assertRegex(result["enhanced"].lower(), r"no (?:voice|vocals?)")
        self.assertIn("no guitars", result["enhanced"].lower())
        self.assertNotRegex(result["enhanced"].lower(), r"\b(?:sin|voz|guitarras)\b")
        shown = client.post("/music/style-english", json={"prompt": result["enhanced"]})
        self.assertEqual(shown.status_code, 200, shown.text)
        self.assertEqual(shown.json()["prompt"], result["enhanced"])
        repeated = client.post("/music/enhance_prompt", json=body)
        self.assertEqual(repeated.json(), result)

    def test_spanish_and_the_mixed_phrase_become_stable_english(self):
        spanish = "Batería suave al fondo"
        reset_style_translation_cache()
        first = style_for_engine(spanish)
        self.assertNotEqual(first.casefold(), spanish.casefold())
        self.assertNotIn("batería", first.casefold())
        self.assertNotIn("battery", first.casefold())
        self.assertIn("drums", first.casefold())
        reset_style_translation_cache()
        self.assertEqual(style_for_engine(spanish), first)
        reset_style_translation_cache()
        self.assertEqual(style_for_engine(first), first)

        mixed = "A track with gabber hardcore · kicks potentes con bounce"
        reset_style_translation_cache()
        translated = style_for_engine(mixed)
        self.assertNotIn("potentes", translated.casefold())
        self.assertTrue(translated.startswith("A track with gabber hardcore"))
        reset_style_translation_cache()
        self.assertEqual(style_for_engine(translated), translated)
        shouted = (
            "GABBER HARDCORE · KICK CONTUNDENTES, VIBRACION BOUNCE · "
            "PITIDOS DE COMPUTADORAS · MELODIA ORIGINAL CON SINTETIZADOR"
        )
        reset_style_translation_cache()
        heard = style_for_engine(shouted)
        low = heard.casefold()
        self.assertNotIn("contents", low)
        self.assertNotIn("questions", low)
        self.assertNotIn("demands", low)
        self.assertNotIn("vibracion", low)
        self.assertNotIn("pitidos", low)
        self.assertIn("gabber", low)
        self.assertIn("hardcore", low)
        self.assertRegex(low, r"kick")
        self.assertRegex(low, r"vibrat")
        self.assertRegex(low, r"whistl|beep|comput")
        self.assertRegex(low, r"synth|melod")
        reset_style_translation_cache()
        self.assertEqual(style_for_engine(shouted), heard)
        self.assertTrue(translation_worker_running())

    def test_french_and_german_sentences_change_and_lyrics_do_not(self):
        import main

        french = style_for_engine("Une piste de techno sombre")
        self.assertNotEqual(french.casefold(), "une piste de techno sombre")
        german = style_for_engine("Ein Track mit harten Kicks")
        self.assertNotEqual(german.casefold(), "ein track mit harten kicks")
        boundary = "hardcore en 4x4 con doble bombo"
        translated = style_for_engine(boundary)
        self.assertNotEqual(translated.casefold(), boundary.casefold())
        self.assertNotIn("doble", translated.casefold())
        self.assertNotIn("bombo", translated.casefold())
        self.assertNotIn("bumper", translated.casefold())
        self.assertRegex(translated.casefold(), r"\bkicks?\b")
        body = {
            "prompt": "Batería suave al fondo",
            "lyrics": "canta esto en español",
            "instrumental": False,
            "bpm": 120,
        }
        client_result = main._prepare_generation(main.MusicGenRequest(**body))
        generation, prepared = client_result
        self.assertEqual(generation.lyrics, "canta esto en español")
        self.assertEqual(prepared["effective_parameters"]["lyrics"], "canta esto en español")
        self.assertEqual(prepared["effective_parameters"]["prompt"], generation.prompt)
        self.assertNotIn("batería", generation.prompt.casefold())
        self.assertNotIn("battery", generation.prompt.casefold())
        self.assertIn("drums", generation.prompt.casefold())
        from fastapi.testclient import TestClient
        shown = TestClient(main.app).post("/music/style-english", json={"prompt": body["prompt"]})
        self.assertEqual(shown.status_code, 200)
        self.assertEqual(shown.json()["prompt"], generation.prompt)
