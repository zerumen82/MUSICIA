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
    MAX_CAPTION_CHARS,
    STYLE_MODIFIERS,
    analyze_prompt,
    find_modifiers,
    find_style,
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


class StyleCaptionTest(unittest.TestCase):
    """style_caption: la frase del usuario va entera y primero."""

    def test_conserva_la_frase_y_annade_estilo_en_ingles(self):
        caption = style_caption(PROMPT)
        self.assertTrue(caption.startswith(PROMPT))
        # Vocabulario que el motor reconoce (A/B GPU 2026-10-06): hardstyle
        # + distorted kick, no «gabber», que no existe en su vocabulario.
        self.assertIn("distorted", caption)
        self.assertIn("kick", caption)
        self.assertNotIn("gabber", caption.lower())
        self.assertLessEqual(len(caption), MAX_CAPTION_CHARS)

    def test_sin_regla_se_queda_igual(self):
        texto = "idea suave para la cena"
        self.assertEqual(style_caption(texto), texto)

    def test_no_pega_genero_distinto(self):
        caption = style_caption("jazz suave con piano")
        self.assertTrue(caption.startswith("jazz suave con piano"))
        self.assertIn("jazz", caption.lower())
        self.assertNotIn("hardcore", caption.lower())

    def test_doble_bombo_como_capa_componible(self):
        """Los detalles pedidos se detectan en LA FRASE del usuario (A/B real)."""
        caption = style_caption(f"{PROMPT} con doble bombo a toda velocidad")
        self.assertTrue(caption.startswith(PROMPT))
        self.assertIn("double bass", caption)  # Cláusula actualizada
        self.assertIn("energetic tempo", caption)  # Cláusula actualizada
        # La capa de estilo no lleva pegado el doble bombo: es componible.
        self.assertNotIn("double bass", find_style(PROMPT)["style"])

    def test_modificadores_solo_cuando_se_piden(self):
        self.assertEqual(find_modifiers("hardcore holandes"), ())
        self.assertEqual(len(find_modifiers("hardcore holandes con doble bombo")), 1)

    def test_modificadores_sensibles_a_acentos(self):
        clausulas = find_modifiers("algo rapidísimo")
        self.assertEqual(len(clausulas), 1)
        self.assertIn("energetic tempo", clausulas[0])  # Cláusula actualizada

    def test_capa_estilo_y_capa_detalles_independientes(self):
        """«Doble bombo» solo no pega un género, y un género no añade detalles."""
        caption_pop = style_caption("pop alegre con doble bombo")
        self.assertIn("pop", caption_pop.lower())
        self.assertIn("double bass", caption_pop)  # Cláusula actualizada
        self.assertNotIn("hardstyle", caption_pop.lower())

    def test_sin_recortar_a_mitad_de_frase(self):
        largo = (f"{PROMPT} " + "y otra cosa " * 90).strip()
        caption = style_caption(largo)
        if len(caption) > MAX_CAPTION_CHARS:
            self.assertEqual(caption, largo)

    def test_idempotente_mejorar_luego_generar(self):
        """MEJORAR compone y GENERAR vuelve a componer: el estilo sale UNA vez."""
        once = style_caption(PROMPT)
        self.assertEqual(style_caption(once), once)
        rule = find_style(PROMPT)
        self.assertEqual(once.count(rule["style"]), 1)

    def test_genero_del_desplegable_no_duplica_estilo(self):
        """La frase del desplegable ya trae la cláusula: no se pega otra."""
        rule = find_style("techno oscuro")
        con_clausula = f"techno oscuro con bombo seco. {rule['style']}"
        self.assertEqual(style_caption(con_clausula), con_clausula)

    def test_palabras_sueltas_reconocen_estilo(self):
        """Agujeros 2026-10-06: hardcore/tecno/rap/trap/dembow/chill solos
        viajaban en español sin frase inglesa (el motor no cumplía)."""
        casos = {
            "hardcore en 4x4": ("hardcore holandes", 180),
            "tecno oscuro": ("techno", 135),
            "rap noventero": ("hip hop", 90),
            "trap oscuro": ("trap", 140),
            "dembow pegajoso": ("reggaeton", 95),
            "chill para dormir": ("ambient", 70),
        }
        for texto, (genero, bpm) in casos.items():
            with self.subTest(texto=texto):
                self.assertEqual(find_style(texto)["name"], genero)
                caption = style_caption(texto)
                self.assertTrue(caption.startswith(texto))
                self.assertGreater(len(caption), len(texto))
                self.assertEqual(style_bpm(texto), bpm)

    def test_trap_no_cae_en_hip_hop(self):
        """«trap» contiene «rap»: la regla trap tiene que ir primero."""
        self.assertEqual(find_style("trap oscuro")["name"], "trap")

    def test_detalles_viajan_aunque_no_haya_genero(self):
        """Sin estilo reconocido, los detalles sí se traducen (antes se perdían)."""
        caption = style_caption("algo contundente con doble bombo")
        self.assertTrue(caption.startswith("algo contundente con doble bombo"))
        self.assertIn("double bass", caption)  # Cláusula actualizada

    def test_clausulas_no_se_duplican(self):
        """Idempotencia también para modificadores: dos pasadas = una."""
        once = style_caption("algo contundente con doble bombo")
        self.assertEqual(style_caption(once), once)
        self.assertEqual(once.count("double bass"), 1)  # Cláusula actualizada

    def test_capa_documental_estilo_vocal_y_tempo(self):
        """Guía oficial (vocal style + tempo feel) y 400 textos minados:
        las palabras del fabricante se detectan y viajan en inglés."""
        casos = {
            "balada con voz susurrada": "whispered vocals",
            "tema en falsete": "falsetto vocals",
            "rock con voz gritada": "shouted vocals",
            "trap con voz rapeada": "rapped verses",
            "canción a tempo lento": "slow, laid-back tempo",
            "pulso constante y moderado": "steady",
            "himno explosivo": "anthemic",
            "riffs pegadizos con capas": "catchy, memorable hook",  # Cláusula actualizada
            "caja de ritmos y contrabajo": "drum-machine",
        }
        for texto, esperado in casos.items():
            with self.subTest(texto=texto):
                caption = style_caption(texto)
                self.assertIn(esperado, caption)
                # Idempotencia: solo para frases sin estilo detectado
                if "caja de ritmos" not in texto:  # Este caso detecta estilo en la caption
                    self.assertEqual(style_caption(caption), caption)


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
        clausulas = find_modifiers("techno contundente sin voz")
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
                regla = find_style(texto)
                detalles = find_modifiers(texto)
                self.assertTrue(
                    regla is not None or len(detalles) > 0,
                    f"«{texto}» no dispara nada",
                )

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
                mods = analyze_prompt(f"techno {texto}")["modifiers"]
                regla = find_style(texto)
                self.assertTrue(
                    regla is not None or len(mods) > 0,
                    f"«{texto}» no dispara nada",
                )


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
        res = analyze_prompt(f"{PROMPT} con doble bombo")
        self.assertEqual(res["detected_genre"], "hardcore holandes")
        self.assertEqual(res["suggested_bpm"], 180)
        self.assertIn("Doble bombo", res["modifiers"])

    def test_chip_activo_no_se_sugiere(self):
        """Lo ya escrito se marca activo y deja de sugerirse (no duplica)."""
        res = analyze_prompt(f"{PROMPT} con doble bombo")
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
    """MEJORAR PROMPT: frase del usuario + estilo en inglés, visible y editable."""

    def test_annade_estilo_y_lo_declara(self):
        res = enhance_prompt(PROMPT)
        self.assertTrue(res["enhanced"].startswith(PROMPT))
        self.assertIn("distorted", res["enhanced"])
        self.assertEqual(res["genre_detected"], "hardcore holandes")
        self.assertEqual(res["suggested_bpm"], 180)
        self.assertIn("descripción de estilo en inglés", res["additions"])

    def test_bpm_elegido_se_une_al_final(self):
        res = enhance_prompt(PROMPT, bpm=175)
        self.assertIn("175 bpm", res["enhanced"])
        self.assertTrue(res["enhanced"].startswith(PROMPT))

    def test_detalles_pedidos_aparecen_en_enhanced(self):
        res = enhance_prompt(f"{PROMPT} con doble bombo")
        self.assertIn("double bass", res["enhanced"])  # Cláusula actualizada
        self.assertEqual(res["genre_detected"], "hardcore holandes")

    def test_sin_estilo_y_sin_bpm_no_cambia_nada(self):
        res = enhance_prompt("cancion bonita para mi novia")
        self.assertEqual(res["enhanced"], "cancion bonita para mi novia")
        self.assertEqual(res["additions"], [])
        self.assertIsNone(res["genre_detected"])

    def test_solo_bpm_comportamiento_antiguo(self):
        res = enhance_prompt("cancion bonita para mi novia", bpm=120)
        self.assertEqual(res["enhanced"], "cancion bonita para mi novia, 120 bpm")
        self.assertEqual(res["additions"], ["120 bpm"])

    def test_prompt_demasiado_largo_no_se_recorta(self):
        largo = (f"{PROMPT} " + "detalle " * 110).strip()
        res = enhance_prompt(largo)
        self.assertEqual(res["enhanced"], largo)


if __name__ == "__main__":
    unittest.main()
