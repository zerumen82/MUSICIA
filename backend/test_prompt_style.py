"""Caption de estilo y MEJORAR PROMPT, sin GPU ni red.

Se ejecuta con el venv del backend:
    backend\\venv\\Scripts\\python.exe -m unittest backend.test_prompt_style -v
"""

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from prompt_enhancer import enhance_prompt  # noqa: E402
from genre_glossary import VOCAB_PATH  # noqa: E402
from prompt_style import (  # noqa: E402
    STYLE_MODIFIERS,
    STYLE_RULES,
    analyze_prompt,
    find_modifiers,
    find_style,
    find_styles,
    known_spanish_exclusion_details,
    style_bpm,
    style_caption,
)

PROMPT = "baterias techno hardcore holandés"
CLAUSES = {rule["name"]: rule["style"] for rule in STYLE_RULES}


def _vocab_lines() -> set[str]:
    """Líneas literales del vocabulario del modelo (genres_vocab.txt)."""
    return {line.strip().lower() for line in VOCAB_PATH.read_text(encoding="utf-8").splitlines() if line.strip()}


class FindStyleTest(unittest.TestCase):
    """find_style: el estilo lo elige el propio prompt, no un género ajeno."""

    def test_catalogo_json_con_esquema_valido(self):
        """El catálogo es datos (NO HARDCODE): existe, valida y las regex compilan."""
        import json
        import re as _re
        catalog = json.loads((BACKEND_DIR / "style_catalog.json").read_text(encoding="utf-8"))
        self.assertTrue(catalog["styles"] and catalog["modifiers"])
        for rule in catalog["styles"]:
            self.assertTrue(rule["keys"] and rule["name"] and rule["style"])
            self.assertIsInstance(rule["bpm"], int)
            for key in rule["keys"]:
                if key.startswith("re:"):
                    _re.compile(key[3:])
        for mod in catalog["modifiers"]:
            for field in ("label", "text", "keys", "suggest_with", "clause"):
                self.assertIn(field, mod)
        names = [r["name"] for r in catalog["styles"]]
        self.assertLess(names.index("trap"), names.index("hip hop"))

    def test_hardcore_holandes_gana_a_techno(self):
        rule = find_style(PROMPT)
        self.assertIsNotNone(rule)
        self.assertEqual(rule["name"], "hardcore holandes")
        self.assertEqual(rule["bpm"], 180)

    def test_insensible_a_mayusculas_y_acentos(self):
        self.assertEqual(find_style("GABBER de ROTTERDAM")["name"], "hardcore holandes")
        self.assertEqual(find_style("lo-fi suave")["name"], "lo-fi")

    def test_sin_estilo_no_devuelve_nada(self):
        self.assertIsNone(find_style("cancion bonita para mi novia"))
        self.assertIsNone(find_style(""))
        self.assertIsNone(find_style("te"))

    def test_el_especifico_gana_al_generico(self):
        self.assertEqual(find_style("hard techno oscuro")["name"], "hard techno")
        self.assertEqual(find_style("hardcore techno de rotterdam")["name"], "hardcore holandes")
        self.assertEqual(find_style("trance epico")["name"], "trance")

    def test_tres_estilos_se_detectan_todos(self):
        """Bug 2026-10-10: con 3 estilos solo viajaba el primero."""
        rules = find_styles("techno hardcore trance")
        names = [r["name"] for r in rules]
        self.assertGreaterEqual(len(names), 2)
        self.assertEqual(len(names), len(set(names)))

    def test_caption_conserva_mezcla_sin_presets(self):
        self.assertEqual(style_caption("techno hardcore trance"), "techno hardcore trance")

    def test_caption_multiestilo_es_idempotente(self):
        once = style_caption("techno hardcore trance")
        self.assertEqual(style_caption(once), once)

    def test_bpm_multiestilo_es_el_del_primero(self):
        first = find_styles("techno hardcore trance")
        if first:
            self.assertEqual(style_bpm("techno hardcore trance"), first[0]["bpm"])

    def test_analyze_expone_todos_los_generos(self):
        info = analyze_prompt("techno hardcore trance")
        self.assertTrue(info["detected_genres"])
        self.assertEqual(info["detected_genre"], info["detected_genres"][0])


class StyleCaptionTest(unittest.TestCase):
    """Casos que antes invertían el papel, el carácter o las restricciones."""

    def test_instrumentos_conservan_su_papel(self):
        for prompt in (
            "batería suave al fondo", "bajo potente, sin voz",
            "jazz con contrabajo", "piano protagonista y batería discreta",
            "guitarras limpias, nada de riffs distorsionados",
            "melodía potente con voz susurrada", "sin guitarra ni batería",
            "voz al fondo, sin modificar el bajo",
        ):
            with self.subTest(prompt=prompt):
                self.assertEqual(style_caption(prompt), prompt)

    def test_generos_no_autorizan_recetas(self):
        for prompt in ("techno", "electrónica", "gabber", "jungle", "rap", "synth pop"):
            with self.subTest(prompt=prompt):
                self.assertEqual(style_caption(prompt), prompt)

    def test_instrucciones_y_ambiguedad_no_se_resuelven_con_listas(self):
        for prompt in (
            "cambia solo la batería; conserva el resto",
            "si hay voz, consérvala; no añadas una cantante",
            "más cálido sin ralentizarlo", "crea algo extraño, evita lo oscuro",
            "conserva los sintes y sustituye la percusión por palmas",
            "no techno: prefiero jazz; nada de voces",
        ):
            with self.subTest(prompt=prompt):
                self.assertEqual(style_caption(prompt), prompt)

    def test_puntuacion_saltos_y_texto_largo_no_se_recortan(self):
        prompt = "Conserva esto.\nDespués aquello; sin cambios: ¡sí! " + "detalle " * 180
        self.assertEqual(style_caption(prompt), prompt.strip())

    def test_clausulas_voluntarias_se_conservan_sin_repetir(self):
        clause = STYLE_MODIFIERS[0]["clause"]
        prompt = f"techno. {clause}"
        self.assertEqual(style_caption(prompt), prompt)
        self.assertEqual(style_caption(style_caption(prompt)), prompt)

    def test_palabras_de_busqueda_no_se_marcan_como_roles_elegidos(self):
        for prompt in ("batería suave al fondo", "bajo potente", "jazz con double bass"):
            with self.subTest(prompt=prompt):
                self.assertEqual(find_modifiers(prompt), ())

    def test_frase_de_chip_completa_se_reconoce(self):
        mod = next(mod for mod in STYLE_MODIFIERS if mod["label"] == "Doble bombo")
        self.assertIn(mod["clause"], find_modifiers(f"hardcore {mod['text']}"))
        self.assertIn(mod["clause"], find_modifiers(f"hardcore {mod['clause']}"))


class NewCatalogTest(unittest.TestCase):
    """Filas nuevas del catálogo (2026-10-06): huecos de la propia UI."""

    def test_synthwave_del_desplegable(self):
        rule = find_style("synthwave nocturno con bajo analógico y arpegios retro")
        self.assertIsNotNone(rule)
        self.assertEqual(rule["name"], "synthwave")
        self.assertEqual(rule["bpm"], 100)

    def test_electronica_antes_que_electro(self):
        """«Electrónica» contiene «electro»: la regla específica gana."""
        self.assertEqual(find_style("electrónica moderna con bajos profundos")["name"], "electronica")
        self.assertEqual(find_style("electro funk con drum machine")["name"], "electro")

    def test_folk_acustico(self):
        self.assertEqual(find_style("acústico con guitarras y folk")["name"], "folk acustico")
        self.assertEqual(find_style("folk rock con armónica")["name"], "folk acustico")
        self.assertEqual(
            find_style("instrumentación acústica, guitarras y cuerdas")["name"], "folk acustico"
        )

    def test_calma_cae_en_ambient(self):
        self.assertEqual(find_style("canción tranquila para dormir")["name"], "ambient")

    def test_sin_voz_como_modificador(self):
        clausulas = find_modifiers("techno contundente sin voz, instrumental")
        self.assertEqual(len(clausulas), 1)
        self.assertIn("no vocals", clausulas[0])
        # Solo se detecta al escribirlo: nunca se sugiere como chip.
        chips = {c["label"]: c for c in analyze_prompt("techno")["chips"]}
        self.assertFalse(chips["Sin voz"]["suggested"])

    def test_lofi_hiphop_lofi_gana(self):
        """Corregido 2026-10-06 (UI negra + auditoría de vocabulario): lo-fi
        va antes que hip hop en el catálogo, así que «lo-fi hip hop» cae en
        lo-fi y no en hip hop genérico."""
        self.assertEqual(find_style("lo-fi suave con piano y vinilo, relajado")["name"], "lo-fi")
        self.assertEqual(find_style("hip hop con boom bap")["name"], "hip hop")

    def test_rap_no_secuestra_rapido(self):
        """No hay clave «rap»: sería subcadena de «rápido» y robaría tempos."""
        self.assertIsNone(find_style("rapido y veloz sin género"))

    def test_variantes_del_remix_disparan_regla(self):
        """Cada texto de VARIANTS (RemixIAPanel) reconoce estilo o detalle:
        si no, el motor improvisaría (auditoría 2026-10-06)."""
        variantes = [
            "enérgica y potente, driving, ritmo rápido e imparable",
            "tranquila para dormir, tempo lento y espacioso, ambient",
            "oscuro y tenso, dark, melancólico en tono menor",
            "luminoso y optimista, brillante, uplifting",
            "acústico con guitarras, folk, cuerdas y contrabajo",
            "electrónica con sintetizadores, caja de ritmos y 4x4",
            "orquestal cinematográfico, cuerdas y percusión, épico",
            "lo-fi suave con piano y vinilo, relajado",
            "épico y grandioso, himno, arreglo con capas y clímax",
            "minimalista, pocos elementos, capas que evolucionan",
        ]
        for texto in variantes:
            with self.subTest(texto=texto):
                self.assertEqual(style_caption(texto), texto)
                self.assertTrue(analyze_prompt(texto)["chips"])

    def test_moods_de_crear_caen_en_regla(self):
        moods = [
            "nocturno y oscuro",
            "tranquilo y relajado, tempo lento",
            "enérgico y potente, driving e imparable",
            "melancólico y nostálgico",
            "cinematográfico, épico, con capas",
            "luminoso y optimista, brillante",
            "épico y grandioso, como un himno",
            "oscuro y tenso",
            "chill relajado y cálido",
        ]
        for texto in moods:
            with self.subTest(texto=texto):
                self.assertEqual(style_caption(texto), texto)
                self.assertTrue(analyze_prompt(texto)["chips"])


class StyleBpmTest(unittest.TestCase):
    """style_bpm: lo pedido manda; si no, el típico del estilo; si no, nada."""

    def test_lo_elegido_manda(self):
        self.assertEqual(style_bpm(PROMPT, requested=140), 140)

    def test_tipico_del_estilo(self):
        self.assertEqual(style_bpm(PROMPT), 180)
        self.assertEqual(style_bpm("drum and bass liquido"), 174)

    def test_sin_regla_no_inventa(self):
        self.assertIsNone(style_bpm("cancion bonita para mi novia"))


class AnalyzePromptTest(unittest.TestCase):
    """analyze_prompt: capas separadas + chips desde el catálogo (sin LM)."""

    def test_capas_separadas(self):
        res = analyze_prompt(f"{PROMPT} con doble bombo a toda velocidad")
        self.assertEqual(res["detected_genre"], "hardcore holandes")
        self.assertEqual(res["suggested_bpm"], 180)
        self.assertIn("Doble bombo", res["modifiers"])

    def test_chip_activo_no_se_sugiere(self):
        """Lo ya escrito se marca activo y deja de sugerirse (no duplica)."""
        res = analyze_prompt(f"{PROMPT} con doble bombo a toda velocidad")
        chip = next(c for c in res["chips"] if c["label"] == "Doble bombo")
        self.assertTrue(chip["active"])
        self.assertFalse(chip["suggested"])

    def test_chip_lleva_su_clausula_en_ingles(self):
        """La UI muestra y añade la cláusula en inglés, no la etiqueta en
        español: ver y enviar tienen que ser el mismo texto."""
        for chip in analyze_prompt(PROMPT)["chips"]:
            with self.subTest(chip=chip["label"]):
                self.assertTrue(chip["clause"], f"«{chip['label']}» sin cláusula")

    def test_chips_dependen_del_genero(self):
        """El set de sugeridos cambia con el género: no es una lista fija."""
        hardcore = {c["label"] for c in analyze_prompt(PROMPT)["chips"] if c["suggested"]}
        jazz = {c["label"] for c in analyze_prompt("jazz suave")["chips"] if c["suggested"]}
        self.assertIn("Doble bombo", hardcore)
        self.assertNotIn("Doble bombo", jazz)

    def test_generico_se_sugiere_siempre(self):
        for prompt in (PROMPT, "jazz suave", "cancion bonita"):
            chips = {c["label"]: c for c in analyze_prompt(prompt)["chips"]}
            self.assertTrue(chips["A toda velocidad"]["suggested"])

    def test_sin_texto_no_hay_activos(self):
        res = analyze_prompt("")
        self.assertIsNone(res["detected_genre"])
        self.assertEqual(res["modifiers"], [])
        self.assertTrue(all(not c["active"] for c in res["chips"]))

    def test_todo_modificador_tiene_datos_de_chip(self):
        """El catálogo es la fuente única: cada fila lleva label/text/suggest.
        suggest_with puede ser vacío a propósito (palabra de refuerzo que no
        se ofrece como chip, como «Sin voz»): lo que no puede es faltar."""
        for mod in STYLE_MODIFIERS:
            self.assertTrue(mod["label"])
            self.assertTrue(mod["text"])
            self.assertIn("suggest_with", mod)
            self.assertIsInstance(mod["suggest_with"], tuple)

    def test_chips_de_voz_marcados_en_dato(self):
        """Los 7 modificadores de voz llevan voice:true y el chip lo expone;
        el resto, False. La UI los oculta en VOZ + BASE NUEVA (base
        instrumental por diseño); "Bater\u00edas protagonistas" no es de voz."""
        info = analyze_prompt("techno")
        voces = {c["label"] for c in info["chips"] if c["voice"]}
        # Los 7 de voz deben estar
        self.assertEqual(len(voces), 7)
        # Y no deben incluir Baterías protagonistas
        for label in voces:
            self.assertNotIn("Bater", label)
        # Los no voz deben incluir Baterías protagonistas
        resto = {c["label"] for c in info["chips"] if not c["voice"]}
        self.assertTrue(any("Bater" in l for l in resto))
        self.assertIn("4x4 (bombo a cada pulso)", resto)


class EnhancePromptTest(unittest.TestCase):
    """Borrador: valores elegidos + descripción ceñida al modelo (B9).

    B9 (2026-10-20, regla del usuario): lo que se añade tiene que ser lo que
    el modelo declara. Género = línea literal de genres_vocab.txt; descripción
    = solo cláusula validada del catálogo. Sin estilo reconocido el texto se
    queda literal, como en B8.
    """

    def test_sin_estilo_no_annade_nada(self):
        for prompt in ("batería suave al fondo", "piano con voz susurrada"):
            with self.subTest(prompt=prompt):
                result = enhance_prompt(prompt)
                self.assertEqual(result["enhanced"], prompt)
                self.assertEqual(result["additions"], [])
                self.assertEqual(result["adaptation"], "literal")

    def test_etiqueta_del_modelo_recibe_su_clausula_validada(self):
        vocab = _vocab_lines()
        for label in ("gabber", "techno", "lofi", "jazz"):
            with self.subTest(label=label):
                result = enhance_prompt(label)
                self.assertEqual(len(result["genres"]), 1)
                estilo = result["genres"][0]
                self.assertIn(estilo["genre"].lower(), vocab)
                clause = CLAUSES[estilo["name"]]
                self.assertEqual(result["enhanced"], f"{label}, {clause}")
                self.assertEqual(result["additions"], [clause])

    def test_clausula_ya_escrita_no_se_duplica(self):
        clause = CLAUSES["hardcore holandes"]
        for prompt in (f"gabber, {clause}", clause.upper()):
            with self.subTest(prompt=prompt[:32]):
                result = enhance_prompt(prompt)
                self.assertEqual(result["enhanced"], prompt)
                self.assertEqual(result["additions"], [])

    def test_negacion_no_annade_el_estilo_negado(self):
        result = enhance_prompt("sin hardcore, relajado")
        self.assertEqual([e["name"] for e in result["genres"]], ["ambient"])
        self.assertNotIn(CLAUSES["hardcore holandes"], result["enhanced"])
        # La exclusión del género no se puede contrastar con las reglas
        # instrumentales: el fallback conserva el texto y omite la receta.
        self.assertEqual(result["enhanced"], "sin hardcore, relajado")
        self.assertTrue(result["warnings"])

    def test_estilo_sin_linea_del_modelo_no_se_annade_y_se_avisa(self):
        # Si el modelo no declara el estilo, no se añade su cláusula (NO FAKE).
        with patch("prompt_enhancer.catalog_styles",
                   return_value=[{"name": "hardcore holandes", "genre": None}]):
            result = enhance_prompt("gabber")
        self.assertEqual(result["enhanced"], "gabber")
        self.assertEqual(result["additions"], [])
        self.assertIsNone(result["genres"][0]["genre"])
        self.assertTrue(any("no es una línea del modelo" in w for w in result["warnings"]))

    def test_varios_estilos_anidan_clausulas_y_avisan(self):
        # La documentación oficial recomienda repetición o evolución temporal;
        # combinar opuestos a ciegas degrada. El aviso lo dice la propia app.
        result = enhance_prompt("gabber y trance")
        self.assertEqual(result["genres"][0]["name"], "hardcore holandes")
        self.assertEqual(result["additions"],
                         [CLAUSES["hardcore holandes"], CLAUSES["trance"]])
        self.assertTrue(any("Varios estilos" in w for w in result["warnings"]))

    def test_bpm_elegido_se_propone_detras_de_la_clausula(self):
        result = enhance_prompt("gabber", bpm=175)
        clause = CLAUSES["hardcore holandes"]
        self.assertEqual(result["enhanced"], f"gabber, {clause}, 175 bpm")
        self.assertEqual(result["additions"], [clause, "175 bpm"])
        self.assertEqual(result["suggested_bpm"], 180)

    def test_bpm_existente_no_se_duplica(self):
        for prompt in ("bateria 120 BPM", "piano a 120bpm", "sesion 120,0 bpm"):
            with self.subTest(prompt=prompt):
                result = enhance_prompt(prompt, bpm=120)
                self.assertEqual(result["enhanced"], prompt)
                self.assertEqual(result["additions"], [])

    def test_bpm_contradictorio_se_declara_y_no_se_impone(self):
        for prompt in ("piano a 130 bpm", "120 bpm al inicio y 130 bpm al final"):
            with self.subTest(prompt=prompt):
                result = enhance_prompt(prompt, bpm=120)
                self.assertEqual(result["enhanced"], prompt)
                self.assertTrue(result["warnings"])
                self.assertEqual(result["additions"], [])

    def test_texto_largo_se_conserva_y_no_se_amplia(self):
        prompt = "techno " + "detalle " * 110
        result = enhance_prompt(prompt, bpm=120)
        self.assertEqual(result["enhanced"], prompt.strip())
        self.assertEqual(result["additions"], [])
        self.assertTrue(result["warnings"])

    def test_borrador_preserva_restricciones_al_annadir_bpm(self):
        prompt = "bajo potente, sin voz; batería suave al fondo"
        result = enhance_prompt(prompt, bpm=120)
        self.assertEqual(style_caption(result["enhanced"]), f"{prompt}, 120 bpm")

    def test_prompt_vacio_se_rechaza(self):
        with self.assertRaises(ValueError):
            enhance_prompt(" ")

    def test_descripciones_no_contradicen_restricciones(self):
        for prompt in ("gabber sin bombo", "trance sin bajo", "ambient con bateria",
                       "techno nada de bombo", "techno no añadir bombo",
                       "trance sin batería, ni bajo"):
            with self.subTest(prompt=prompt):
                result = enhance_prompt(prompt)
                self.assertEqual(result["enhanced"], prompt)
                self.assertEqual(result["additions"], [])
                self.assertTrue(result["warnings"])

    def test_no_quiero_estilo_no_lo_activa(self):
        result = enhance_prompt("no quiero techno")
        self.assertEqual(result["genres"], [])
        self.assertEqual(result["enhanced"], "no quiero techno")

    def test_prosa_derivada_no_activa_generos_en_segunda_pasada(self):
        for prompt in ("techno", "synthwave", "gabber y trance"):
            with self.subTest(prompt=prompt):
                first = enhance_prompt(prompt)
                second = enhance_prompt(first["enhanced"])
                self.assertEqual(second["enhanced"], first["enhanced"])
                self.assertEqual(second["genres"], first["genres"])
                self.assertEqual(second["additions"], [])

    def test_clausula_con_espacios_distintos_no_duplica(self):
        clause = CLAUSES["techno"]
        prompt = "techno, " + clause.replace(" ", "  \n")
        self.assertEqual(enhance_prompt(prompt)["enhanced"], prompt)


class StructuredPromptTest(unittest.TestCase):
    def test_pista_de_idioma_solo_exclusiones_es_completas_conocidas(self):
        for text in ("sin bombo", "sin bajo", "nada de voz", "sin voz y sin guitarras"):
            with self.subTest(text=text):
                self.assertTrue(known_spanish_exclusion_details(text))
        for text in ("no drums", "without bass", "warm drums, sin bajo", "sin bajo potente",
                     "sin meditación", "sin voz ni meditación", "sin bombo; warm synths"):
            with self.subTest(text=text):
                self.assertFalse(known_spanish_exclusion_details(text))

    def test_traduccion_solo_compone_y_no_reemplaza_validacion_original(self):
        raw = "sin bajo"
        result = enhance_prompt(raw, main_style="trance", details_for_engine="no bass")
        self.assertEqual(result["original"], raw)
        self.assertIn("no bass", result["enhanced"])
        self.assertNotIn(raw, result["enhanced"])
        self.assertNotIn(CLAUSES["trance"], result["enhanced"])
        self.assertTrue(result["warnings"])
        self.assertEqual(enhance_prompt(raw, main_style="trance", details_for_engine="no bass"), result)
        with self.assertRaises(ValueError):
            enhance_prompt("sin techno", main_style="techno", details_for_engine="different text")
        with self.assertRaises(ValueError):
            enhance_prompt("sin voz", main_style="techno", details_for_engine="")

    def test_exclusiones_no_contrastables_omiten_receta_completa(self):
        for details in ("sin meditación", "nada de energía oscura", "sin voz ni meditación",
                        "sin voz y sin meditación"):
            with self.subTest(details=details):
                result = enhance_prompt(details, main_style="ambient")
                self.assertIn(details, result["enhanced"])
                self.assertIn("Predominantly ambient", result["enhanced"])
                self.assertEqual(len(result["additions"]), 1)
                self.assertNotIn(CLAUSES["ambient"], result["enhanced"])
                self.assertTrue(any("no se pueden contrastar" in warning for warning in result["warnings"]))
                legacy = enhance_prompt(f"ambient {details}")
                self.assertEqual(legacy["enhanced"], f"ambient {details}")

    def test_exclusiones_instrumentales_completas_compatibles_permiten_ayuda(self):
        for details in ("sin voz", "sin guitarras", "sin voz ni guitarras",
                        "sin voz y sin guitarras", "without vocals and without guitars"):
            for style in ("ambient", "techno"):
                with self.subTest(details=details, style=style):
                    result = enhance_prompt(details, main_style=style)
                    self.assertIn(CLAUSES[style], result["enhanced"])
                    self.assertFalse(result["warnings"])

    def test_seleccion_negada_se_rechaza_sin_sustituir(self):
        for details, kwargs in (("sin techno", {"main_style": "techno"}),
                                ("no quiero trance", {"main_style": "techno", "influence_styles": ["trance"]})):
            with self.subTest(details=details), self.assertRaises(ValueError):
                enhance_prompt(details, **kwargs)

    def test_excluir_estilo_vecino_no_rechaza_principal_literal(self):
        for style, details in (("funk", "sin disco"), ("ambient", "sin meditación")):
            with self.subTest(style=style):
                result = enhance_prompt(details, main_style=style)
                self.assertIn(f"Predominantly {style}", result["enhanced"])
                self.assertIn(details, result["enhanced"])
                self.assertEqual(result["selection"]["main_style"], style)

    def test_negaciones_instrumentales_en_datos(self):
        for details in ("nada de bombo", "no añadir bombo", "sin batería, ni bajo"):
            with self.subTest(details=details):
                result = enhance_prompt(details, main_style="techno")
                self.assertEqual(len(result["additions"]), 1)
                self.assertNotIn(CLAUSES["techno"], result["enhanced"])

    def test_principal_y_matices_sin_asignar_instrumentos_a_matices(self):
        result = enhance_prompt("sin voz; batería al fondo", main_style="gabber",
                                influence_styles=["trance", "jazz"])
        self.assertIn("Predominantly gabber", result["enhanced"])
        self.assertIn("subtle influences of trance, jazz", result["enhanced"])
        self.assertIn("sin voz; batería al fondo", result["enhanced"])
        self.assertIn(CLAUSES["hardcore holandes"], result["enhanced"])
        self.assertNotIn(CLAUSES["trance"], result["enhanced"])
        self.assertNotIn(CLAUSES["jazz"], result["enhanced"])
        self.assertNotIn("bpm", result["enhanced"])
        self.assertEqual(result["selection"]["main_style"], "gabber")
        self.assertEqual(result["original"], "sin voz; batería al fondo")

    def test_estilo_solo_permite_texto_vacio(self):
        result = enhance_prompt("", main_style="techno")
        self.assertIn("techno", result["enhanced"])
        self.assertIn(CLAUSES["techno"], result["enhanced"])

    def test_validacion_no_sustituye_etiquetas(self):
        for args in ({"main_style": "estilo inventado zzz"},
                     {"main_style": "techno", "influence_styles": ["estilo inventado zzz"]},
                     {"influence_styles": ["trance"]}):
            with self.subTest(args=args), self.assertRaises(ValueError):
                enhance_prompt("detalle", **args)

    def test_etiqueta_valida_sin_ficha_conserva_nombre_y_avisa(self):
        result = enhance_prompt("", main_style="acid jazz")
        self.assertIn("acid jazz", result["enhanced"])
        self.assertNotIn(CLAUSES["jazz"], result["enhanced"])
        self.assertTrue(result["warnings"])

    def test_exclusiones_impiden_descripcion_pero_conservan_roles(self):
        for style, details in (("gabber", "sin bombo"), ("trance", "sin bajo"),
                               ("ambient", "con bateria")):
            with self.subTest(style=style):
                result = enhance_prompt(details, main_style=style)
                self.assertIn(style, result["enhanced"])
                self.assertIn(details, result["enhanced"])
                self.assertEqual(len(result["additions"]), 1)
                self.assertTrue(result["warnings"])

    def test_quitar_ayuda_conserva_principal_matices_y_texto(self):
        result = enhance_prompt("sin voz", main_style="techno", influence_styles=["trance"],
                                include_descriptions=False)
        self.assertIn("Predominantly techno", result["enhanced"])
        self.assertIn("trance", result["enhanced"])
        self.assertIn("sin voz", result["enhanced"])
        self.assertNotIn(CLAUSES["techno"], result["enhanced"])

    def test_preparacion_estable_sin_reanalizar_detalles_como_selecciones(self):
        kwargs = {"main_style": "techno", "influence_styles": ["synthwave"]}
        result = enhance_prompt("cinematic, sin voz", **kwargs)
        self.assertEqual(enhance_prompt("cinematic, sin voz", **kwargs), result)
        second = enhance_prompt(result["enhanced"], **kwargs)
        self.assertEqual(second["enhanced"], result["enhanced"])
        self.assertEqual(second["selection"], result["selection"])
        self.assertEqual([entry["genre"] for entry in result["genres"]], ["techno", "synthwave"])


if __name__ == "__main__":
    unittest.main()
