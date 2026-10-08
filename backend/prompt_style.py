"""Caption de estilo en inglés para el motor, a partir de datos.

El motor ACE-Step fue entrenado con captions descriptivos en inglés de
~312 caracteres (200 ejemplos en `vendor/ACE-Step-1.5/examples/text2music/`).
Una frase corta en español le deja libertad total sobre timbre y arreglos:
el tempo puede salir correcto y el sonido, sin embargo, «es otra cosa».

Este módulo NO reescribe la frase del usuario: la conserva entera y le
apunta detrás una descripción de estilo en inglés elegida por palabras
clave de SU propio texto. Si no reconoce ningún estilo pero sí detalles
(doble bombo, 4x4…), los detalles viajan igual en inglés; si no reconoce
nada, devuelve el prompt tal cual (nunca inventa). Los BPM son los típicos de cada estilo (datos);
el BPM elegido por el usuario manda siempre. El patrón rítmico tampoco se
deduce del BPM: «4x4» es un modificador más y hay que pedirlo.

Composición (desde el A/B real del 2026-10-06, jobs GPU 59de2282..2f24614d):
los detalles que el usuario pida por encima del estilo («doble bombo»,
«rápido», «sin voz»...) se detectan en SU frase y se añaden como cláusulas
de MODIFICADORES. Nada va pegado dentro del caption del estilo: el estilo
es una capa y los detalles, otras. A/B medido: el vocabulario que el motor
reconoce (hardstyle, double bass kick, snares) produce el kick dominante
y el doble bombo pedidos; «gabber» no existe en su vocabulario efectivo.

Sin red, sin GPU, sin dependencias: stdlib puro.
"""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

# Catálogo fuera del código (NO HARDCODE): estilos y modificadores viven en
# style_catalog.json, al lado de este módulo. Aquí solo la lógica de
# detección y composición. Las claves pueden ser subcadenas o regex con
# prefijo "re:" (para palabras que serían subcadena de otras: rap/rápido).
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

# Longitudes: por debajo de los límites del motor y de enhance_prompt.
MIN_LENGTH = 3
MAX_CAPTION_CHARS = 800


def _key_hit(key: str, text: str) -> bool:
    """¿Aparece la clave en el texto? Las claves con prefijo "re:" son
    regex (palabra completa); el resto, subcadenas de toda la vida."""
    if key.startswith("re:"):
        return re.search(key[3:], text) is not None
    return key in text

def _plain(text: str) -> str:
    """Minúsculas y sin acentos, para comparar sin falsos negativos."""
    decomposed = unicodedata.normalize("NFD", text or "")
    return decomposed.encode("ascii", "ignore").decode("ascii").lower()


def find_style(prompt: str) -> dict | None:
    """Regla de estilo cuya palabra clave aparece en el prompt (o None)."""
    text = _plain((prompt or "").strip())
    if len(text) < MIN_LENGTH:
        return None
    for rule in STYLE_RULES:
        if any(_key_hit(key, text) for key in rule["keys"]):
            return rule
    return None


def find_modifiers(prompt: str) -> tuple[str, ...]:
    """Cláusulas EN de los modificadores detectados en el texto del usuario."""
    text = _plain((prompt or "").strip())
    if len(text) < MIN_LENGTH:
        return ()
    return tuple(
        mod["clause"] for mod in STYLE_MODIFIERS if any(_key_hit(key, text) for key in mod["keys"])
    )


def analyze_prompt(prompt: str) -> dict:
    """Separación de capas de un prompt: frase, estilo y detalles (datos).

    Fuente única del endpoint /music/style_options: la UI pinta lo que esta
    función decide y los chips salen del mismo catálogo que la detección.
    El chip de un detalle ya escrito se marca activo, no se duplica.
    """
    original = (prompt or "").strip()
    text = _plain(original)
    rule = find_style(original)
    detected = rule["name"] if rule else None
    chips = []
    for mod in STYLE_MODIFIERS:
        already = len(text) >= MIN_LENGTH and any(_key_hit(key, text) for key in mod["keys"])
        suggested = not already and (
            "*" in mod["suggest_with"] or (detected is not None and detected in mod["suggest_with"])
        )
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
        "suggested_bpm": style_bpm(original),
        "modifiers": [
            mod["label"]
            for mod in STYLE_MODIFIERS
            if len(text) >= MIN_LENGTH and any(_key_hit(key, text) for key in mod["keys"])
        ],
        "chips": chips,
    }


def style_caption(prompt: str) -> str:
    """Frase del usuario + estilo + modificadores detectados (datos, en orden).

    No pega nada que el usuario no haya pedido: el estilo sale de sus
    palabras clave y los modificadores, de los detalles que pidió. Si no
    hay estilo pero sí detalles, los detalles viajan igual en inglés
    (antes se perdían: sin género no había caption compuesto). Si no
    hay regla ni detalles, o el resultado se pasa del límite, devuelve
    el prompt. Idempotente: lo ya compuesto no se duplica (ni estilo
    ni cláusulas). Así MEJORAR → GENERAR y el compose del servidor no
    suman dos estilos.
    """
    original = (prompt or "").strip()
    rule = find_style(original)
    # Las cláusulas ya compuestas no cuentan como «pedidas»: se apartan
    # antes de detectar, o la segunda pasada re-detectaría palabras
    # inglesas («rapid», «speed», «distorted») y sumaría de más.
    remainder = original
    for mod in STYLE_MODIFIERS:
        if mod["clause"] in remainder:
            remainder = remainder.replace(mod["clause"], " ")
    mods = [m for m in find_modifiers(remainder) if m not in original]
    if rule is None:
        if not mods:
            return original
        parts = [original.rstrip(".,; "), *mods]
    else:
        if rule["style"] in original:
            return original
        parts = [original.rstrip(".,; "), rule["style"], *mods]
    caption = ". ".join(parts)
    if len(caption) > MAX_CAPTION_CHARS:
        return original
    return caption


def style_bpm(prompt: str, requested: float | None = None) -> int | None:
    """BPM de las metas: lo pedido manda; si no, el típico del estilo."""
    if requested:
        return int(round(float(requested)))
    rule = find_style(prompt)
    if rule is None:
        return None
    return rule["bpm"]
