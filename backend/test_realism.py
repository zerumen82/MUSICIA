"""Ofertas realistas para el modelo (regla NO FAKE).

La app ofrece chips (AÑADIR), captions de estilo y términos de glosa. Nada de
eso puede usar vocabulario que el modelo no haya escrito, o el usuario pide
algo y el motor obedece otra cosa.

Oráculos (datos, no código):
  B = 400 captions del fabricante (examples/text2music + examples/simple_mode)
  A = acestep/genres_vocab.txt: vocabulario de ETIQUETAS de género del modelo

Regla: la prosa de una cláusula/caption tiene que salir de B. Un GÉNERO
nombrado dentro de su propia caption vale si sus tokens están en A
('A pounding frenchcore track...' es legítimo).

Si no están los datos (repo del motor no descargado), se salta: un test no
puede dar por bueno algo que no puede comprobar.
"""
from __future__ import annotations

import glob
import json
import re
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
EJEMPLOS = RAIZ / "vendor" / "ACE-Step-1.5" / "examples"
GENRES = RAIZ / "vendor" / "ACE-Step-1.5" / "acestep" / "genres_vocab.txt"
CATALOGO = RAIZ / "backend" / "style_catalog.json"
GLOSA = RAIZ / "frontend" / "src" / "prompt_gloss.js"
VARIANTES_JS = RAIZ / "frontend" / "src" / "variants.js"
VOCAL_JS = RAIZ / "frontend" / "src" / "vocal.js"

DISPONIBLES = EJEMPLOS.exists() and GENRES.exists()

VACIAS = set(
    """a an the of and with in on over throughout all is are as at for to from by
    into under near around its it their this that these those every each both such
    no not never anything something while when where which who what how than then
    there here one two through across within without during""".split()
)


def _norm(texto: str) -> str:
    texto = (texto or "").lower().replace("-", " ")
    texto = re.sub(r"[^a-z0-9 ]+", " ", texto)
    return re.sub(r"\s+", " ", texto).strip()


def _captions() -> str:
    ficheros = sorted(glob.glob(str(EJEMPLOS / "text2music" / "*"))) + sorted(
        glob.glob(str(EJEMPLOS / "simple_mode" / "*"))
    )
    return " . ".join(_norm(Path(f).read_text(encoding="utf-8", errors="ignore")) for f in ficheros)


def _generos() -> set[str]:
    tokens: set[str] = set()
    for linea in GENRES.read_text(encoding="utf-8", errors="ignore").splitlines():
        tokens.update(_norm(linea).split())
    return tokens


def _prosa_ausente(frase: str, captions: str) -> list[str]:
    return [
        palabra
        for palabra in _norm(frase).split()
        if palabra not in VACIAS and len(palabra) > 2 and palabra not in captions
    ]


@unittest.skipUnless(DISPONIBLES, "faltan datos del motor (vendor/ACE-Step-1.5)")
class TestOfertasRealistas(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.captions = _captions()
        cls.generos = _generos()
        cls.catalogo = json.loads(CATALOGO.read_text(encoding="utf-8"))
        cls.glosa = GLOSA.read_text(encoding="utf-8")
        cls.variantes = re.findall(
            r"\{ id: '([^']+)', label: '([^']+)', add: '([^']+)' \}",
            VARIANTES_JS.read_text(encoding="utf-8"),
        )
        cls.vocal_tags = re.findall(r"tag:\s*'([^']+)'", VOCAL_JS.read_text(encoding="utf-8")) if VOCAL_JS.exists() else []

    def test_vocal_tags_use_only_vocabulary_the_model_uses(self):
        self.assertTrue(self.vocal_tags, "no encontré tags vocales en frontend/src/vocal.js")
        for tag in self.vocal_tags:
            with self.subTest(tag=tag):
                ausentes = _prosa_ausente(tag, self.captions)
                falsos = [w for w in ausentes if w not in self.generos]
                self.assertEqual(
                    falsos,
                    [],
                    f"el tag vocal «{tag}» pide palabras que el modelo no escribe",
                )

    def test_chips_uses_only_vocabulary_the_model_uses(self):
        for mod in self.catalogo["modifiers"]:
            with self.subTest(chip=mod["label"]):
                self.assertEqual(
                    _prosa_ausente(mod["clause"], self.captions),
                    [],
                    f"el chip «{mod['label']}» pide al motor palabras que no usa",
                )

    def test_variantes_del_modelo(self):
        """Las VARIANTES del UI (inglés) usan el corpus y disparan estilo o
        modificador: si no, el motor improvisaría en vez de obedecer."""
        self.assertTrue(self.variantes, "no encontré variantes en frontend/src/variants.js")
        from prompt_style import analyze_prompt

        for nombre, etiqueta, texto in self.variantes:
            with self.subTest(variante=nombre):
                ausentes = _prosa_ausente(texto, self.captions)
                falsos = [w for w in ausentes if w not in self.generos]
                self.assertEqual(
                    falsos,
                    [],
                    f"la variante «{etiqueta}» pide palabras que el modelo no escribe",
                )
                info = analyze_prompt(texto)
                self.assertTrue(
                    info["detected_genre"] or info["modifiers"],
                    f"la variante «{etiqueta}» no dispara estilo ni modificador",
                )

    def test_style_captions_use_only_vocabulary_the_model_uses(self):
        for estilo in self.catalogo["styles"]:
            with self.subTest(estilo=estilo["name"]):
                ausentes = _prosa_ausente(estilo["style"], self.captions)
                # El nombre del género dentro de su propia caption es legítimo.
                falsos = [w for w in ausentes if w not in self.generos]
                self.assertEqual(
                    falsos,
                    [],
                    f"la caption de «{estilo['name']}» usa palabras que el modelo no escribe",
                )

    def test_style_keys_exist_in_the_model_genre_vocabulary(self):
        for estilo in self.catalogo["styles"]:
            with self.subTest(estilo=estilo["name"]):
                self.assertTrue(
                    any(all(p in self.generos for p in _norm(k.replace("re:", "")).split())
                        for k in estilo["keys"]),
                    f"el género «{estilo['name']}» no está en genres_vocab.txt",
                )

    def test_gloss_terms_exist_in_the_model_vocabulary(self):
        for termino in re.findall(r"en:\s*'([^']+)'", self.glosa):
            with self.subTest(termino=termino):
                partes = _norm(termino).split()
                self.assertTrue(
                    all(p in self.generos or p in self.captions for p in partes),
                    f"la glosa añade «{termino}» y el modelo no lo usa",
                )


if __name__ == "__main__":
    unittest.main()
