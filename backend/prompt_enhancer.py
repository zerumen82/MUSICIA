"""Borrador optativo que conserva la intención y los controles elegidos.

No añade recetas de género ni traduce palabras aisladas. El borrador solo
puede incorporar un BPM seleccionado explícitamente, sin contradecir uno
ya escrito. La UI requiere aplicarlo antes de sustituir el texto editable.
"""

from __future__ import annotations

import re

from prompt_style import find_style

MIN_LENGTH = 3
MAX_PROMPT_CHARS = 800

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


def enhance_prompt(prompt: str, bpm: int | None = None) -> dict:
    """Prepara un borrador fiel; no muta ningún prompt enviado."""
    original = (prompt or "").strip()
    if len(original) < MIN_LENGTH:
        raise ValueError(f"El prompt necesita al menos {MIN_LENGTH} caracteres")

    rule = find_style(original)
    additions: list[str] = []
    warnings: list[str] = []
    enhanced = original
    written_bpms = [float(value.replace(",", ".")) for value in re.findall(
        r"(?<![\w.])([0-9]+(?:[.,][0-9]+)?)\s*bpm\b", original, flags=re.IGNORECASE,
    )]
    if bpm and written_bpms and any(value != bpm for value in written_bpms):
        warnings.append("El BPM del texto y el seleccionado difieren; revisa cuál quieres conservar.")
    elif bpm and not written_bpms:
        addition = f"{bpm} bpm"
        candidate = f"{original}, {addition}"
        if len(candidate) <= MAX_PROMPT_CHARS:
            enhanced = candidate
            additions.append(addition)
        else:
            warnings.append("No se añade el BPM: el borrador excedería el límite de caracteres.")

    return {
        "original": original,
        "enhanced": enhanced,
        "genre_detected": None if rule is None else rule["name"],
        "suggested_bpm": None if rule is None else rule["bpm"],
        "additions": additions,
        "warnings": warnings,
        "adaptation": "literal",
    }
