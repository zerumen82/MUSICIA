"""Preparación local de estilos explícitos y detalles propios (B9b).

Expresa principal y matices mediante plantillas de configuración; las etiquetas
deben existir enteras en el vocabulario, que no acredita fidelidad audible.
Añade solo descripciones existentes compatibles y declara cada añadido. La
ruta heredada conserva detección local y BPM explícito sin traducir el texto.
"""

from __future__ import annotations

import re

from genre_glossary import catalog_styles, glossary_line
from prompt_style import (
    PROMPT_PREPARATION, caption_conflicts, clause_present, find_styles, has_unchecked_exclusions,
    selected_style_negated, selected_style_rule, without_catalog_descriptions,
)

MIN_LENGTH = PROMPT_PREPARATION["min_length"]
MAX_PROMPT_CHARS = PROMPT_PREPARATION["max_prompt_chars"]

# Textos históricos de sugerencia optativa; no intervienen en el caption
# efectivo. La ruta que los presenta debe declarar que son un borrador y
# nunca aplicar estas decisiones musicales automáticamente.
REMIX_BASES: dict[str, str] = {
    "musica": "an instrumental piece inspired by a reference track",
    "voz": "soft musical backing for a lead vocal",
    "mixta": "a new take on a track with music and vocals, same spirit",
    "otro": "sound texture inspired by an ambient reference",
}
REMIX_BASS_STRONG = "strong bass"
REMIX_BASS_BALANCED = "balanced bright mix"
REMIX_DYN_STEADY = "steady smooth texture"
REMIX_DYN_EXPRESSIVE = "expressive dynamics"
REMIX_PAUSES = "with quiet breaks"


def _model_genres(rules) -> list[dict]:
    """Género literal del modelo por cada estilo reconocido (B9).

    `genre` solo existe cuando alguna clave del estilo es línea literal de
    `genres_vocab.txt`, la whitelist con la que el motor escribe géneros.
    `None` significa que el modelo no declara ese estilo: por B9 no se añade
    su cláusula y se avisa (NO FAKE: aquí no se inventa ninguna forma).
    """
    declared = {row["name"]: row.get("genre") for row in catalog_styles()}
    return [
        {"name": rule["name"], "genre": declared.get(rule["name"]), "clause": rule.get("style", "")}
        for rule in rules
    ]


def _selection(main_style: str | None, influence_styles: list[str] | None) -> tuple[str | None, list[str]]:
    """Valida etiquetas enteras; nunca cambia un estilo por otro vecino."""
    main = main_style.strip() if main_style is not None else None
    if main_style is not None and not main:
        raise ValueError("Selecciona un estilo principal válido o deja el campo vacío.")
    influences = [label.strip() for label in (influence_styles or [])]
    if influences and not main:
        raise ValueError("Elige un estilo principal antes de añadir matices.")
    for label in ([main] if main else []) + influences:
        if not glossary_line(label):
            raise ValueError(f"El estilo «{label}» no es una línea del vocabulario del modelo.")
    normalized = [" ".join(label.lower().split()) for label in ([main] if main else []) + influences]
    if len(normalized) != len(set(normalized)):
        raise ValueError("Cada estilo debe tener un único papel: principal o matiz.")
    return main, influences


def enhance_prompt(
    prompt: str,
    bpm: int | None = None,
    *,
    main_style: str | None = None,
    influence_styles: list[str] | None = None,
    include_descriptions: bool = True,
    details_for_engine: str | None = None,
) -> dict:
    """Prepara principal/matices y detalles; preserva el contrato literal legado.

    Las selecciones estructuradas no se extraen de los detalles ni de la prosa
    que produce esta función. Si se facilita traducción de los detalles, solo
    se usa al componer: las restricciones se contrastan con el original.
    La ruta antigua conserva detección y BPM optativo.
    """
    original = (prompt or "").strip()
    main, influences = _selection(main_style, influence_styles)
    for label in ([main] if main else []) + influences:
        if selected_style_negated(label, original):
            raise ValueError(f"El estilo seleccionado «{label}» está excluido en tus detalles; revisa la selección o el texto.")
    if not main and len(original) < MIN_LENGTH:
        raise ValueError(f"El prompt necesita al menos {MIN_LENGTH} caracteres")

    additions: list[str] = []
    warnings: list[str] = []
    enhanced = details_for_engine.strip() if main and details_for_engine is not None else original
    if original and main and not enhanced:
        raise ValueError("La traducción de los detalles está vacía; no se prepara el prompt sin tus instrucciones.")
    if main:
        template = PROMPT_PREPARATION["influences_template" if influences else "main_template"]
        role = template.format(main_style=main,
                               influence_styles=PROMPT_PREPARATION["influence_separator"].join(influences))
        if not clause_present(role, enhanced):
            enhanced = PROMPT_PREPARATION["detail_separator"].join(part for part in (role, enhanced) if part)
            additions.append(role)
        genres = []
        rules = []
        for label in [main, *influences]:
            rule = selected_style_rule(label)
            genres.append({"name": label, "genre": label, "clause": rule["style"] if rule else ""})
            if rule:
                rules.append(rule)
            else:
                warnings.append(f"El estilo «{label}» no tiene descripción de catálogo: se conserva su etiqueta literal.")
        # Un matiz no autoriza a introducir sus instrumentos o su arreglo.
        descriptions = genres[:1]
        if len(enhanced) > MAX_PROMPT_CHARS:
            warnings.append("El prompt preparado supera el límite de la ayuda; se conservan los estilos y todos tus detalles.")
    else:
        rules = find_styles(original)
        genres = _model_genres(rules)
        descriptions = genres

    source = without_catalog_descriptions(original)
    for entry in descriptions if include_descriptions else []:
        clause, literal = entry["clause"], entry["genre"]
        if literal is None:
            warnings.append(
                f"El estilo «{entry['name']}» no es una línea del modelo: no se añade su descripción.")
            continue
        if not clause or clause_present(clause, enhanced):
            continue
        if has_unchecked_exclusions(source):
            warnings.append(f"No se añade la descripción de «{entry['name']}»: no se pueden contrastar todas tus exclusiones con el catálogo.")
            continue
        if caption_conflicts(clause, source):
            warnings.append(f"No se añade la descripción de «{entry['name']}»: contradice tus instrucciones.")
            continue
        candidate = enhanced + PROMPT_PREPARATION["description_separator"] + clause
        if len(candidate) <= MAX_PROMPT_CHARS:
            enhanced = candidate
            additions.append(clause)
        else:
            warnings.append(
                "No se añade la descripción del estilo: el borrador excedería el límite de caracteres.")
    if not main and len(genres) > 1:
        names = ", ".join(entry["name"] for entry in genres)
        warnings.append(
            f"Varios estilos en el texto ({names}): el modelo avisa de combinar opuestos; "
            "elige explícitamente un principal y los demás como matices.")
    written_bpms = [float(value.replace(",", ".")) for value in re.findall(
        r"(?<![\w.])([0-9]+(?:[.,][0-9]+)?)\s*bpm\b", original, flags=re.IGNORECASE,
    )]
    if bpm and written_bpms and any(value != bpm for value in written_bpms):
        warnings.append("El BPM del texto y el seleccionado difieren; revisa cuál quieres conservar.")
    elif bpm and not written_bpms:
        addition = f"{bpm} bpm"
        candidate = f"{enhanced}, {addition}"
        if len(candidate) <= MAX_PROMPT_CHARS:
            enhanced = candidate
            additions.append(addition)
        else:
            warnings.append("No se añade el BPM: el borrador excedería el límite de caracteres.")

    return {
        "original": original,
        "enhanced": enhanced,
        "genre_detected": genres[0]["name"] if genres else None,
        "suggested_bpm": rules[0]["bpm"] if rules else None,
        "genres": genres,
        "additions": additions,
        "warnings": warnings,
        "adaptation": "structured" if main else "literal",
        "selection": {"main_style": main, "influence_styles": influences,
                      "include_descriptions": include_descriptions},
    }
