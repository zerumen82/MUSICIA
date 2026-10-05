"""El prompt del usuario se queda como está.

MEJORAR solo añade el BPM elegido, si la frase no lo trae ya.
No pega otro género: «techno», «hip hop» o «guitarra» no arrastran un estilo distinto.
"""

from __future__ import annotations

MIN_LENGTH = 3
MAX_PROMPT_CHARS = 800


def enhance_prompt(prompt: str, bpm: int | None = None) -> dict:
    """Deja la frase del usuario la primera."""
    original = (prompt or "").strip()
    if len(original) < MIN_LENGTH:
        raise ValueError(f"El prompt necesita al menos {MIN_LENGTH} caracteres")

    low = original.lower()
    additions: list[str] = []
    if bpm and f"{bpm} bpm" not in low:
        additions.append(f"{bpm} bpm")

    enhanced = original if not additions else f"{original}, {', '.join(additions)}"
    if len(enhanced) > MAX_PROMPT_CHARS:
        enhanced = enhanced[:MAX_PROMPT_CHARS].rsplit(",", 1)[0]

    return {
        "original": original,
        "enhanced": enhanced,
        "genre_detected": None,
        "additions": additions,
    }
