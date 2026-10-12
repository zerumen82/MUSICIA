"""Regresiones de géneros vecinos y contradicciones observadas en los logs."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from prompt_style import analyze_prompt, find_styles, style_caption  # noqa: E402


class StyleFidelityTest(unittest.TestCase):
    def test_generos_especificos_no_anaden_genero_vecino(self):
        for prompt, expected in (
            ("hard techno", ["hard techno"]),
            ("dubstep", ["dubstep"]),
            ("electrónica", ["electronica"]),
            ("synth pop", ["synthwave"]),
            ("popular", []),
        ):
            with self.subTest(prompt=prompt):
                self.assertEqual([r["name"] for r in find_styles(prompt)], expected)

    def test_traducciones_del_catalogo_son_generos_literales_del_modelo(self):
        import json
        root = Path(__file__).resolve().parent.parent
        catalog = json.loads((root / "backend/style_catalog.json").read_text(encoding="utf-8"))
        vocabulary = {line.lower().strip() for line in (root / "vendor/ACE-Step-1.5/acestep/genres_vocab.txt").read_text(encoding="utf-8").splitlines()}
        for alias, genre in catalog["matching"]["genre_translations"].items():
            with self.subTest(alias=alias):
                self.assertIn(genre, vocabulary)
                self.assertEqual(style_caption(alias), alias)

    def test_mezclas_explicitas_se_conservan(self):
        self.assertEqual(set(r["name"] for r in find_styles("hard techno y techno")), {"hard techno", "techno"})
        self.assertEqual(set(r["name"] for r in find_styles("flamenco pop")), {"flamenco", "pop"})

    def test_negaciones_no_anaden_positivos(self):
        for prompt in ("sin techno", "no techno", "without techno", "sin baterías", "without drums", "no distorted kick"):
            with self.subTest(prompt=prompt):
                self.assertEqual(style_caption(prompt), prompt)
                self.assertFalse(analyze_prompt(prompt)["modifiers"])
        self.assertEqual([r["name"] for r in find_styles("sin hardstyle, gabber")], ["hardcore holandes"])

    def test_gabber_y_hardcore_no_envian_hardstyle(self):
        for prompt in ("gabber", "hardcore", "hardtek gabber"):
            with self.subTest(prompt=prompt):
                self.assertTrue(style_caption(prompt).startswith(prompt))
                self.assertNotIn("hardstyle", style_caption(prompt).lower())

    def test_descripcion_no_introduce_genero_diferente(self):
        for prompt, other in (("jungle", "drum and bass"), ("disco", "funk"), ("synth pop", "synthwave")):
            with self.subTest(prompt=prompt):
                self.assertNotIn(other, style_caption(prompt).lower())

    def test_negacion_de_instrumento_no_recibe_descripcion_positiva(self):
        for prompt, unwanted in (("metal sin guitarras", "electric guitars"), ("techno sin baterías", "kick"), ("techno sin bombo", "kick"), ("metal sin bombo", "double bass drumming"), ("techno without kick drum", "four-on-the-floor kick"), ("jazz sin melodías", "melodic")):
            with self.subTest(prompt=prompt):
                self.assertNotIn(unwanted, style_caption(prompt).lower())

    def test_negaciones_coordinadas_no_anaden_instrumentos(self):
        for prompt in ("metal sin guitarra ni batería", "rock without guitar or drums"):
            with self.subTest(prompt=prompt):
                self.assertEqual(style_caption(prompt), prompt)

    def test_repeticion_positiva_despues_de_negacion_se_reconoce(self):
        self.assertEqual([r["name"] for r in find_styles("no techno, mejor techno oscuro")], ["techno"])

    def test_detalles_positivos_siguen_viajando_con_descripcion_excluida(self):
        caption = style_caption("metal sin guitarras con doble bombo")
        self.assertEqual(caption, "metal sin guitarras con doble bombo")
        self.assertNotIn("electric guitars", caption)
        self.assertEqual(style_caption("algo distorsionado sin guitarras"), "algo distorsionado sin guitarras")

    def test_componer_dos_veces_no_anade_estilos_por_la_descripcion(self):
        for prompt in ("gabber", "metal sin guitarras", "hard techno y techno", "techno hardcore trance"):
            with self.subTest(prompt=prompt):
                once = style_caption(prompt)
                self.assertEqual(style_caption(once), once)


if __name__ == "__main__":
    unittest.main()
