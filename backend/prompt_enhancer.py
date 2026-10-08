"""El prompt del usuario se queda como está, primero.

MEJORAR añade dos cosas, sin pisar su frase:
1. El BPM elegido, si la frase no lo trae ya.
2. La descripción de estilo en inglés del estilo que EL PROMPT pide
   (`prompt_style`): el motor fue entrenado con captions ingleses largos y
   con una frase corta en español el sonido sale «a otra cosa» aunque el
   tempo acierte. Si el prompt no encaja en ninguna regla, no se añade nada.

No pega un género distinto al pedido (decisión 2026-10-04): la tabla de
estilos se elige por las palabras del propio usuario.
"""

from __future__ import annotations

from prompt_style import style_caption, find_style

MIN_LENGTH = 3
MAX_PROMPT_CHARS = 800


def enhance_prompt(prompt: str, bpm: int | None = None) -> dict:
    """Deja la frase del usuario la primera."""
    original = (prompt or "").strip()
    if len(original) < MIN_LENGTH:
        raise ValueError(f"El prompt necesita al menos {MIN_LENGTH} caracteres")

    low = original.lower()
    bpm_part = f"{bpm} bpm" if (bpm and f"{bpm} bpm" not in low) else ""

    # Estilo en inglés del género que el propio prompt pide (datos, no magia).
    rule = find_style(original)
    styled = style_caption(original)
    has_style = styled != original
    if has_style and len(f"{styled}, {bpm_part}".rstrip(", ")) > MAX_PROMPT_CHARS:
        has_style = False  # sin sitio: mejor la frase sola que cortarla a la mitad

    additions: list[str] = []
    if bpm_part:
        additions.append(bpm_part)
    if has_style:
        additions.append("descripción de estilo en inglés")

    tail = ", ".join(a for a in additions if a != "descripción de estilo en inglés")
    if has_style and tail:
        enhanced = f"{styled}, {tail}"
    elif has_style:
        enhanced = styled
    elif tail:
        enhanced = f"{original}, {tail}"
    else:
        enhanced = original

    return {
        "original": original,
        "enhanced": enhanced,
        "genre_detected": None if rule is None else rule["name"],
        "suggested_bpm": None if rule is None else rule["bpm"],
        "additions": additions,
    }
