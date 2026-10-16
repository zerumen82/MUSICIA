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
from source_understanding import SourceAnalysisSettings

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
    # Espera de Musicia y, al arrancar el motor, ACESTEP_GENERATION_TIMEOUT.
    # El motor trae 600 s. Con SFT, 50 pasos y batch 2, un original de 81 s
    # llegó al paso 49 y la UI mostró «sin audio válido» (2026-10-13).
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
    batch_size: int = 2
    # Dos variantes por tirada (doc del modelo: batch 2-4; «casi nunca
    # aciertas con una»). Decisión 2026-10-06 (ask_user): x2 tiempo/GPU.
    # Las 2 se descargan a BIBLIOTECA y el usuario elige (spec/02 [R3]).
    audio_format: str = "mp3"
    model: str = "acestep-v15-sft"
    # SFT en toda la app desde 2026-10-09 (decisión del usuario tras oír el
    # A/B iii.mp3 vs iii-sft.mp3): el turbo no obedece el prompt (guidance 1.0).
    # Dos modelos medidos en esta GPU de 8 GB (spec/02 [M1]): el turbo horneado
    # (rápido, sin CFG) y el sft con CFG de verdad (obedece el prompt).
    allowed_models: tuple[str, ...] = ("acestep-v15-turbo", "acestep-v15-sft")
    # Modelo de las operaciones de remix (REESTILAR, VERSIÓN, TRAMO):
    # son las que tienen que obedecer el prompt. CREAR sigue en `model`.
    remix_model: str = "acestep-v15-sft"
    # Tareas que se consideran remix para elegir modelo (ver `model_for`).
    remix_tasks: tuple[str, ...] = ("cover", "repaint")
    # Pasos de difusión y guidance por modelo. El turbo hornea el CFG en la
    # destilación: el motor fuerza guidance 1.0 y 8 pasos bastan. El sft sí
    # usa CFG: 50 pasos y guidance 9.0 (su familia admite guidance de verdad;
    # se subió de 7.0 el 2026-10-05 a petición de «que el estilo se cumpla»).
    # Si un modelo no está en la tabla, valen inference_steps/guidance_scale.
    steps_by_model: dict[str, int] = field(
        default_factory=lambda: {"acestep-v15-turbo": 8, "acestep-v15-sft": 50}
    )
    guidance_by_model: dict[str, float] = field(
        default_factory=lambda: {"acestep-v15-turbo": 1.0, "acestep-v15-sft": 9.0}
    )
    lm_model: str = "acestep-5Hz-lm-0.6B"
    lm_backend: str = "pt"
    # Apagado de verdad: build_payload lo fija en False (decisión 2026-10-03:
    # el thinking generaba códigos que mandaban más que el prompt). El True
    # viejo mentía: nadie lo leía.
    thinking: bool = False
    use_lm: bool = True
    # use_format (spec/02 [R3]): APAGADO el 2026-10-06 tras medirlo en vivo:
    # con caption en español el LM devuelve otra cosa (piano contemplativo
    # a 300 bpm para «hardcore en 4x4 con doble bombo») y el servidor
    # SUSTITUYE caption y BPM por ese invento (llm_generation_inputs.py).
    # Override por petición para futuros A/B; `thinking` sigue off.
    use_format: bool = False
    infer_method: str = "ode"
    task_type: str = "text2music"
    # Solo estas tareas caben en el turbo de 8 GB. lego/extract/complete
    # exigen el modelo base y no se ofrecen.
    allowed_tasks: tuple[str, ...] = ("text2music", "cover", "repaint")
    # 1.0 copia la forma; valores más bajos cambian más el estilo.
    cover_strength: float = 0.6
    # Reestilo (cover nativo): 0.2 es la transferencia de estilo del motor.
    remix_cover_strength: float = 0.2
    # El prompt dice "sin melodías": fuerza baja para que el caption gane y
    # la melodía original se pierda (el motor: a menor fuerza, más libertad).
    # Sin medir en GPU: el job lo registra para poder ajustarlo con datos.
    remix_cover_strength_no_melody: float = 0.1
    # El prompt dice "melodías como la original": fuerza alta para que el
    # audio de origen pese más. Solo vale en el camino cover (misma duración).
    remix_cover_strength_like_original: float = 0.5
    max_duration_seconds: float = 600.0
    # [M3] Diferencia mínima (bpm) entre lo pedido y lo medido para que
    # BIBLIOTECA enseñe «pedía X · salió Y». Medido, no de oído.
    bpm_display_tolerance: int = 3
    instrumental_marker: str = "[instrumental]"
    max_slug_chars: int = 40
    max_name_versions: int = 500

    def model_for(self, task: str, requested: str | None = None) -> str:
        """Modelo efectivo de una generación: lo pedido, o el de remix.

        Único sitio donde se decide. Cubre los dos caminos: el remix que
        construye su propia petición y la generación normal (VERSIÓN/TRAMO
        son cover/repaint y van al modelo de remix sin pedirlo).
        """
        if requested:
            return requested
        return self.remix_model if task in self.remix_tasks else self.model


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
class RemixSettings:
    """Contrato de edición del material original, independiente del género."""

    scopes: list[dict[str, str]] = field(default_factory=lambda: [
        {"id": "full", "label": "Canción completa", "why": "Rehace toda la canción a partir de esta. El texto dice qué cambia.", "how": "Rehace toda la canción a partir de esta. El texto dice qué cambia.", "placeholder": "Qué cambia y qué se queda."},
        {"id": "region", "label": "Tramo", "why": "Cambia solo el trozo que marques. El resto se queda.", "how": "Cambia solo el trozo que marques. El resto se queda.", "placeholder": "Qué debe sonar en el trozo marcado."},
        {"id": "groups", "label": "Por pistas", "why": "Elige en cada pista si se queda, se rehace o se quita.", "how": "Elige en cada pista si se queda, se rehace o se quita.", "placeholder": "Qué debe sonar en las pistas que pongas en transformar."},
    ])
    groups: list[dict[str, str]] = field(default_factory=lambda: [
        {"id": "vocals", "label": "Voz"},
        {"id": "drums", "label": "Batería"},
        {"id": "bass", "label": "Bajo"},
        {"id": "other", "label": "Acompañamiento restante"},
    ])
    actions: list[dict[str, str]] = field(default_factory=lambda: [
        {"id": "keep", "label": "Conservar"},
        {"id": "transform", "label": "Transformar"},
        {"id": "remove", "label": "Quitar"},
    ])
    repaint_modes: list[str] = field(default_factory=lambda: ["conservative", "balanced", "aggressive"])
    cover_noise_strength: float = 0.0
    repaint_mode: str = "balanced"
    repaint_strength: float = 0.5
    repaint_wav_crossfade_sec: float = 0.1
    repaint_latent_crossfade_frames: int = 10
    # Contrato del motor instalado generate_music._resolve_repaint_config;
    # los campos crossfade directos del request se ignoran allí.
    repaint_resolution_max_frames: int = 25
    repaint_resolution_max_wav_seconds: float = 0.05
    sample_rate: int = 48000
    intermediate_format: str = "wav32"
    export_bitrate: str = "192k"
    peak_limit_dbfs: float = -1.0
    duration_tolerance_seconds: float = 0.25
    # Si al quitar la voz generada y los grupos quitados queda menos que esta
    # fracción del audio nuevo, la pista transformada usa la generación entera.
    single_transform_min_remaining_ratio: float = 0.25
    timeline_min_duration_seconds: float = 1.0
    timeline_min_repeat_seconds: float = 1.0
    timeline_transition_seconds: float = 0.1
    timeline_max_transition_seconds: float = 2.0
    timeline_min_groove_confidence: float = 0.12
    groove_octave_score_ratio: float = 0.9
    groove_octave_lag_tolerance_frames: float = 1.0
    # El flujo de ataques del golpe tiene que superar al del compás por este
    # múltiplo para sustituirlo. Un tren de clics reparte la energía entre
    # armónicos y no llega; el bombo a negras, con el acento en el compás, sí.
    groove_onset_spectrum_ratio: float = 1.5
    # Un golpe solo desempata a otro período de evidencia cercana si es al
    # menos este múltiplo más nítido. Así una textura borrosa no gana por
    # unas milésimas de evidencia, ni un acento lento gana por un pliegue
    # apenas mayor.
    groove_hit_preference_ratio: float = 2.0
    # Un período interior solo cuenta como pulso si su evidencia, medida
    # con los mismos múltiplos, alcanza esta fracción de la evidencia del
    # lag legal más rápido. Por debajo es un pliegue sobre la caída de la
    # autocorrelación, no un golpe. Los pulsos reales revisados superan
    # tres cuartos; el pliegue falso de un audio sin golpe queda en un octavo.
    groove_peak_evidence_ratio: float = 0.5
    # El periodo elegido tiene que superar esta vez la evidencia de un tempo
    # un poco más lento o más rápido. Por debajo, la autocorrelación es una
    # meseta: el máximo es un número, no un golpe. Los pulsos ya revisados
    # quedan por encima de 1,39; la meseta que el ajuste convirtió en 226
    # queda en 1,15.
    groove_shoulder_ratio: float = 1.25
    groove_shoulder_period_fraction: float = 0.08
    groove_shoulder_min_frames: float = 2.0
    # Generaciones extra de una variante de canción completa cuando el audio
    # no se puede medir: no hay pulso, o el ajuste lo deja por debajo del
    # mínimo del detector. No recalibra el tempo ni usa el BPM pedido. Un
    # BPM medido fuera de tolerancia no gasta estos intentos. Si se agotan,
    # el error del detector sigue siendo el del trabajo.
    full_groove_retries: int = 2
    groove_smooth_frames: int = 3
    groove_refine_periods: int = 8
    groove_refine_radius_frames: float = 3.0
    groove_refine_step_frames: float = 0.025
    groove_refine_max_periods: int = 16
    groove_refine_max_candidates: int = 1000
    tempo_verify_tolerance_bpm: float = 2.0
    timeline_max_repetitions: int = 1200
    # El motor instalado continúa un final con repaint. El tutorial del
    # proveedor limita cada trozo a 3–90 s. El lote de la generación sigue
    # en 2; cada trozo continúa una base ya elegida.
    continuation_min_seconds: float = 3.0
    continuation_max_seconds: float = 90.0
    continuation_max_chunks: int = 200
    continuation_batch_size: int = 1
    demucs_model: str = "htdemucs"
    demucs_device: str = "auto"
    demucs_shifts: int = 1
    demucs_overlap: float = 0.25
    subprocess_poll_seconds: float = 0.5
    subprocess_timeout_seconds: float = 1800.0
    subprocess_termination_seconds: float = 5.0
    parameters: dict[str, dict[str, float]] = field(default_factory=lambda: {
        "cover_strength": {"min": 0.0, "max": 1.0, "step": 0.05},
        "cover_noise_strength": {"min": 0.0, "max": 1.0, "step": 0.05},
        "repaint_strength": {"min": 0.0, "max": 1.0, "step": 0.05},
        "repaint_wav_crossfade_sec": {"min": 0.0, "max": 2.0, "step": 0.05},
        "repaint_latent_crossfade_frames": {"min": 0, "max": 100, "step": 1},
        "bpm": {"min": 30, "max": 300, "step": 1},
        "seed": {"min": 0, "max": 2147483647, "step": 1},
        "gain_db": {"min": -60.0, "max": 12.0, "step": 0.5},
        # Segundos que avanzan las flechas del teclado en onda, tramo y comparación.
        "timeline_nudge_seconds": {"min": 0.0, "max": 30.0, "step": 1.0},
    })


@dataclass
class StyleTranslationSettings:
    """El estilo se pasa al inglés en local. La letra cantada no se toca.

    El modelo corre en el Python del motor, en CPU, para no ocupar la GPU
    de la música. Los números salen de las frases medidas el 2026-10-16:
    una caption ya inglesa se queda, y una palabra española dentro de una
    frase inglesa sí se traduce.
    """

    model_id: str = "facebook/nllb-200-distilled-600M"
    target_lang: str = "eng_Latn"
    device: str = "cpu"
    python_path: str = "vendor/ACE-Step-1.5/.venv/Scripts/python.exe"
    worker_script: str = "backend/style_translator_worker.py"
    language_map: str = "backend/nllb_languages.json"
    # «batería» salió battery y «bombo» salió bumper el 2026-10-16.
    # Se corrige con este fichero, después de traducir. No es una rama en código.
    term_fixes: str = "backend/style_term_fixes.json"
    english_code: str = "en"
    # Por debajo de esta confianza, un texto corto no se toma por otro idioma.
    clause_foreign_confidence: float = 0.15
    # Un texto con al menos estas letras usa el umbral largo, más bajo,
    # y además tiene que superar al inglés por este múltiplo. Medido el
    # 2026-10-16: «medieval flutes» es rumano a 0,083 contra inglés 0,078
    # (1,06) y se queda; «hardcore en 4x4 con doble bombo» es español a
    # 0,089 contra inglés 0,049 (1,82) y se traduce.
    long_text_chars: int = 12
    long_text_foreign_confidence: float = 0.08
    long_text_foreign_ratio: float = 1.5
    word_min_chars: int = 4
    word_min_confidence: float = 0.16
    # Una palabra solo destapa un idioma si supera al inglés por este múltiplo.
    word_foreign_ratio: float = 4.0
    max_input_tokens: int = 256
    max_new_tokens: int = 256
    # Un haz. Con uno solo, «flautas medievales» salió «Middle-earth flutes»
    # el 2026-10-16. Con cuatro, «Flutes of the Middle Ages».
    num_beams: int = 4
    do_sample: bool = False
    load_timeout_seconds: float = 180.0
    request_timeout_seconds: float = 120.0
    log_path: str = "logs/style-translator.log"


@dataclass
class ProcessLogSettings:
    """Ficheros que el progreso abre al pulsar. Rutas bajo logs/ del proyecto.

    tail_lines es lo que se enseña. line_char_budget acota la lectura de un
    fichero largo. max_tail_lines impide pedir el registro entero.
    """

    engine_stdout: str = "logs/acestep-api.log"
    engine_stderr: str = "logs/acestep-api.err.log"
    api_stderr: str = "logs/musicia-api.err.log"
    tail_lines: int = 200
    max_tail_lines: int = 2000
    line_char_budget: int = 400


@dataclass
class PathsSettings:
    outputs_dir: str = str(BACKEND_DIR / "outputs")


@dataclass
class AppSettings:
    host: str = "127.0.0.1"
    port: int = 8000
    # El supervisor repone la API si el proceso sigue vivo y el puerto no acepta
    # conexiones al pasar este tiempo. Un arranque normal escucha antes.
    api_listen_grace_seconds: float = 60.0
    log_level: str = "INFO"
    # Historial de trabajos en memoria: los activos no se tocan nunca; de los
    # terminados se guardan los últimos N (la UI sondea /music/jobs cada 3 s).
    job_history: int = 30
    cors_origins: list[str] = field(
        default_factory=lambda: ["http://localhost:5173", "http://127.0.0.1:5173"]
    )
    acestep: AcestepSettings = field(default_factory=AcestepSettings)
    generation: GenerationDefaults = field(default_factory=GenerationDefaults)
    mixer: MixerSettings = field(default_factory=MixerSettings)
    remix: RemixSettings = field(default_factory=RemixSettings)
    source_analysis: SourceAnalysisSettings = field(default_factory=SourceAnalysisSettings)
    style_translation: StyleTranslationSettings = field(default_factory=StyleTranslationSettings)
    process_logs: ProcessLogSettings = field(default_factory=ProcessLogSettings)
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


def engine_launch_timeout_seconds(settings: AppSettings | None = None) -> int:
    """Segundos que el proceso del motor puede usar en una generación.

    Hay que exportarlo como ACESTEP_GENERATION_TIMEOUT antes de arrancar.
    Si no, el motor corta a los 600 s aunque esta espera sea más larga.
    """
    chosen = settings or get_settings()
    return max(1, int(chosen.acestep.job_timeout))


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
