"""Configuración central de Musicia.

Todos los valores (puertos, rutas, parámetros de generación, voces por defecto,
orígenes CORS) viven aquí. Nada de constantes mágicas repartidas por el código.

Orden de precedencia, de mayor a menor:
1. Variables de entorno ``MUSICIA_*``
2. Fichero JSON (``MUSICIA_CONFIG_FILE`` o ``backend/config.json``)
3. Los valores por defecto declarados en este módulo

Anidar con doble guion bajo: ``MUSICIA_ACESTEP__BASE_URL=http://127.0.0.1:8001``
Las listas se pasan separadas por comas: ``MUSICIA_APP__CORS_ORIGINS=http://a,http://b``
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, fields, is_dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from loguru import logger

BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BACKEND_DIR.parent

ENV_PREFIX = "MUSICIA_"
NESTED_SEPARATOR = "__"
CONFIG_FILE_ENV = f"{ENV_PREFIX}CONFIG_FILE"
DEFAULT_CONFIG_FILE = BACKEND_DIR / "config.json"


@dataclass
class AcestepSettings:
    """Conexión con el motor local ACE-Step 1.5 (proceso separado en :8001)."""

    base_url: str = "http://127.0.0.1:8001"
    health_path: str = "/health"
    submit_path: str = "/release_task"
    result_path: str = "/query_result"
    audio_path: str = "/v1/audio"
    models_path: str = "/v1/models"
    format_input_path: str = "/format_input"
    request_timeout: float = 60.0
    # El sondeo de la pastilla no puede esperar lo mismo que una generación.
    health_timeout: float = 3.0
    poll_interval: float = 3.0
    # Cortes seguidos del sondeo. Si el motor sigue vivo, se sigue esperando.
    poll_max_misses: int = 8
    job_timeout: float = 1800.0
    api_key: str | None = None

    def endpoint(self, path: str) -> str:
        return f"{self.base_url.rstrip('/')}{path}"


@dataclass
class GenerationDefaults:
    """Valores por defecto de una generación (perfil GPU de 8 GB VRAM)."""

    duration_seconds: float = 120.0
    instrumental: bool = True
    bpm: int | None = None
    key_scale: str = ""
    time_signature: str = ""
    language: str = "es"
    inference_steps: int = 8
    guidance_scale: float = 7.0
    seed: int = -1
    use_random_seed: bool = True
    batch_size: int = 1
    audio_format: str = "mp3"
    model: str = "acestep-v15-turbo"
    # Uno solo residente. El XL pide 12 GB y el base no está medido en 8 GB.
    allowed_models: tuple[str, ...] = ("acestep-v15-turbo",)
    lm_model: str = "acestep-5Hz-lm-0.6B"
    lm_backend: str = "pt"
    thinking: bool = True
    use_lm: bool = True
    infer_method: str = "ode"
    task_type: str = "text2music"
    # Solo estas tareas caben en el turbo de 8 GB. lego/extract/complete
    # exigen el modelo base y no se ofrecen.
    allowed_tasks: tuple[str, ...] = ("text2music", "cover", "repaint")
    # 1.0 copia la forma; valores más bajos cambian más el estilo.
    cover_strength: float = 0.6
    # Voz real + base nueva. 0.2 es la transferencia de estilo del motor:
    # el prompt manda y la melodía del instrumental de origen sirve de guía.
    remix_cover_strength: float = 0.2
    # El prompt dice "sin melodías": fuerza baja para que el caption gane y
    # la melodía original se pierda (el motor: a menor fuerza, más libertad).
    # Sin medir en GPU: el job lo registra para poder ajustarlo con datos.
    remix_cover_strength_no_melody: float = 0.1
    # El prompt dice "melodías como la original": fuerza alta para que el
    # audio de origen pese más. Solo vale en el camino cover (misma duración).
    remix_cover_strength_like_original: float = 0.5
    max_duration_seconds: float = 600.0
    instrumental_marker: str = "[instrumental]"
    max_slug_chars: int = 40


@dataclass
class TtsSettings:
    default_voice: str = "es-ES-AlvaroNeural"
    default_output_name: str = "voice_output.mp3"
    max_text_chars: int = 5000


@dataclass
class MixerSettings:
    default_output_name: str = "mixed_output.mp3"
    min_gain_db: float = -60.0
    max_gain_db: float = 12.0
    # LOOP DE 4 COMPASES. Cuatro compases de 4/4 son 16 golpes, desde el primer golpe.
    loop_bars: int = 4
    beats_per_bar: int = 4
    # Arreglo automático: si la voz dura menos que este tanto de la base,
    # se corta en frases y se reparte. No se estira.
    arrange_shorter_than: float = 0.85
    vocal_silence_db: float = -36.0
    vocal_min_silence_s: float = 0.28
    vocal_min_phrase_s: float = 0.45
    vocal_frame_ms: int = 20
    vocal_slice_fade_s: float = 0.02
    max_vocal_phrases: int = 24
    fallback_bar_seconds: float = 2.0


@dataclass
class PathsSettings:
    outputs_dir: str = str(BACKEND_DIR / "outputs")


@dataclass
class AppSettings:
    host: str = "127.0.0.1"
    port: int = 8000
    log_level: str = "INFO"
    cors_origins: list[str] = field(
        default_factory=lambda: ["http://localhost:5173", "http://127.0.0.1:5173"]
    )
    acestep: AcestepSettings = field(default_factory=AcestepSettings)
    generation: GenerationDefaults = field(default_factory=GenerationDefaults)
    tts: TtsSettings = field(default_factory=TtsSettings)
    mixer: MixerSettings = field(default_factory=MixerSettings)
    paths: PathsSettings = field(default_factory=PathsSettings)

    @property
    def outputs_dir(self) -> Path:
        return Path(self.paths.outputs_dir).expanduser().resolve()


# ---------------------------------------------------------------------------
# Carga: defaults -> fichero JSON -> variables de entorno
# ---------------------------------------------------------------------------


def _to_tree(instance: Any) -> Any:
    """Convierte un dataclass en diccionario; los escalares se devuelven tal cual."""
    if not is_dataclass(instance):
        return instance
    return {f.name: _to_tree(getattr(instance, f.name)) for f in fields(instance)}


def _assign(instance: Any, name: str, value: Any) -> None:
    """Asigna un valor ya coercionado al campo indicado."""
    setattr(instance, name, value)


def _merge_tree(instance: Any, data: dict[str, Any]) -> Any:
    """Aplica un diccionario de datos sobre un dataclass, coercionando por tipo."""
    for name, incoming in data.items():
        if not hasattr(instance, name):
            logger.warning(f"Configuración ignorada (campo desconocido): {name}")
            continue
        current = getattr(instance, name)
        if is_dataclass(current) and isinstance(incoming, dict):
            _merge_tree(current, incoming)
        else:
            _assign(instance, name, _coerce(incoming, current))
    return instance


def _coerce(value: Any, reference: Any) -> Any:
    """Convierte un valor de JSON/entorno al tipo del valor por defecto."""
    if isinstance(value, str) and reference is not None:
        if isinstance(reference, bool):
            return value.strip().lower() in {"1", "true", "yes", "y", "on"}
        if isinstance(reference, int):
            return int(value)
        if isinstance(reference, float):
            return float(value)
    return value


def _apply_env(tree: dict[str, Any]) -> dict[str, Any]:
    """Aplica overrides ``MUSICIA_A__B=c`` sobre el árbol de configuración."""
    for env_key, raw_value in os.environ.items():
        if not env_key.startswith(ENV_PREFIX) or env_key == CONFIG_FILE_ENV:
            continue
        path = [part.lower() for part in env_key[len(ENV_PREFIX) :].split(NESTED_SEPARATOR) if part]
        if not path:
            continue
        cursor: Any = tree
        for part in path[:-1]:
            if not isinstance(cursor, dict) or part not in cursor:
                logger.warning(f"Variable de entorno ignorada (ruta desconocida): {env_key}")
                cursor = None
                break
            cursor = cursor[part]
        if cursor is None or not isinstance(cursor, dict):
            continue
        leaf = path[-1]
        if leaf not in cursor:
            logger.warning(f"Variable de entorno ignorada (campo desconocido): {env_key}")
            continue
        cursor[leaf] = _parse_env_value(raw_value, cursor[leaf])
    return tree


def _parse_env_value(raw_value: str, reference: Any) -> Any:
    """Interpreta un valor de entorno según el tipo del valor por defecto."""
    if isinstance(reference, list):
        return [item.strip() for item in raw_value.split(",") if item.strip()]
    return _coerce(raw_value, reference)


def _load_config_file() -> dict[str, Any]:
    """Lee el fichero JSON de configuración si existe."""
    config_path = Path(os.getenv(CONFIG_FILE_ENV, DEFAULT_CONFIG_FILE))
    if not config_path.exists():
        return {}
    try:
        with config_path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        logger.error(f"No se pudo leer la configuración {config_path}: {exc}")
        return {}
    logger.info(f"Configuración cargada desde {config_path}")
    return data if isinstance(data, dict) else {}


def build_settings() -> AppSettings:
    """Construye la configuración final combinando las tres fuentes."""
    settings = AppSettings()
    _merge_tree(settings, _load_config_file())
    _merge_tree(settings, _apply_env(_to_tree(settings)))
    return settings


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    """Devuelve la configuración de la aplicación (cacheada)."""
    settings = build_settings()
    settings.outputs_dir.mkdir(parents=True, exist_ok=True)
    logger.info(
        f"Configuración activa | motor={settings.acestep.base_url} "
        f"| outputs={settings.outputs_dir} | modelo={settings.generation.model}"
    )
    return settings