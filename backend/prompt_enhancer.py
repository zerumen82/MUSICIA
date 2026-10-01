"""Mejorador de prompts por reglas locales (sin IA externa, sin red).

Convierte una idea corta ("lo-fi tranquilo") en un prompt profesional rico:
instrumentación, estructura, adjetivos de mezcla y detalles de producción.
Reglas deterministas por género: mismo input, mismo output, cero fake.
"""

from __future__ import annotations

import re

# --- Perfiles por género: qué añade el experto a cada estilo ---
PROFILES: dict[str, dict] = {
    "lofi": {
        "match": ["lofi", "lo-fi", "hip hop", "chillhop"],
        "add": [
            "warm vinyl crackle texture",
            "soft dusty piano chords",
            "muted upright bass",
            "laid-back swing groove",
            "side-chained padding",
            "intimate close-mic mix",
            "tape saturation",
        ],
        "structure": "8-bar intro, mellow main theme, subtle variation, gentle outro",
    },
    "techno": {
        "match": ["techno", "electronic dance", "club"],
        "add": [
            "punchy saturated kick drum",
            "hypnotic rolling bassline",
            "stabby analog synth stabs",
            "crisp offbeat hi-hats",
            "dark atmospheric pads",
            "club sound system mix, wide stereo",
        ],
        "structure": "building intro, stripped groove, tension breakdown, full drop, outro",
    },
    "synthwave": {
        "match": ["synthwave", "retrowave", "80s", "retro"],
        "add": [
            "analog synth arpeggios",
            "gated reverb drums",
            "deep fretless bass",
            "neon retro lead melody",
            "lush reverberant mix",
        ],
        "structure": "cinematic intro, main theme, synth solo section, anthemic ending",
    },
    "orquestal": {
        "match": ["orquesta", "orquestal", "epic", "cinematic", "orquestral"],
        "add": [
            "soaring string ensemble",
            "brass swells and french horns",
            "cinematic taiko percussion",
            "subtle choir pads",
            "wide hall reverb, dynamic orchestral mix",
        ],
        "structure": "quiet introduction, progressive build, epic climax, resolution",
    },
    "jazz": {
        "match": ["jazz", "sax", "bebop", "swing", "bossa"],
        "add": [
            "warm saxophone lead",
            "walking double bass",
            "brushed drum kit",
            "round electric piano comping",
            "intimate club recording sound",
        ],
        "structure": "head theme, improvised solo section, head reprise, soft ending",
    },
    "ambient": {
        "match": ["ambient", "etereo", "etéreo", "drone", "texturas"],
        "add": [
            "evolving glassy pads",
            "field recording textures",
            "granular shimmer details",
            "very slow harmonic movement",
            "spacious cathedral reverb",
        ],
        "structure": "endless drift, no percussion, gradual textural evolution",
    },
    "acustico": {
        "match": ["acoustic", "acustico", "acústico", "guitarra", "folk"],
        "add": [
            "fingerpicked steel-string guitar",
            "soft brushed percussion",
            "warm double bass",
            "natural room ambience",
            "organic live performance feel",
        ],
        "structure": "intimate opening, verse progression, emotional bridge, warm close",
    },
    "electro": {
        "match": ["electro", "electronica", "electrónica", "edm", "house"],
        "add": [
            "deep sub bass",
            "crisp modern drum programming",
            "layered synth textures",
            "vocal-chop style leads",
            "polished radio-ready mix",
        ],
        "structure": "filtered intro, groove build, energetic drop, refined outro",
    },
}

# --- Adjetivos por mood ---
MOOD_WORDS: dict[str, list[str]] = {
    "nocturno": ["night-time atmosphere", "moody"],
    "tranquilo": ["relaxed", "easy-going"],
    "energico": ["high energy", "driving"],
    "melancolico": ["melancholic", "bittersweet"],
    "cinematografico": ["cinematic tension", "narrative arc"],
    "alegre": ["uplifting", "sunny"],
    "epico": ["epic", "grandiose"],
    "oscuro": ["dark", "brooding"],
    "chill": ["mellow", "cozy"],
}

# --- Español -> claves del diccionario (para detectar el género en el texto) ---
GENRE_ES = {
    "lofi": "lofi", "lo-fi": "lofi", "hip hop": "lofi", "chillhop": "lofi",
    "techno": "techno", "club": "techno",
    "synthwave": "synthwave", "retro": "synthwave", "ochentera": "synthwave",
    "orquesta": "orquestal", "orquestal": "orquestal", "epica": "orquestal",
    "épica": "orquestal", "cinematografica": "orquestal", "cinematográfica": "orquestal",
    "jazz": "jazz", "saxofon": "jazz", "saxofón": "jazz",
    "ambient": "ambient", "etéreo": "ambient", "etereo": "ambient", "texturas": "ambient",
    "acustica": "acustico", "acústica": "acustico", "guitarra": "acustico", "folk": "acustico",
    "electronica": "electro", "electrónica": "electro", "electro": "electro", "house": "electro",
}

MIN_LENGTH = 3
MAX_PROMPT_CHARS = 800


def enhance_prompt(prompt: str, bpm: int | None = None, mood: str | None = None) -> dict:
    """Enriquece un prompt con reglas de producción musical.

    Devuelve {original, enhanced, genre_detected, additions} para que la UI
    muestre qué se ha añadido (transparencia total, nada oculto).
    """
    original = (prompt or "").strip()
    if len(original) < MIN_LENGTH:
        raise ValueError(f"El prompt necesita al menos {MIN_LENGTH} caracteres")

    low = original.lower()
    genre_key = next((k for k, v in GENRE_ES.items() if k in low), None)
    profile_key = GENRE_ES.get(genre_key) if genre_key else None
    profile = PROFILES.get(profile_key) if profile_key else None

    additions: list[str] = []
    parts = [original]

    if profile:
        additions.extend(profile["add"])
        parts.append(profile["structure"])

    # Mood explícito o detectado en el texto
    mood_key = mood if mood in MOOD_WORDS else next(
        (k for k in MOOD_WORDS if k in low), None
    )
    if mood_key:
        additions.extend(MOOD_WORDS[mood_key])

    if bpm:
        additions.append(f"{bpm} bpm")
        parts.append(f"{bpm} bpm")

    # Deduplicar conservando orden
    seen: set[str] = set()
    unique_adds = [a for a in additions if not (a in seen or seen.add(a))]

    if unique_adds:
        parts.append(", ".join(unique_adds))

    enhanced = ", ".join(parts)
    if len(enhanced) > MAX_PROMPT_CHARS:
        enhanced = enhanced[:MAX_PROMPT_CHARS].rsplit(",", 1)[0]

    return {
        "original": original,
        "enhanced": enhanced,
        "genre_detected": profile_key or genre_key,
        "additions": unique_adds,
    }
