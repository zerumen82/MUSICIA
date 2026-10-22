"""Ofertas realistas para el modelo (regla NO FAKE).

La app ofrece chips y textos voluntarios de catálogo. Estos datos se
contrastan con ejemplos del fabricante, sin tratar el corpus como vocabulario
cerrado del encoder ni usarlo para afirmar fidelidad musical.

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
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

RAIZ = BACKEND_DIR.parent
EJEMPLOS = RAIZ / "vendor" / "ACE-Step-1.5" / "examples"
GENRES = RAIZ / "vendor" / "ACE-Step-1.5" / "acestep" / "genres_vocab.txt"
CATALOGO = RAIZ / "backend" / "style_catalog.json"
GLOSA = RAIZ / "frontend" / "src" / "prompt_gloss.js"
VARIANTES_JS = RAIZ / "frontend" / "src" / "variants.js"
VOCAL_JS = RAIZ / "frontend" / "src" / "vocal.js"
GENRES_JS = RAIZ / "frontend" / "src" / "genres.js"

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

    def test_exclusion_keys_use_only_vocabulary_the_model_uses(self):
        """Cada caption_key debe existir en los captions del fabricante.

        La familia de exclusión decide si una descripción se omite. Si la
        palabra no está en el vocabulario del fabricante, esa familia no puede
        reconocerla y el modelo tampoco la escribiría.
        """
        for familia in self.catalogo["caption_exclusions"]:
            for key in familia["caption_keys"]:
                with self.subTest(clave=key):
                    patron = key[3:] if key.startswith("re:") else re.escape(key)
                    self.assertIsNotNone(
                        re.search(patron, self.captions),
                        f"la clave de exclusión {key} no aparece en los captions del fabricante",
                    )

    def test_variantes_del_modelo(self):
        """Variantes elegidas: datos revisados, conservados sin expansión automática."""
        self.assertTrue(self.variantes, "no encontré variantes en frontend/src/variants.js")
        from prompt_style import style_caption

        for nombre, etiqueta, texto in self.variantes:
            with self.subTest(variante=nombre):
                ausentes = _prosa_ausente(texto, self.captions)
                falsos = [w for w in ausentes if w not in self.generos]
                self.assertEqual(
                    falsos,
                    [],
                    f"la variante «{etiqueta}» pide palabras que el modelo no escribe",
                )
                self.assertEqual(style_caption(texto), texto)

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

    @unittest.skipUnless(shutil.which("node"), "falta Node para ejecutar la vista previa real")
    def test_preview_frontend_equals_backend_caption(self):
        """Recorrido Node → backend de los prompts que antes cambiaban su intención."""
        from prompt_style import style_caption

        prompts = [
            "batería suave al fondo", "bajo potente, sin voz", "jazz con contrabajo",
            "techno", "electrónica", "sin guitarra ni batería",
            "si hay voz consérvala; cambia solo la percusión",
        ]
        script = (
            "import { glossPrompt } from './frontend/src/prompt_gloss.js';"
            "import { readFileSync } from 'node:fs';"
            "const inputs = JSON.parse(readFileSync(0, 'utf8'));"
            "process.stdout.write(JSON.stringify(inputs.map(glossPrompt)));"
        )
        execution = subprocess.run(
            [shutil.which("node"), "--input-type=module", "-e", script],
            cwd=RAIZ, input=json.dumps(prompts), text=True, encoding="utf-8",
            capture_output=True, timeout=30, check=True,
        )
        previews = json.loads(execution.stdout)
        self.assertEqual(len(previews), len(prompts))
        for original, preview in zip(prompts, previews):
            with self.subTest(original=original):
                self.assertEqual(preview, original)
                self.assertEqual(style_caption(preview), preview)

    def test_las_bases_del_remix_son_del_vocabulario_del_modelo(self):
        """El prompt que sugiere el remix (SUBIR y BIBLIOTECA) va en inglés y
        solo con palabras de las captions del modelo: antes era prosa en
        español que el motor ignoraba aunque el panel prometía «ENVÍA»
        (auditoría 2026-10-08). La explicación (basis) sí es español: es UI."""
        from prompt_enhancer import (
            REMIX_BASES,
            REMIX_BASS_BALANCED,
            REMIX_BASS_STRONG,
            REMIX_DYN_EXPRESSIVE,
            REMIX_DYN_STEADY,
            REMIX_PAUSES,
        )

        self.assertEqual(sorted(REMIX_BASES), ["mixta", "musica", "otro", "voz"])
        trozos = [
            REMIX_BASS_STRONG, REMIX_BASS_BALANCED,
            REMIX_DYN_STEADY, REMIX_DYN_EXPRESSIVE, REMIX_PAUSES,
        ]
        for texto in [*REMIX_BASES.values(), *trozos]:
            with self.subTest(texto=texto):
                self.assertEqual(
                    _prosa_ausente(texto, self.captions),
                    [],
                    f"la base del remix «{texto}» usa palabras que el modelo no escribe",
                )

    def test_genres_js_only_offers_genres_the_model_can_write(self):
        """El selector GÉNERO (CREAR + ASISTENTE) añade al prompt un `genre`
        que tiene que ser LÍNEA LITERAL de genres_vocab.txt: si no, el
        usuario pide un estilo que el modelo no puede emitir (bug 2026-10-08:
        5 de 29 no estaban: hardcore holandes, uptempo, hard bounce,
        acustico, orquestal)."""
        self.assertTrue(GENRES_JS.exists(), "no encuentro frontend/src/genres.js")
        lineas = {
            linea.strip().lower()
            for linea in GENRES.read_text(encoding="utf-8", errors="ignore").splitlines()
            if linea.strip()
        }
        generos = re.findall(r"genre: '([^']+)'", GENRES_JS.read_text(encoding="utf-8"))
        self.assertTrue(generos, "no extraje ningún genre de genres.js")
        for g in generos:
            with self.subTest(genre=g):
                self.assertIn(
                    g.lower(),
                    lineas,
                    f"el género «{g}» de genres.js no es una línea literal de genres_vocab.txt",
                )

    def test_genres_js_agrees_with_the_backend_catalog(self):
        """Mismo estilo ⇒ mismo texto en el selector GÉNERO y en el GLOSARIO:
        la fuente de verdad del género es catalog_styles() (backend), y
        genres.js no puede divergir (bug 2026-10-08: el glosario añadía
        «gabber» y el selector «hardcore holandes» para el mismo estilo)."""
        from genre_glossary import catalog_styles

        backend = {s["name"]: s["genre"] for s in catalog_styles()}
        pares = re.findall(
            r"\{ id: '([^']+)', label: '[^']+', bpm: \d+, genre: '([^']+)' \}",
            GENRES_JS.read_text(encoding="utf-8"),
        )
        self.assertTrue(pares, "no extraje los estilos de genres.js")
        self.assertEqual(len(pares), len(backend), "genres.js y el catálogo del backend no tienen los mismos estilos")
        for nombre, genre in pares:
            with self.subTest(estilo=nombre):
                self.assertIn(nombre, backend, f"el estilo «{nombre}» no está en el catálogo del backend")
                self.assertEqual(
                    genre,
                    backend[nombre],
                    f"«{nombre}»: el selector añade «{genre}» y el glosario «{backend[nombre]}»",
                )


if __name__ == "__main__":
    unittest.main()
