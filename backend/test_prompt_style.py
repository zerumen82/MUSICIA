"""Caption de estilo y MEJORAR PROMPT, sin GPU ni red.

Se ejecuta con el venv del backend:
    backend\\venv\\Scripts\\python.exe -m unittest backend.test_prompt_style -v
"""

import sys
import unittest
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from prompt_enhancer import enhance_prompt  # noqa: E402
from prompt_style import (  # noqa: E402
    STYLE_MODIFIERS,
    analyze_prompt,
    find_modifiers,
    find_style,
    find_styles,
    style_bpm,
    style_caption,
)

PROMPT = "baterias techno hardcore holandés"


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
    """Borrador optativo: solo valores elegidos, sin reglas creativas."""

    def test_genero_no_annade_caracter_instrumentos_o_ritmo(self):
        for prompt in (PROMPT, "techno", "electrónica", "batería suave al fondo", "jazz con contrabajo"):
            with self.subTest(prompt=prompt):
                result = enhance_prompt(prompt)
                self.assertEqual(result["enhanced"], prompt)
                self.assertEqual(result["additions"], [])
                self.assertEqual(result["adaptation"], "literal")

    def test_bpm_elegido_se_propone_sin_preset_de_genero(self):
        result = enhance_prompt(PROMPT, bpm=175)
        self.assertEqual(result["enhanced"], f"{PROMPT}, 175 bpm")
        self.assertEqual(result["additions"], ["175 bpm"])
        self.assertEqual(result["suggested_bpm"], 180)

    def test_bpm_existente_no_se_duplica(self):
        for prompt in ("techno 120 BPM", "techno a 120bpm", "techno 120,0 bpm"):
            with self.subTest(prompt=prompt):
                result = enhance_prompt(prompt, bpm=120)
                self.assertEqual(result["enhanced"], prompt)
                self.assertEqual(result["additions"], [])

    def test_bpm_contradictorio_se_declara_y_no_se_impone(self):
        for prompt in ("techno a 130 bpm", "120 bpm al inicio y 130 bpm al final"):
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


if __name__ == "__main__":
    unittest.main()
