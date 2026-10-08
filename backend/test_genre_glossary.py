"""Glosario de estilos: todo lo que devuelve es vocabulario real del motor (NO FAKE).

El archivo `genres_vocab.txt` es la whitelist que el motor usa para escribir el
campo genres. Si el glosario ofreciera una forma que no está en ese archivo, el
usuario pediría un estilo que el modelo no puede decir.

Se ejecuta con el venv del backend:
    backend\\venv\\Scripts\\python.exe -m unittest backend.test_genre_glossary -v
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import genre_glossary  # noqa: E402

DISPONIBLE = genre_glossary.VOCAB_PATH.exists()


def _lineas_vocab() -> set[str]:
    """Líneas del archivo del modelo, para comprobar pertenencia literal."""
    return {
        line.strip()
        for line in genre_glossary.VOCAB_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    }


class Busqueda(unittest.TestCase):
    """Búsqueda en el vocabulario del modelo."""

    @unittest.skipUnless(DISPONIBLE, "falta vendor/ACE-Step-1.5 (vocabulario del motor)")
    def test_sin_consulta_devuelve_los_primeros(self) -> None:
        res = genre_glossary.search("", limit=50)
        self.assertTrue(res["available"])
        self.assertGreater(res["total"], 100_000)
        self.assertEqual(len(res["items"]), 50)
        self.assertTrue(res["source"].endswith("genres_vocab.txt"))

    @unittest.skipUnless(DISPONIBLE, "falta vendor/ACE-Step-1.5 (vocabulario del motor)")
    def test_búsqueda_por_subcadena(self) -> None:
        res = genre_glossary.search("house", limit=40)
        self.assertGreater(res["total"], 0)
        self.assertTrue(all("house" in item.lower() for item in res["items"]))
        self.assertTrue(res["items"][0].lower().startswith("house"), res["items"][:3])

    @unittest.skipUnless(DISPONIBLE, "falta vendor/ACE-Step-1.5 (vocabulario del motor)")
    def test_no_sirve_el_archivo_entero(self) -> None:
        self.assertLessEqual(len(genre_glossary.search("a", limit=10**6)["items"]), genre_glossary.MAX_LIMIT)
        self.assertGreaterEqual(len(genre_glossary.search("a", limit=0)["items"]), 1)

    @unittest.skipUnless(DISPONIBLE, "falta vendor/ACE-Step-1.5 (vocabulario del motor)")
    def test_todo_resultado_es_una_linea_del_archivo(self) -> None:
        lineas = _lineas_vocab()
        for query in ("", "techno", "hardcore", "house", "jazz"):
            for item in genre_glossary.search(query, limit=50)["items"]:
                self.assertIn(item, lineas, f"«{item}» no está en el vocabulario del modelo")
        combinado = genre_glossary.combine("techno", "hardcore", limit=50)
        for item in combinado["items"]:
            self.assertIn(item, lineas, f"«{item}» no está en el vocabulario del modelo")

    @unittest.skipUnless(DISPONIBLE, "falta vendor/ACE-Step-1.5 (vocabulario del motor)")
    def test_combinaciones_son_reales(self) -> None:
        res = genre_glossary.combine("techno", "hardcore")
        self.assertIn("hardcore techno", res["exact"])
        self.assertGreater(res["total"], 0)
        for item in res["items"]:
            self.assertIn("techno", item.lower())
            self.assertIn("hardcore", item.lower())
        self.assertEqual(res["items"][: len(res["exact"])], res["exact"])

    @unittest.skipUnless(DISPONIBLE, "falta vendor/ACE-Step-1.5 (vocabulario del motor)")
    def test_no_inventa_formas_imposibles(self) -> None:
        self.assertEqual(genre_glossary.combine("zzqq", "wxyz")["total"], 0)
        self.assertEqual(genre_glossary.combine("techno", "techno")["total"], 0)
        self.assertEqual(genre_glossary.combine("", "techno")["items"], [])


class Catalogo(unittest.TestCase):
    """Estilos propios de Musicia, servidos con el mismo vocabulario."""

    def test_estilos_con_nombre_caption_y_bpm(self) -> None:
        styles = genre_glossary.catalog_styles()
        self.assertGreaterEqual(len(styles), 10)
        for style in styles:
            self.assertTrue(style["name"])
            self.assertTrue(style["text"])
            self.assertIsInstance(style["bpm"], int)

    def test_genre_es_una_linea_literal_del_vocabulario(self) -> None:
        """Lo que el glosario añade como género está en genres_vocab.txt."""
        _, lower = genre_glossary._vocab()
        voc = set(lower)
        styles = genre_glossary.catalog_styles(voc)
        con_genre = [s for s in styles if s["genre"]]
        self.assertGreaterEqual(len(con_genre), 20)
        for style in con_genre:
            with self.subTest(estilo=style["name"]):
                self.assertIn(style["genre"].lower(), voc)
        por_nombre = {s["name"]: s["genre"] for s in styles}
        # Claves multipalabra cuya frase completa sí es línea del modelo
        # (el control viejo, palabra a palabra, las descartaba por error).
        self.assertEqual(por_nombre.get("hard techno"), "hard techno")
        self.assertEqual(por_nombre.get("hard bounce"), "hard house")


class SinDatos(unittest.TestCase):
    """Sin el archivo del modelo el glosario se queda vacío: nunca inventa."""

    def test_archivo_ausente_devuelve_vacio(self) -> None:
        ausente = BACKEND_DIR / "no_existe_genres_vocab.txt"
        with patch.object(genre_glossary, "VOCAB_PATH", ausente), patch.object(genre_glossary, "_WARNED", True):
            res = genre_glossary.search("house")
            self.assertFalse(res["available"])
            self.assertEqual(res["items"], [])
            self.assertEqual(res["total"], 0)
            self.assertEqual(genre_glossary.combine("techno", "hardcore")["items"], [])


if __name__ == "__main__":
    unittest.main()
