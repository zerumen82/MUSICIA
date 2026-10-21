"""Prompt literal y catálogo de sugerencias voluntarias.

CREAR y REMIX comparten style_caption: conserva el texto completo sin
inferir arreglos, protagonismo, carácter ni traducciones parciales.
La detección del catálogo solo organiza sugerencias; no cambia el envío
ni equivale a comprensión semántica del modelo.
"""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

# Catálogo de sugerencias fuera del código. Las claves completas o regex
# permiten buscar entradas; nunca autorizan una expansión del caption.
_CATALOG = json.loads((Path(__file__).resolve().parent / "style_catalog.json").read_text(encoding="utf-8"))


def _freeze(rule: dict) -> dict:
    """El JSON no tiene tuplas: se normalizan al cargar (el código espera tuplas)."""
    frozen = dict(rule)
    for field in ("keys", "suggest_with"):
        if field in frozen and isinstance(frozen[field], list):
            frozen[field] = tuple(frozen[field])
    return frozen


STYLE_RULES: tuple[dict, ...] = tuple(_freeze(r) for r in _CATALOG["styles"])
STYLE_MODIFIERS: tuple[dict, ...] = tuple(_freeze(m) for m in _CATALOG["modifiers"])
_NEGATION_BEFORE = re.compile(_CATALOG["matching"]["negation_before"])
_NEGATION_OBJECTS = re.compile(_CATALOG["matching"]["negation_objects"])
_NEGATION_OBJECT_SEPARATOR = re.compile(_CATALOG["matching"]["negation_object_separator"])
_NEGATION_OBJECT_ARTICLE = re.compile(_CATALOG["matching"]["negation_object_article"])
_STRUCTURED_SPANISH_EXCLUSION_PREFIX = re.compile(_CATALOG["matching"]["structured_spanish_exclusion_prefix"])
_STRUCTURED_EXCLUSION_REMAINDER = re.compile(_CATALOG["matching"]["structured_exclusion_remainder"])
_CAPTION_EXCLUSIONS = _CATALOG["caption_exclusions"]
PROMPT_PREPARATION = _CATALOG["preparation"]
STRUCTURED_DETAILS_SOURCE_LANGUAGE = _CATALOG["matching"]["structured_exclusion_source_language"]

# Mínimo existente para buscar sugerencias; no limita el caption literal.
MIN_LENGTH = 3


def _key_matches(key: str, text: str):
    """Ocurrencias completas; los prefijos lingüísticos se declaran como regex."""
    pattern = key[3:] if key.startswith("re:") else rf"(?<!\w){re.escape(key)}(?!\w)"
    return re.finditer(pattern, text)


def _is_negated(text: str, start: int) -> bool:
    return _NEGATION_BEFORE.search(text[:start]) is not None


def _key_hit(key: str, text: str, *, negated: bool = False) -> bool:
    return any(_is_negated(text, match.start()) == negated for match in _key_matches(key, text))

def _plain(text: str) -> str:
    """Minúsculas y sin acentos, para comparar sin falsos negativos."""
    decomposed = unicodedata.normalize("NFD", text or "")
    return decomposed.encode("ascii", "ignore").decode("ascii").lower()


def _clause_pattern(clause: str) -> str:
    """Cláusula literal con cualquier espaciado, sin buscar palabras sueltas."""
    return r"\s+".join(re.escape(word) for word in clause.split())


def without_catalog_descriptions(prompt: str) -> str:
    """Vista para detección, nunca texto de salida: ignora prosa derivada.

    Las descripciones completas de estilos y chips no son elecciones nuevas.
    Se conserva el prompt original, incluso cuando contenía esa misma frase.
    """
    text = _plain(prompt)
    for rule in (*STYLE_RULES, *STYLE_MODIFIERS):
        clause = rule.get("style", rule.get("clause", ""))
        if clause:
            text = re.sub(_clause_pattern(_plain(clause)), " ", text)
    return text


def selected_style_rule(label: str) -> dict | None:
    """Ficha exacta de una etiqueta: no hereda recetas de una subfrase."""
    text = _plain(label).strip()
    for rule in STYLE_RULES:
        if text == _plain(rule["name"]):
            return rule
        for key in rule["keys"]:
            if (key.startswith("re:") and re.fullmatch(key[3:], text)) or text == key:
                return rule
    return None


def selected_style_negated(label: str, prompt: str) -> bool:
    """Detecta una selección explícitamente excluida en el texto propio."""
    source = without_catalog_descriptions(prompt)
    # Las claves de detección agrupan estilos distintos (funk/disco): no son
    # equivalencias autorizadas para rechazar una elección literal.
    return _key_hit(_plain(label), source, negated=True)


def has_unchecked_exclusions(prompt: str) -> bool:
    """True si una exclusión completa no es contrastable con el catálogo.

    No atribuye significado a objetos desconocidos. Una coincidencia parcial
    como «voz» dentro de «voz ni meditación» no acredita la cláusula entera.
    Ante esa incertidumbre el preparador conserva roles/detalles y omite la
    descripción automática completa.
    """
    source = without_catalog_descriptions(prompt)
    for match in _NEGATION_OBJECTS.finditer(source):
        for fragment in _NEGATION_OBJECT_SEPARATOR.split(match.group(1)):
            fragment = _NEGATION_OBJECT_ARTICLE.sub("", fragment.strip())
            known = any(
                re.fullmatch(key[3:] if key.startswith("re:") else re.escape(key), fragment)
                for constraint in _CAPTION_EXCLUSIONS
                for key in constraint["keys"]
            )
            if not known:
                return True
    return False


def known_spanish_exclusion_details(prompt: str) -> bool:
    """Pista ES solo para detalles enteramente hechos de exclusiones conocidas.

    No identifica idiomas por una palabra instrumental ni cambia la frase.
    El marcador español inequívoco y los objetos completos del catálogo
    permiten pedir traducción real cuando el detector estadístico se abstiene.
    """
    source = _plain(prompt).strip()
    return bool(
        _STRUCTURED_SPANISH_EXCLUSION_PREFIX.match(source)
        and not has_unchecked_exclusions(source)
        and _STRUCTURED_EXCLUSION_REMAINDER.fullmatch(_NEGATION_OBJECTS.sub("", source))
    )


def find_styles(prompt: str) -> tuple[dict, ...]:
    """Todas las reglas de estilo cuyas claves aparecen en el prompt.

    En orden de catálogo (específico antes que genérico) y sin duplicados
    por nombre. Antes solo viajaba la primera (el 2º y 3er estilo que el
    usuario añadía se ignoraban en silencio: bug 2026-10-10).
    """
    text = without_catalog_descriptions((prompt or "").strip())
    if len(text) < MIN_LENGTH:
        return ()
    # Una frase específica (también negada) cubre las coincidencias genéricas
    # de dentro: «sin hard techno» no pide techno por contener esa palabra.
    matches = [
        (match.start(), match.end(), index)
        for index, rule in enumerate(STYLE_RULES)
        for key in rule["keys"]
        for match in _key_matches(key, text)
    ]
    covered = []
    selected = set()
    for start, end, index in sorted(matches, key=lambda m: (-(m[1] - m[0]), m[2], m[0])):
        if any(left <= start and end <= right for left, right in covered):
            continue
        covered.append((start, end))
        if not _is_negated(text, start):
            selected.add(index)
    return tuple(rule for index, rule in enumerate(STYLE_RULES) if index in selected)


def caption_conflicts(caption: str, original: str) -> bool:
    """Filtra sugerencias que contradigan exclusiones reconocidas del catálogo.

    Se comparte entre las sugerencias y la preparación para no añadir una
    descripción incompatible. No interpreta toda la intención musical.
    """
    source, description = _plain(original), _plain(caption)
    for constraint in _CAPTION_EXCLUSIONS:
        excluded = any(_key_hit(key, source, negated=True) for key in constraint["keys"])
        requested = any(_key_hit(key, source) for key in constraint["keys"])
        present = any(_key_hit(key, description) for key in constraint["caption_keys"])
        absent = any(_key_hit(key, description, negated=True) for key in constraint["caption_keys"])
        if (excluded and present) or (requested and absent):
            return True
    return False


def find_style(prompt: str) -> dict | None:
    """Primera regla de estilo (compat: BPM, género principal, chips)."""
    styles = find_styles(prompt)
    return styles[0] if styles else None


def clause_present(clause: str, text: str) -> bool:
    """True si la cláusula completa ya está escrita en el texto (comparación llana).

    Sirve para no duplicar una cláusula de catálogo que la persona ya tenía
    escrita. Compara sin acentos ni mayúsculas y colapsando espacios.
    """
    needle = " ".join(_plain(clause or "").split())
    return bool(needle) and needle in " ".join(_plain(text or "").split())


def _modifier_selected(mod: dict, text: str) -> bool:
    """Solo una cláusula o frase completa puede marcar su chip como elegido.

    Una palabra de búsqueda como «batería» o «potente» no demuestra que
    el usuario haya pedido batería protagonista o una voz potente.
    """
    return any(_key_hit(_plain(mod[field]), text) for field in ("clause", "text"))


def find_modifiers(prompt: str) -> tuple[str, ...]:
    """Cláusulas de catálogo escritas completas; no interpreta palabras sueltas."""
    text = _plain((prompt or "").strip())
    return tuple(mod["clause"] for mod in STYLE_MODIFIERS if _modifier_selected(mod, text))


def analyze_prompt(prompt: str) -> dict:
    """Entradas de catálogo para sugerencias, separadas del caption efectivo.

    El endpoint /music/style_options devuelve coincidencias de búsqueda y
    frases completas ya escritas; no certifica interpretación semántica.
    """
    original = (prompt or "").strip()
    text = _plain(original)
    rules = find_styles(original)
    detected = rules[0]["name"] if rules else None
    detected_all = [r["name"] for r in rules]
    chips = []
    for mod in STYLE_MODIFIERS:
        already = _modifier_selected(mod, text)
        suggested = not already and (
            "*" in mod["suggest_with"] or any(d in mod["suggest_with"] for d in detected_all)
        ) and not caption_conflicts(mod["clause"], original)
        chips.append({
            "label": mod["label"],
            "text": mod["text"],
            # Inglés literal de la cláusula: es lo que viaja al motor y lo
            # que la UI muestra, para que ver y enviar sean lo mismo.
            "clause": mod["clause"],
            "active": already,
            "suggested": suggested,
            # La UI oculta los de voz donde la base es instrumental
            # (VOZ + BASE NUEVA): el dato manda, no una lista en el frontend.
            "voice": bool(mod.get("voice", False)),
        })
    return {
        "detected_genre": detected,
        "detected_genres": detected_all,
        "suggested_bpm": style_bpm(original),
        "modifiers": [
            mod["label"]
            for mod in STYLE_MODIFIERS
            if _modifier_selected(mod, text)
        ],
        "chips": chips,
    }


def style_caption(prompt: str) -> str:
    """Texto del cuadro, solo sin espacios externos.

    No traduce. El inglés que viaja al motor lo decide style_for_engine,
    y esa misma frase es la que se muestra antes de enviar.
    """
    return (prompt or "").strip()


def style_bpm(prompt: str, requested: float | None = None) -> int | None:
    """BPM de las metas: lo pedido manda; si no, el típico del estilo."""
    if requested:
        return int(round(float(requested)))
    rule = find_style(prompt)
    if rule is None:
        return None
    return rule["bpm"]
