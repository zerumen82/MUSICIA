"""Pasa el texto de estilo al inglés antes de que lo vea el motor.

La letra cantada no entra aquí. El cuadro sigue mostrando lo que escribió
la persona; la frase que se envía y el payload usan esta misma función.
Si el traductor falla, no se manda nada inventado y la petición se detiene.
Un idioma que el traductor no conoce (el latín, p. ej.) se envía tal cual:
no corta la generación por una detección que el modelo no puede resolver.
"""

from __future__ import annotations

import atexit
import json
import os
import re
import subprocess
import threading
from functools import lru_cache
from pathlib import Path

from config import PROJECT_ROOT, AppSettings, get_settings
from genre_glossary import VOCAB_PATH
from prompt_style import (STRUCTURED_DETAILS_SOURCE_LANGUAGE, known_exclusion_spans,
                          known_spanish_exclusion_details)

_WORD = re.compile(r"[^\W\d_]+", flags=re.UNICODE)
_LETTERS = re.compile(r"[^\W\d_]", flags=re.UNICODE)
_CACHE: dict[tuple, str] = {}
_CACHE_LOCK = threading.Lock()
_DETECTOR = None
_DETECTOR_LOCK = threading.Lock()
_VOCAB: set[str] | None = None


class _Worker:
    def __init__(self) -> None:
        self.proc: subprocess.Popen | None = None
        self.lock = threading.Lock()
        self.counter = 0
        self.log = None

    def running(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def stop(self) -> None:
        proc = self.proc
        self.proc = None
        if proc is not None and proc.poll() is None:
            proc.kill()
            proc.wait(timeout=5)
        if self.log is not None:
            self.log.close()
            self.log = None


_WORKER = _Worker()


def _shutdown_worker() -> None:
    _WORKER.stop()


atexit.register(_shutdown_worker)


def reset_style_translation_cache() -> None:
    """Vacía la memoria de frases ya traducidas. La usa la prueba de idempotencia."""
    with _CACHE_LOCK:
        _CACHE.clear()


def translation_worker_running() -> bool:
    return _WORKER.running()


def stop_style_translation_worker() -> None:
    """Detiene el worker de traducción. La usan las pruebas para aislarse entre sí."""
    _WORKER.stop()


def _path(raw: str) -> Path:
    path = Path(raw)
    return path if path.is_absolute() else PROJECT_ROOT / path


def _require_file(path: Path, label: str) -> Path:
    if not path.is_file():
        raise ValueError(
            f"No está {label}: {path}. No se envía el estilo sin pasarlo al inglés."
        )
    return path


def _check(settings: AppSettings) -> None:
    config = settings.style_translation
    for name, value in (
        ("clause_foreign_confidence", config.clause_foreign_confidence),
        ("long_text_foreign_confidence", config.long_text_foreign_confidence),
        ("word_min_confidence", config.word_min_confidence),
    ):
        if not 0 < value <= 1:
            raise ValueError(f"La confianza «{name}» del traductor tiene que estar entre 0 y 1.")
    if config.word_foreign_ratio <= 1 or config.long_text_foreign_ratio <= 1:
        raise ValueError("La relación para traducir tiene que ser mayor que 1.")
    if config.word_min_chars < 1 or config.long_text_chars < 1:
        raise ValueError("Los mínimos de letras del traductor tienen que ser positivos.")
    if config.num_beams < 1 or config.max_input_tokens < 1 or config.max_new_tokens < 1:
        raise ValueError("Los límites del traductor tienen que ser positivos.")
    if config.load_timeout_seconds <= 0 or config.request_timeout_seconds <= 0:
        raise ValueError("Los tiempos de espera del traductor tienen que ser positivos.")


@lru_cache(maxsize=8)
def _language_map(path: str) -> dict[str, str]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    codes = data.get("codes") if isinstance(data, dict) else None
    if not isinstance(codes, dict) or not codes:
        raise ValueError(
            "El mapa de idiomas del traductor está vacío. No se envía el estilo sin pasarlo al inglés."
        )
    return {str(key).lower(): str(value) for key, value in codes.items()}


def _term_pattern(term: str) -> re.Pattern[str]:
    parts = [re.escape(part) for part in term.split() if part]
    return re.compile(r"(?<!\w)" + r"\s+".join(parts) + r"(?!\w)", re.IGNORECASE)


@lru_cache(maxsize=8)
def _term_fixes(path: str) -> tuple[tuple[str, str, str], ...]:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(
            "Las correcciones del traductor no se leen. "
            "No se envía el estilo sin pasar esas palabras al inglés."
        ) from exc
    rows = data.get("fixes") if isinstance(data, dict) else None
    if not isinstance(rows, list) or not rows:
        raise ValueError(
            "Las correcciones del traductor están vacías. "
            "No se envía el estilo sin pasar esas palabras al inglés."
        )
    fixes: list[tuple[str, str, str]] = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError(
                "Una corrección del traductor no tiene source, wrong y right. "
                "No se envía el estilo sin pasar esas palabras al inglés."
            )
        source = row.get("source")
        wrong = row.get("wrong")
        right = row.get("right")
        if not all(isinstance(item, str) and item.strip() for item in (source, wrong, right)):
            raise ValueError(
                "Una corrección del traductor no tiene source, wrong y right. "
                "No se envía el estilo sin pasar esas palabras al inglés."
            )
        if str(wrong).casefold() == str(right).casefold():
            raise ValueError(
                "Una corrección del traductor no cambia la palabra. "
                "No se envía el estilo sin pasar esas palabras al inglés."
            )
        fixes.append((str(source).strip(), str(wrong).strip(), str(right).strip()))
    fixes.sort(key=lambda item: len(item[0]), reverse=True)
    return tuple(fixes)


def _load_term_fixes(settings: AppSettings) -> tuple[tuple[str, str, str], ...]:
    path = _require_file(
        _path(settings.style_translation.term_fixes),
        "el fichero de correcciones del traductor",
    )
    return _term_fixes(str(path))


def _with_case(sample: str, replacement: str) -> str:
    if sample.isupper():
        return replacement.upper()
    if sample[:1].isupper():
        return replacement[:1].upper() + replacement[1:]
    return replacement


def correct_translated_terms(source: str, english: str, settings: AppSettings | None = None) -> str:
    """Cambia la palabra medida mal solo si el origen la pidió en español.

    Una caption que ya estaba en inglés no debe pasar por aquí. Si el inglés
    ya dice drums o kick, la palabra equivocada no está y no se toca.
    """
    chosen = settings or get_settings()
    grouped: dict[str, list[tuple[str, str]]] = {}
    order: list[str] = []
    for source_term, wrong, right in _load_term_fixes(chosen):
        if source_term not in grouped:
            grouped[source_term] = []
            order.append(source_term)
        grouped[source_term].append((wrong, right))
    remaining = source or ""
    result = english or ""
    for source_term in order:
        if not _term_pattern(source_term).search(remaining):
            continue
        wrongs = sorted(grouped[source_term], key=lambda item: len(item[0]), reverse=True)
        for wrong, right in wrongs:
            pattern = _term_pattern(wrong)

            def repl(match: re.Match[str], replacement: str = right) -> str:
                return _with_case(match.group(0), replacement)

            result = pattern.sub(repl, result)
        remaining = _term_pattern(source_term).sub(
            lambda match: " " * len(match.group(0)), remaining
        )
    return result


def _vocab_lines() -> set[str]:
    global _VOCAB
    if _VOCAB is None:
        if VOCAB_PATH.is_file():
            _VOCAB = {
                line.strip().lower()
                for line in VOCAB_PATH.read_text(encoding="utf-8").splitlines()
                if line.strip()
            }
        else:
            _VOCAB = set()
    return _VOCAB


def _detector():
    global _DETECTOR
    with _DETECTOR_LOCK:
        if _DETECTOR is None:
            from lingua import LanguageDetectorBuilder

            _DETECTOR = (
                LanguageDetectorBuilder.from_all_languages().with_preloaded_language_models().build()
            )
        return _DETECTOR


def _iso(language) -> str:
    code = language.iso_code_639_1
    if code is None:
        return ""
    return code.name.lower()


def _ranked(text: str, english_code: str):
    foreign: list[tuple[str, float]] = []
    english = 0.0
    for item in _detector().compute_language_confidence_values(text):
        iso = _iso(item.language)
        if iso == english_code:
            english = float(item.value)
        elif iso:
            foreign.append((iso, float(item.value)))
    foreign.sort(key=lambda item: item[1], reverse=True)
    return english, foreign


def _clause_iso(text: str, settings: AppSettings) -> str | None:
    """Idioma de la frase entera, o None si no destaca sobre el inglés."""
    config = settings.style_translation
    if text.lower() in _vocab_lines():
        return None
    english, foreign = _ranked(text, config.english_code)
    letters = len(_LETTERS.findall(text))
    long_text = letters >= config.long_text_chars
    threshold = (
        config.long_text_foreign_confidence
        if long_text
        else config.clause_foreign_confidence
    )
    margin = config.long_text_foreign_ratio if long_text else 1.0
    if foreign and foreign[0][1] >= threshold and foreign[0][1] > english * margin:
        return foreign[0][0]
    return None


def _source_iso(text: str, settings: AppSettings) -> str | None:
    """Idioma de origen, o None si el texto se queda como está."""
    config = settings.style_translation
    clause = _clause_iso(text, settings)
    if clause is not None:
        return clause
    best: tuple[str, float] | None = None
    for word in _WORD.findall(text):
        if len(word) < config.word_min_chars:
            continue
        word_english, word_foreign = _ranked(word, config.english_code)
        if not word_foreign:
            continue
        iso, confidence = word_foreign[0]
        if confidence < config.word_min_confidence:
            continue
        if word_english > 0 and confidence < word_english * config.word_foreign_ratio:
            continue
        if best is None or confidence > best[1]:
            best = (iso, confidence)
    if best is not None:
        return best[0]
    return None


def _flores(iso: str, settings: AppSettings) -> str | None:
    """Código FLORES del idioma, o None si el traductor no lo conoce (el latín, p. ej.).

    Un idioma sin código no corta la generación: el texto viaja tal cual.
    Que el mapa falle o esté vacío sí corta, eso lo decide _require_file.
    """
    config = settings.style_translation
    mapping = _language_map(str(_require_file(_path(config.language_map), "el mapa de idiomas")))
    return mapping.get(iso)


def _read_line(proc: subprocess.Popen, timeout: float) -> str:
    holder: dict[str, str] = {}

    def read() -> None:
        holder["line"] = proc.stdout.readline() if proc.stdout is not None else ""

    thread = threading.Thread(target=read, daemon=True)
    thread.start()
    thread.join(timeout)
    if thread.is_alive():
        raise TimeoutError
    return holder.get("line", "")


def _start_worker(settings: AppSettings) -> None:
    config = settings.style_translation
    python = _require_file(_path(config.python_path), "el Python del traductor")
    script = _require_file(_path(config.worker_script), "el programa del traductor")
    log_path = _path(config.log_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log = log_path.open("a", encoding="utf-8")
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["HF_HUB_DISABLE_TELEMETRY"] = "1"
    env["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"
    env["TRANSFORMERS_VERBOSITY"] = "error"
    env["TOKENIZERS_PARALLELISM"] = "false"
    proc = subprocess.Popen(
        [
            str(python), str(script),
            "--model", config.model_id,
            "--device", config.device,
            "--max-input-tokens", str(config.max_input_tokens),
            "--max-new-tokens", str(config.max_new_tokens),
            "--num-beams", str(config.num_beams),
            "--do-sample", "true" if config.do_sample else "false",
        ],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=log,
        text=True, encoding="utf-8", cwd=str(PROJECT_ROOT), env=env,
    )
    _WORKER.proc = proc
    _WORKER.log = log
    try:
        line = _read_line(proc, config.load_timeout_seconds)
    except TimeoutError as exc:
        _WORKER.stop()
        raise ValueError(
            "El traductor local no terminó de cargarse. No se envía el estilo sin pasarlo al inglés."
        ) from exc
    if proc.poll() is not None and not line:
        _WORKER.stop()
        raise ValueError(
            "El traductor local se cerró al arrancar. No se envía el estilo sin pasarlo al inglés."
        )
    try:
        ready = json.loads(line) if line else {}
    except json.JSONDecodeError as exc:
        _WORKER.stop()
        raise ValueError(
            "El traductor local no anunció que estaba listo. No se envía el estilo sin pasarlo al inglés."
        ) from exc
    if not ready.get("ready"):
        _WORKER.stop()
        detail = str(ready.get("error") or "sin detalle")
        raise ValueError(
            f"El traductor local no arrancó ({detail}). No se envía el estilo sin pasarlo al inglés."
        )


def _translate(text: str, source_lang: str, settings: AppSettings) -> str:
    config = settings.style_translation
    with _WORKER.lock:
        if not _WORKER.running():
            _start_worker(settings)
        proc = _WORKER.proc
        assert proc is not None and proc.stdin is not None
        _WORKER.counter += 1
        identity = _WORKER.counter
        proc.stdin.write(json.dumps({
            "id": identity, "text": text, "source_lang": source_lang, "target_lang": config.target_lang,
        }) + "\n")
        proc.stdin.flush()
        try:
            line = _read_line(proc, config.request_timeout_seconds)
        except TimeoutError as exc:
            _WORKER.stop()
            raise ValueError(
                "El traductor local tardó demasiado. No se envía el estilo sin pasarlo al inglés."
            ) from exc
        if not line:
            _WORKER.stop()
            raise ValueError(
                "El traductor local se cortó. No se envía el estilo sin pasarlo al inglés."
            )
        try:
            answer = json.loads(line)
        except json.JSONDecodeError as exc:
            _WORKER.stop()
            raise ValueError(
                "El traductor local contestó algo ilegible. No se envía el estilo sin pasarlo al inglés."
            ) from exc
        if answer.get("error"):
            raise ValueError(
                f"El traductor local falló ({answer['error']}). No se envía el estilo sin pasarlo al inglés."
            )
        if answer.get("id") != identity:
            _WORKER.stop()
            raise ValueError(
                "El traductor local contestó a otra frase. No se envía el estilo sin pasarlo al inglés."
            )
        return str(answer.get("text") or "")


def _piece(chunk: str, settings: AppSettings) -> str:
    stripped = chunk.strip()
    if not stripped:
        return chunk
    iso = _source_iso(stripped, settings)
    if iso is None or iso == settings.style_translation.english_code:
        return chunk
    _load_term_fixes(settings)
    source = _flores(iso, settings)
    if source is None:
        # El traductor no conoce este idioma (el latín, p. ej.): el texto
        # escrito viaja tal cual. Cortar aquí tumba la generación entera
        # por una detección que el modelo no puede resolver.
        return chunk
    if source == settings.style_translation.target_lang:
        return chunk
    # NLLB lee mal el español en mayúsculas: «CONTUNDENTES» sale contents
    # y «PITIDOS» sale questions. En minúsculas la misma frase sale bien.
    # Lo que se envía es ese inglés, no las mayúsculas del cuadro.
    english = _match_case(stripped, _translate(stripped.casefold(), source, settings).strip())
    english = correct_translated_terms(stripped, english, settings)
    if not english:
        raise ValueError(
            "El traductor local devolvió un estilo vacío. No se envía el texto sin pasarlo al inglés."
        )
    prefix = chunk[: len(chunk) - len(chunk.lstrip())]
    suffix = chunk[len(chunk.rstrip()) :]
    return f"{prefix}{english}{suffix}"


def _match_case(source: str, english: str) -> str:
    """Si el texto escrito empieza en minúscula, el inglés también."""
    if source and english and source[0].islower() and english[0].isupper():
        return english[0].lower() + english[1:]
    return english


def _segments(text: str) -> list[str]:
    found = _detector().detect_multiple_languages_of(text)
    if not found:
        return [text]
    parts: list[str] = []
    cursor = 0
    for span in found:
        if span.start_index > cursor:
            parts.append(text[cursor : span.start_index])
        parts.append(text[span.start_index : span.end_index])
        cursor = span.end_index
    if cursor < len(text):
        parts.append(text[cursor:])
    return parts


def _cache_key(settings: AppSettings, text: str) -> tuple:
    config = settings.style_translation
    return (config.model_id, config.target_lang, config.language_map, config.term_fixes, text)


def style_for_engine(prompt: str, settings: AppSettings | None = None) -> str:
    """Inglés que viaja al motor. Vacío sigue vacío. Una frase ya inglesa no se reescribe."""
    chosen = settings or get_settings()
    _check(chosen)
    text = (prompt or "").strip()
    if not text:
        return ""
    key = _cache_key(chosen, text)
    with _CACHE_LOCK:
        cached = _CACHE.get(key)
    if cached is not None:
        return cached
    # Una frase extranjera se traduce entera. Partirla mezcla idiomas mal
    # medidos («Batería suave » en español y «al fondo» en italiano).
    # Una frase inglesa con una palabra extranjera sí se parte, para no
    # reescribir el inglés que ya está bien.
    if _clause_iso(text, chosen):
        translated = _piece(text, chosen).strip()
    else:
        translated = "".join(_piece(part, chosen) for part in _segments(text)).strip()
    if not translated:
        # Inalcanzable hoy: _piece ya corta si una traducción sale vacía.
        # Si alguna refactor lo alcanzara, el texto escrito viaja tal cual en
        # vez de tumbar la generación (decisión del 2026-10-19: siempre entrega).
        return text.strip()
    with _CACHE_LOCK:
        _CACHE[key] = translated
        _CACHE[_cache_key(chosen, translated)] = translated
    return translated


_CONNECTORS: dict[str, str] = {}


def _load_connectors() -> dict[str, str]:
    """Conectores del catálogo: el hueco entre dos exclusiones también viaja."""
    global _CONNECTORS
    if not _CONNECTORS:
        from prompt_style import SPANISH_CONNECTORS
        _CONNECTORS = dict(SPANISH_CONNECTORS)
    return _CONNECTORS


def _is_spanish_connector(gap: str) -> bool:
    """True si el hueco entre dos exclusiones es un conector español."""
    conectores = _load_connectors()
    return any(re.fullmatch(rf"\s*{re.escape(espanol)}\s*", gap or "", flags=re.IGNORECASE)
               for espanol in conectores)


def _english_connector(gap: str) -> str:
    """El conector español pasa a inglés; el resto del hueco se conserva."""
    conectores = _load_connectors()
    for espanol, ingles in conectores.items():
        if re.fullmatch(rf"\s*{re.escape(espanol)}\s*", gap, flags=re.IGNORECASE):
            return f" {ingles} "
    return gap


def translate_exclusion_spans(prompt: str, spans, settings: AppSettings | None = None) -> str:
    """Traduce solo los tramos de exclusión reconocidos de un texto mixto.

    «gabber sin bombo» -> «gabber without kick»: el estilo se conserva tal
    cual (ya está en el idioma del modelo) y solo viaja la exclusión en
    inglés, para que el motor pueda honorarla. Sin tramos, devuelve el texto
    sin tocar.
    """
    text = prompt or ""
    if not spans:
        return text
    chosen = settings or get_settings()
    _check(chosen)
    source = _flores(STRUCTURED_DETAILS_SOURCE_LANGUAGE, chosen)
    if source is None:
        raise ValueError("El traductor local no tiene código para los detalles españoles; no se envían sin traducir.")
    _load_term_fixes(chosen)
    pieces: list[str] = []
    cursor = 0
    for indice, (start, end) in enumerate(spans):
        fragment = text[start:end]
        english = _match_case(fragment, _translate(fragment.casefold(), source, chosen).strip())
        english = correct_translated_terms(fragment, english, chosen)
        if not english:
            raise ValueError("El traductor local devolvió una exclusión vacía; no se prepara el prompt sin tus instrucciones.")
        hueco = text[cursor:start]
        if indice and _is_spanish_connector(hueco):
            hueco = _english_connector(hueco)
        pieces.append(hueco)
        pieces.append(english)
        cursor = end
    pieces.append(text[cursor:])
    return "".join(pieces)


def translate_style_details(prompt: str, settings: AppSettings | None = None) -> str:
    """Traduce detalles B9b aislados, con pista fiable para exclusiones ES cortas.

    El detector general conserva su comportamiento. Esta caché separada no
    reutiliza una abstención estadística previa como si fuera una traducción.
    No fabrica texto: las exclusiones reconocidas pasan por el mismo NLLB
    local y las mismas correcciones verificadas que el resto de la app.
    """
    text = (prompt or "").strip()
    if not known_spanish_exclusion_details(text):
        # Texto mixto: si hay exclusiones en español que el catálogo reconoce,
        # se traducen solo esos tramos; el resto se conserva tal cual.
        spans = known_exclusion_spans(text)
        if spans:
            return translate_exclusion_spans(text, spans, settings)
        return style_for_engine(text, settings)
    chosen = settings or get_settings()
    _check(chosen)
    source_lang = STRUCTURED_DETAILS_SOURCE_LANGUAGE
    key = ("structured-details-source", source_lang, *_cache_key(chosen, text))
    with _CACHE_LOCK:
        cached = _CACHE.get(key)
    if cached is not None:
        return cached
    source = _flores(source_lang, chosen)
    if source is None:
        raise ValueError("El traductor local no tiene código para los detalles españoles; no se envían sin traducir.")
    _load_term_fixes(chosen)
    translated = _match_case(text, _translate(text.casefold(), source, chosen).strip())
    translated = correct_translated_terms(text, translated, chosen)
    if not translated:
        raise ValueError("El traductor local devolvió detalles vacíos; no se prepara el prompt sin tus instrucciones.")
    with _CACHE_LOCK:
        _CACHE[key] = translated
        _CACHE[_cache_key(chosen, translated)] = translated
    return translated
