"""Glosario de estilos: el vocabulario real con el que el motor escribe géneros.

`acestep/constrained_logits_processor.py` carga `genres_vocab.txt` y lo usa como
whitelist sobre los logits del campo `genres`: lo que no está en ese archivo, el
modelo no puede emitirlo. Si la frase del usuario trae palabras que casan, el
motor recorta además el sub-trié a esas entradas (`_extract_caption_genres`).

Este módulo sirve ese mismo archivo a la UI: LOCAL-FIRST, sin red, con la misma
caché por mtime que usa el propio motor. Nada aquí es inventado: cada elemento
del glosario es una línea literal del archivo del modelo.
"""

from __future__ import annotations

import re
import threading
from pathlib import Path
from typing import Any

from loguru import logger

from config import PROJECT_ROOT
from prompt_style import STYLE_RULES

VOCAB_PATH = PROJECT_ROOT / "vendor" / "ACE-Step-1.5" / "acestep" / "genres_vocab.txt"

DEFAULT_LIMIT = 50
MAX_LIMIT = 200

_CACHE: dict[str, Any] = {"mtime": -1.0, "items": [], "lower": []}
_STYLES_CACHE: dict[str, Any] = {"mtime": -1.0, "styles": None}
_LOCK = threading.Lock()
_WARNED = False


def _vocab() -> tuple[list[str], list[str]]:
    """Géneros del archivo (originales y en minúsculas), con caché por mtime.

    Si el archivo no existe devuelve listas vacías y lo avisa una sola vez:
    el glosario nunca rellena el hueco con datos inventados.
    """
    global _WARNED
    try:
        mtime = VOCAB_PATH.stat().st_mtime
    except OSError:
        if not _WARNED:
            logger.warning(f"Glosario: no encuentro el vocabulario del motor en {VOCAB_PATH}")
            _WARNED = True
        return [], []
    with _LOCK:
        if mtime != _CACHE["mtime"]:
            text = VOCAB_PATH.read_text(encoding="utf-8")
            items = [line.strip() for line in text.splitlines() if line.strip()]
            _CACHE.update(mtime=mtime, items=items, lower=[item.lower() for item in items])
            logger.info(f"Glosario cargado: {len(items)} géneros de {VOCAB_PATH.name}")
        return _CACHE["items"], _CACHE["lower"]


def _norm(value: str) -> str:
    """Minúsculas y espacios colapsados: la comparación no distingue mayúsculas."""
    return " ".join((value or "").lower().split())


def glossary_line(text: str) -> str | None:
    """La línea entera del glosario igual a `text`, o None.

    No recorta ni elige una subfrase. Si el modelo escribió otra cosa, no es
    un género del glosario.
    """
    needle = _norm(text)
    if not needle:
        return None
    items, _lower = _vocab()
    for item in items:
        if _norm(item) == needle:
            return item
    return None


def _clamp(limit: Any) -> int:
    """Límite de resultados dentro de [1, MAX_LIMIT] (nunca se sirve el archivo entero)."""
    try:
        return max(1, min(int(limit), MAX_LIMIT))
    except (TypeError, ValueError):
        return DEFAULT_LIMIT


def _subfrase_literal(nombre: str, vocab: set[str]) -> str | None:
    """La subfrase más larga de `nombre` que sea LÍNEA LITERAL del modelo.

    «uptempo hard dance» no es línea (ni sus claves: uptempo, rawstyle,
    makina), pero «hard dance» sí: esa es la forma que el modelo puede
    escribir y por eso es la que se ofrece. Si ninguna subfrase está en el
    archivo devuelve None: aquí no se inventa ninguna forma (NO FAKE).
    """
    palabras = _norm(nombre).split()
    for size in range(len(palabras), 0, -1):
        for i in range(len(palabras) - size + 1):
            frase = " ".join(palabras[i:i + size])
            if frase in vocab:
                return frase
    return None


def catalog_styles(vocab_lower: set[str] | None = None) -> list[dict[str, Any]]:
    """Estilos propios de Musicia (catálogo: nombre, bpm y caption real).

    `genre` es la primera clave que aparece como LÍNEA LITERAL en el
    vocabulario del modelo (p. ej. «hard techno»), que es lo que la UI añade
    al prompt: una frase que el motor sí puede emitir. Antes se exigía que
    cada palabra suelta fuera una línea, y eso descartaba claves
    multipalabra cuya frase completa sí existe («hard techno», «hard house»).
    Las claves `re:` son expresiones, no líneas: se ignoran.

    `vocab_lower=None` carga el vocabulario él mismo (los llamadores que ya
    lo tienen en mano se lo pasan para no releer el archivo).
    """
    if vocab_lower is None:
        _, lower = _vocab()
        vocab_lower = set(lower)
        # Cachear por mtime del vocab: no recalcular en cada búsqueda del glosario.
        mtime = VOCAB_PATH.stat().st_mtime if VOCAB_PATH.exists() else -1.0
        with _LOCK:
            if mtime == _STYLES_CACHE["mtime"] and _STYLES_CACHE["styles"] is not None:
                return _STYLES_CACHE["styles"]
    estilos = []
    for rule in STYLE_RULES:
        genre = None
        if vocab_lower is not None:
            for key in rule.get("keys", ()):
                if key.startswith("re:"):
                    continue
                if _norm(key) in vocab_lower:
                    genre = key
                    break
            if genre is None:
                # Ninguna clave es línea del modelo: la subfrase del nombre
                # que sí lo es («uptempo hard dance» → «hard dance»).
                genre = _subfrase_literal(rule["name"], vocab_lower)
        estilos.append({
            "name": rule["name"], "bpm": rule.get("bpm"), "text": rule.get("style", ""),
            "keys": list(rule.get("keys", ())), "genre": genre,
        })
    if vocab_lower is None:
        with _LOCK:
            _STYLES_CACHE["mtime"] = mtime
            _STYLES_CACHE["styles"] = estilos
    return estilos


def search(q: str = "", limit: int = DEFAULT_LIMIT) -> dict[str, Any]:
    """Búsqueda en el vocabulario del modelo.

    Sin `q` devuelve las primeras entradas (para abrir el panel con algo);
    con `q`, las que la contienen, poniendo delante las que empiezan por ella.
    """
    items, lower = _vocab()
    limit = _clamp(limit)
    needle = _norm(q)
    if not items:
        return {
            "q": q, "total": 0, "limit": limit, "items": [], "styles": catalog_styles(set(lower)),
            "available": False, "source": str(VOCAB_PATH),
        }
    if not needle:
        picked, total = items[:limit], len(items)
    else:
        starts = [item for item, low in zip(items, lower) if low.startswith(needle)]
        rest = [
            item for item, low in zip(items, lower)
            if not low.startswith(needle) and needle in low
        ]
        picked, total = (starts + rest)[:limit], len(starts) + len(rest)
    return {
        "q": q, "total": total, "limit": limit, "items": picked, "styles": catalog_styles(set(lower)),
        "available": True, "source": str(VOCAB_PATH),
    }


def combine(a: str, b: str, limit: int = DEFAULT_LIMIT) -> dict[str, Any]:
    """Entradas del vocabulario que unen los dos estilos pedidos.

    Solo devuelve lo que existe en el archivo del modelo: si «techno gabber»
    no es una forma que el motor pueda decir, no se ofrece. Las formas exactas
    (por ejemplo «hardcore techno») van primero.
    """
    items, lower = _vocab()
    left, right = _norm(a), _norm(b)
    limit = _clamp(limit)
    base: dict[str, Any] = {
        "a": left, "b": right, "total": 0, "items": [], "exact": [],
        "available": bool(items), "source": str(VOCAB_PATH),
    }
    if not items or not left or not right or left == right:
        return base
    exact_forms = {f"{left} {right}", f"{right} {left}"}
    both = re.compile(rf"\b{re.escape(left)}\b")
    also = re.compile(rf"\b{re.escape(right)}\b")
    exact: list[str] = []
    matched: list[str] = []
    for item, low in zip(items, lower):
        if low in exact_forms:
            exact.append(item)
        elif left in low and right in low and both.search(low) and also.search(low):
            matched.append(item)
    return {
        **base, "exact": exact, "items": (exact + matched)[:limit],
        "total": len(exact) + len(matched),
    }
