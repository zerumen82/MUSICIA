"""Proyectos sobre audio original: cover, repaint y recombinación de grupos.

El género analizado es información revisable; no altera texto, operación ni
parámetros. Los intermedios se conservan como PCM para poder verificarlos.
"""
from __future__ import annotations

import asyncio
import hashlib
import math
import time
import uuid
from pathlib import Path
from typing import Literal

from fastapi import BackgroundTasks, HTTPException
from pydantic import BaseModel, Field
from pydub import AudioSegment
from loguru import logger

from audio_analysis import detect_groove
from mixer_service import MixerService
from music_service import GenerationRequest, MusicEngineError, engine_is_converting
from prompt_constraints import rules as constraint_rules, validate_explicit_constraints
from separator_service import SeparatorService
from source_understanding import category_catalog

COMPUTE_LOCK = asyncio.Lock()


class RemixProjectRequest(BaseModel):
    source_name: str
    source_kind: Literal["upload", "output"] | None = None
    prompt: str = ""
    scope: Literal["full", "region", "groups"] = "full"
    output_name: str | None = None
    reference_name: str | None = None
    reference_kind: Literal["upload", "output"] | None = None
    cover_strength: float | None = None
    cover_noise_strength: float | None = None
    region_start: float | None = None
    region_end: float | None = None
    repaint_mode: str | None = None
    repaint_strength: float | None = None
    repaint_wav_crossfade_sec: float | None = None
    repaint_latent_crossfade_frames: int | None = None
    bpm: int | None = None
    source_bpm: float | None = None
    duration_seconds: float | None = None
    repeat_start: float | None = None
    repeat_end: float | None = None
    transition_seconds: float | None = None
    seed: int | None = None
    lyrics: str | None = None
    instrumental: bool | None = None
    groups: dict[str, Literal["keep", "transform", "remove"]] | None = None
    gains_db: dict[str, float] = Field(default_factory=dict)
    source_classification: Literal["electronic", "non_electronic", "mixed", "unknown"] | None = None
    classification_origin: Literal["manual", "analysis", "unknown"] = "unknown"

    class Config:
        extra = "forbid"


class SeparateGroupsRequest(BaseModel):
    file_name: str
    source_kind: Literal["upload", "output"] | None = None


def source_digest(source: Path) -> str:
    """Identifica las muestras de origen, no solo un nombre reutilizable.

    Lectura por chunks: `hashlib.file_digest` necesita Python 3.11 y la API
    productiva corre en 3.10 (bug real 2026-10-12: un job remix falló en vivo).
    """
    digest = hashlib.sha256()
    with source.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_project(request: RemixProjectRequest, duration: float, settings) -> None:
    config = settings.remix
    if not math.isfinite(duration) or duration <= 0 or duration > settings.generation.max_duration_seconds:
        raise ValueError("La fuente debe tener una duración positiva dentro del límite configurado")
    transforms = request.scope != "groups" or any(
        action == "transform" for action in (request.groups or {}).values()
    )
    if transforms and not request.prompt.strip():
        raise ValueError("Escribe qué transformación quieres en el prompt")
    for key, limits in config.parameters.items():
        if key == "gain_db":
            values = request.gains_db.values()
        else:
            value = getattr(request, key, None)
            values = [] if value is None else [value]
        for value in values:
            if not math.isfinite(value) or not limits["min"] <= value <= limits["max"]:
                raise ValueError(f"{key} debe estar entre {limits['min']} y {limits['max']}")
    if request.reference_kind is not None and not request.reference_name:
        raise ValueError("La referencia necesita un nombre de audio")
    if request.scope == "region":
        start, end = request.region_start, request.region_end
        if (start is None or end is None or not math.isfinite(start) or not math.isfinite(end)
                or not 0 <= start < end <= duration):
            raise ValueError("Selecciona un intervalo dentro de la duración real del original")
        if (request.repaint_mode or config.repaint_mode) not in config.repaint_modes:
            raise ValueError("Modo regional no soportado por el checkpoint instalado")
    elif request.region_start is not None or request.region_end is not None:
        raise ValueError("La región solo se aplica al ámbito Tramo")
    if request.scope == "groups":
        ids = {group["id"] for group in config.groups}
        if set(request.groups or {}) != ids:
            raise ValueError("Selecciona exactamente una acción para cada grupo real")
        if set(request.gains_db) - ids:
            raise ValueError("Hay volúmenes para grupos inexistentes")
        if all(action == "remove" for action in request.groups.values()):
            raise ValueError("Quitar todos los grupos no produce una pista musical")
        if request.lyrics and request.groups.get("vocals") != "transform":
            raise ValueError("Una letra nueva requiere transformar el grupo de voz")
        if request.instrumental is True and request.groups.get("vocals") == "keep":
            raise ValueError("Conservar la voz y eliminarla mediante instrumental son instrucciones incompatibles")
    elif request.groups is not None or request.gains_db:
        raise ValueError("Los grupos y sus volúmenes solo se aplican al ámbito Por pistas")
    timeline_fields = (request.duration_seconds, request.repeat_start, request.repeat_end, request.transition_seconds)
    if request.scope == "region" and any(value is not None for value in timeline_fields):
        raise ValueError("La duración y repetición solo se aplican a Canción completa o Por pistas")
    if request.source_bpm is not None:
        limits = config.parameters["bpm"]
        if (request.scope != "groups" or request.bpm is None or not math.isfinite(request.source_bpm)
                or not limits["min"] <= request.source_bpm <= limits["max"]):
            raise ValueError("El BPM original revisado requiere BPM común en Por pistas dentro de sus límites")
    if request.duration_seconds is not None and (
            not math.isfinite(request.duration_seconds)
            or not config.timeline_min_duration_seconds <= request.duration_seconds <= settings.generation.max_duration_seconds):
        raise ValueError("La duración objetivo debe estar dentro del límite configurado")
    if (request.repeat_start is None) != (request.repeat_end is None):
        raise ValueError("Indica inicio y fin de la parte a repetir")
    if request.repeat_start is not None and (
            not math.isfinite(request.repeat_start) or not math.isfinite(request.repeat_end)
            or not 0 <= request.repeat_start < request.repeat_end <= duration):
        raise ValueError("La parte a repetir debe estar dentro de la canción original")
    if request.transition_seconds is not None and (
            not math.isfinite(request.transition_seconds)
            or not 0 < request.transition_seconds <= config.timeline_max_transition_seconds):
        raise ValueError("La transición debe ser positiva y estar dentro del límite configurado")
    if any(value is not None for value in (request.repeat_start, request.repeat_end, request.transition_seconds)) and request.duration_seconds is None:
        raise ValueError("La repetición y transición requieren una duración objetivo mayor")
    voice_control = request.instrumental
    if request.scope == "groups":
        voice_action = request.groups.get("vocals")
        if voice_action in {"keep", "remove"}:
            voice_control = voice_action == "remove"
    validate_explicit_constraints(request.prompt, bpm=request.bpm, instrumental=voice_control,
                                  lyrics=request.lyrics, marker=settings.generation.instrumental_marker)


def timeline_plan(request, duration, settings, measured=None) -> dict:
    config = settings.remix
    measured = measured or {}
    if request.scope == "full" and request.bpm is not None:
        return {"source_duration_seconds": duration, "natural_duration_seconds": None,
                "target_duration_seconds": request.duration_seconds, "tempo_ratio": None,
                "source_bpm": None, "source_bpm_origin": "pending_generated_measurement",
                "bpm_measured": None, "bpm_confidence": None, "target_bpm": request.bpm,
                "repeat_start": 0.0 if request.repeat_start is None else request.repeat_start,
                "repeat_end": duration if request.repeat_end is None else request.repeat_end,
                "mapped_repeat_start": None, "mapped_repeat_end": None,
                "transition_seconds": (config.timeline_transition_seconds if request.transition_seconds is None
                                       else request.transition_seconds),
                "method": "pending_generated_timeline", "tempo_method": "measured_pcm_atempo",
                "beat_clock_bpm": None, "beat_clock_origin": "pending_adjusted_measurement",
                "engine_tempo_method": "engine_conditioning", "status": "pending_generated_audio"}
    source_bpm, origin, ratio = None, "not_required", 1.0
    if request.scope == "groups" and request.bpm is not None:
        if request.source_bpm is not None:
            source_bpm, origin = request.source_bpm, "manual"
        else:
            source_bpm, origin = measured.get("bpm_measured"), "measurement"
            confidence = measured.get("bpm_confidence", 0)
            limits = config.parameters["bpm"]
            if (not source_bpm or not math.isfinite(source_bpm)
                    or not math.isfinite(confidence) or confidence < config.timeline_min_groove_confidence
                    or not limits["min"] <= source_bpm <= limits["max"]):
                raise ValueError("No hay un BPM original fiable: indica el BPM original revisado para cambiar todas las pistas juntas")
        ratio = request.bpm / source_bpm
    natural = duration / ratio
    target = natural if request.duration_seconds is None else request.duration_seconds
    if natural > settings.generation.max_duration_seconds or target > settings.generation.max_duration_seconds:
        raise ValueError("El cambio de tempo o la duración exceden el límite de salida configurado")
    if target < natural:
        minimum = math.ceil(natural)
        raise ValueError(f"La duración objetivo debe ser igual o mayor que la canción al tempo elegido: "
                         f"mínimo {minimum} s ({minimum // 60}:{minimum % 60:02d})")
    expanding = target > natural
    if not expanding and any(value is not None for value in (request.repeat_start, request.repeat_end, request.transition_seconds)):
        raise ValueError("La parte y transición solo se aplican al ampliar la canción")
    start = 0.0 if request.repeat_start is None else request.repeat_start
    end = duration if request.repeat_end is None else request.repeat_end
    transition = config.timeline_transition_seconds if request.transition_seconds is None else request.transition_seconds
    if expanding and ((end - start) / ratio < config.timeline_min_repeat_seconds
                      or (end - start) / ratio <= 2 * transition or natural <= transition):
        raise ValueError("La parte a repetir es demasiado corta para las transiciones elegidas")
    return {"source_duration_seconds": duration, "natural_duration_seconds": natural,
            "target_duration_seconds": target, "tempo_ratio": ratio,
            "source_bpm": source_bpm, "source_bpm_origin": origin,
            "bpm_measured": measured.get("bpm_measured"), "bpm_confidence": measured.get("bpm_confidence"),
            "target_bpm": request.bpm, "repeat_start": start, "repeat_end": end,
            "beat_clock_bpm": request.bpm if request.scope == "groups" else None,
            "beat_clock_origin": "requested_common_tempo" if request.scope == "groups" and request.bpm else "not_required",
            "mapped_repeat_start": start / ratio, "mapped_repeat_end": end / ratio,
            "transition_seconds": transition if expanding else 0.0,
            "method": "repeat_crossfade" if expanding else "original",
            "tempo_method": "common_pcm_atempo" if ratio != 1 else (
                "engine_conditioning" if request.scope == "full" and request.bpm else "original")}


def require_measured_tempo(measured, config, stage) -> float:
    """Medición independiente obligatoria para ajustar y acreditar el tempo full."""
    measured = measured or {}
    bpm, confidence = measured.get("bpm_measured"), measured.get("bpm_confidence")
    limits = config.parameters["bpm"]
    if (isinstance(bpm, bool) or not isinstance(bpm, (int, float)) or not math.isfinite(bpm)
            or not limits["min"] <= bpm <= limits["max"]
            or isinstance(confidence, bool) or not isinstance(confidence, (int, float)) or not math.isfinite(confidence)
            or not config.timeline_min_groove_confidence <= confidence <= 1):
        raise ValueError(f"No hay un BPM fiable {stage}; no se puede verificar el ajuste de tempo "
                         f"(medido: {bpm}, confianza: {confidence})")
    return float(bpm)


def full_variant_plan(request, source_duration, engine_duration, settings, measured) -> dict:
    bpm = require_measured_tempo(measured, settings.remix, "en la variante generada")
    scale = engine_duration / source_duration
    effective = request.model_copy(update={
        "scope": "groups", "source_bpm": bpm,
        "repeat_start": None if request.repeat_start is None else request.repeat_start * scale,
        "repeat_end": None if request.repeat_end is None else request.repeat_end * scale,
    })
    plan = timeline_plan(effective, engine_duration, settings, measured)
    plan.update(source_duration_seconds=source_duration, engine_duration_seconds=engine_duration,
                source_bpm_origin="generated_measurement", tempo_method="measured_pcm_atempo",
                beat_clock_bpm=None, beat_clock_origin="pending_adjusted_measurement",
                engine_tempo_method="engine_conditioning", status="resolved",
                repeat_start=0.0 if request.repeat_start is None else request.repeat_start,
                repeat_end=source_duration if request.repeat_end is None else request.repeat_end)
    return plan


def tempo_after_repetition(measured: dict, periods: list, arrangement: dict, config) -> dict:
    """Si el detector se queda con un grupo de la copia, conserva el pulso ya medido.

    No mira el BPM pedido. La copia tiene un número entero de golpes. Si la
    lectura es ese bloque partido en grupos enteros (15 golpes oídos de 5 en
    5, por ejemplo) y el golpe previo sigue presente, se conserva ese golpe.
    """
    if not arrangement or arrangement.get("method") != "repeat_crossfade":
        return measured
    stride = arrangement.get("repetition_stride_seconds")
    clock = arrangement.get("beat_clock_bpm")
    beats = arrangement.get("beats_per_repetition")
    tolerance = config.tempo_verify_tolerance_bpm
    if not math.isfinite(tolerance) or tolerance < 0:
        raise ValueError("La tolerancia de verificación BPM debe ser finita y no negativa")
    if (isinstance(stride, bool) or not isinstance(stride, (int, float)) or not math.isfinite(stride) or stride <= 0
            or isinstance(clock, bool) or not isinstance(clock, (int, float)) or not math.isfinite(clock) or clock <= 0
            or isinstance(beats, bool) or not isinstance(beats, int) or beats < 2):
        return measured
    if abs(stride - beats * 60.0 / clock) > config.duration_tolerance_seconds:
        return measured
    chosen = measured.get("bpm_measured")
    if isinstance(chosen, bool) or not isinstance(chosen, (int, float)) or not math.isfinite(chosen):
        return measured
    grouped = False
    for divisor in range(1, beats):
        if beats % divisor != 0:
            continue
        group = beats // divisor
        if group <= 1:
            continue
        if abs(chosen - clock / group) <= tolerance:
            grouped = True
            break
    if not grouped:
        return measured
    ratio = config.groove_peak_evidence_ratio
    if isinstance(ratio, bool) or not isinstance(ratio, (int, float)) or not math.isfinite(ratio) or not 0 < ratio <= 1:
        raise ValueError("Configuración de evidencia de pico de groove inválida")
    usable = []
    for item in periods or []:
        bpm, evidence, confidence = item.get("bpm"), item.get("evidence"), item.get("confidence")
        if any(isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value)
               for value in (bpm, evidence, confidence)):
            continue
        usable.append((float(bpm), float(evidence), float(confidence)))
    if not usable:
        return measured
    strongest = max(item[1] for item in usable)
    matches = [item for item in usable
               if item[1] >= strongest * ratio
               and config.timeline_min_groove_confidence <= item[2] <= 1
               and abs(item[0] - clock) <= tolerance]
    if not matches:
        return measured
    bpm, _evidence, confidence = min(matches, key=lambda item: abs(item[0] - clock))
    return {"bpm_measured": round(bpm, 2), "bpm_confidence": round(confidence, 3),
            "repetition_bpm_measured": round(float(chosen), 2),
            "repetition_bpm_confidence": measured.get("bpm_confidence"),
            "tempo_reading": "pulso previo, no el periodo de la repetición"}


def required_measured_tempo(path: Path, arrangement: dict | None = None, config=None) -> dict:
    """BPM obligatorio de canción completa. El motivo del detector no se esconde."""
    groove = detect_groove(path, include_periods=arrangement is not None)
    measured = {"bpm_measured": round(float(groove["bpm"]), 2),
                "bpm_confidence": round(float(groove.get("confidence") or 0), 3)}
    if arrangement is None:
        return measured
    return tempo_after_repetition(measured, groove.get("periods") or [], arrangement, config)


def verify_requested_tempo(measured, requested_bpm, config, stage) -> None:
    bpm = require_measured_tempo(measured, config, stage)
    if not math.isfinite(config.tempo_verify_tolerance_bpm) or config.tempo_verify_tolerance_bpm < 0:
        raise ValueError("La tolerancia de verificación BPM debe ser finita y no negativa")
    if abs(bpm - requested_bpm) > config.tempo_verify_tolerance_bpm:
        raise ValueError(f"El BPM final medido {bpm:g} no cumple el pedido {requested_bpm:g} "
                         f"(tolerancia {config.tempo_verify_tolerance_bpm:g} BPM)")


def full_groove_retries(config) -> int:
    """Generaciones extra permitidas cuando una variante no tiene pulso."""
    value = config.full_groove_retries
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError("Los reintentos de una variante sin pulso deben ser un entero no negativo")
    return value


def audio_has_no_usable_groove(error: BaseException) -> bool:
    """True solo si esta muestra no se puede medir. Un BPM fuera de tolerancia no se regenera."""
    if not isinstance(error, ValueError):
        return False
    text = str(error)
    if text.startswith(("Configuración", "La tolerancia")) or "excede el límite" in text:
        return False
    if text.startswith("El BPM final medido"):
        return False
    return text.startswith((
        "El groove es incierto",
        "Audio demasiado corto",
        "No se ha detectado un tempo",
        "No hay un BPM fiable en la variante generada",
    ))


def replacement_request_seed(requested, batch_size, attempt, seed_max):
    """Semilla pedida para una muestra nueva. No es la semilla real del motor.

    Se aparta un lote entero por intento para no repetir el par ya oído.
    Si no hay semilla, o no cabe, la petición queda aleatoria.
    """
    if any(isinstance(value, bool) or not isinstance(value, int)
           for value in (requested, batch_size, attempt, seed_max)):
        return None
    if batch_size < 1 or attempt < 1 or seed_max < 0 or requested < 0:
        return None
    value = requested + batch_size * attempt
    if value > seed_max:
        return None
    return value


async def accept_measured_draw(measure, replace, retries: int):
    """Devuelve la medición y cuántas muestras nuevas hizo falta pedir."""
    draws = 0
    while True:
        try:
            return await measure(), draws
        except ValueError as exc:
            if draws >= retries or not audio_has_no_usable_groove(exc):
                raise
            draws += 1
            await replace(draws)


async def accept_verified_draw(measure, adjust, replace, retries: int):
    """Mide y ajusta. Pide otra muestra solo cuando el audio no se puede medir.

    Un BPM medido que no cumple la tolerancia sale tal cual: no se persigue
    el número con otra generación.
    """
    draws = 0
    while True:
        try:
            measured = await measure()
            verified = await adjust(measured)
            return measured, verified, draws
        except ValueError as exc:
            if draws >= retries or not audio_has_no_usable_groove(exc):
                raise
            draws += 1
            await replace(draws, exc)


def _visible_phase(status) -> str:
    """Fase corta para la mesa. El texto crudo del motor no se enseña."""
    stage = (getattr(status, "stage", "") or "").lower()
    text = (getattr(status, "progress_text", "") or "").lower()
    if getattr(status, "status", None) == 1:
        return "Descargando el audio"
    if engine_is_converting(stage, text):
        return "Convirtiendo a audio"
    if "load" in text or "carg" in text:
        return "Cargando el modelo"
    return "Rehaciendo el audio"


def project_generation(request, source, reference, settings) -> GenerationRequest:
    """Contrato único para el preview y el envío tras preparar el material."""
    config = settings.remix
    return GenerationRequest(
        prompt=request.prompt, lyrics=request.lyrics, instrumental=request.instrumental,
        task_type="repaint" if request.scope == "region" else "cover", source_path=str(source),
        reference_path=str(reference) if reference else None,
        duration_seconds=None, bpm=request.bpm, seed=request.seed,
        model=settings.generation.remix_model, audio_format=config.intermediate_format,
        cover_strength=(settings.generation.remix_cover_strength if request.cover_strength is None else request.cover_strength),
        cover_noise_strength=config.cover_noise_strength if request.cover_noise_strength is None else request.cover_noise_strength,
        repaint_start=request.region_start, repaint_end=request.region_end,
        repaint_mode=request.repaint_mode or config.repaint_mode,
        repaint_strength=config.repaint_strength if request.repaint_strength is None else request.repaint_strength,
        repaint_wav_crossfade_sec=config.repaint_wav_crossfade_sec if request.repaint_wav_crossfade_sec is None else request.repaint_wav_crossfade_sec,
        repaint_latent_crossfade_frames=config.repaint_latent_crossfade_frames if request.repaint_latent_crossfade_frames is None else request.repaint_latent_crossfade_frames,
    )


class RemixProjectRuntime:
    def __init__(self, app, music, settings, remix_jobs, separate_jobs, find_audio,
                 busy, remember, public_job, event, save, unique_output, safe_name,
                 carry_ficha, measure_bpm, now, cancelled):
        self.music, self.settings = music, settings
        self.remix_jobs, self.separate_jobs = remix_jobs, separate_jobs
        self.find_audio, self.busy = find_audio, busy
        self.remember, self.public_job, self.event, self.save = remember, public_job, event, save
        self.unique_output, self.safe_name = unique_output, safe_name
        self.carry_ficha, self.measure_bpm, self.now, self.cancelled = carry_ficha, measure_bpm, now, cancelled
        app.add_api_route("/music/remix/capabilities", self.capabilities, methods=["GET"])
        app.add_api_route("/music/remix/project", self.create, methods=["POST"])
        app.add_api_route("/music/remix/preview", self.preview, methods=["POST"])
        app.add_api_route("/music/remix/separate", self.separate, methods=["POST"])

    async def capabilities(self) -> dict:
        remix, generation = self.settings.remix, self.settings.generation
        return {
            "scopes": remix.scopes, "groups": remix.groups, "actions": remix.actions,
            "source_categories": category_catalog(self.settings.source_analysis)["categories"],
            "repaint_modes": remix.repaint_modes, "parameters": remix.parameters,
            "model": generation.remix_model,
            "tasks": [task for task in generation.allowed_tasks if task in generation.remix_tasks],
            "defaults": {
                "cover_strength": generation.remix_cover_strength,
                "cover_noise_strength": remix.cover_noise_strength,
                "repaint_mode": remix.repaint_mode, "repaint_strength": remix.repaint_strength,
                "repaint_wav_crossfade_sec": remix.repaint_wav_crossfade_sec,
                "repaint_latent_crossfade_frames": remix.repaint_latent_crossfade_frames,
                "batch_size": generation.batch_size,
                "transition_seconds": remix.timeline_transition_seconds,
            },
            "timeline": {"max_duration_seconds": generation.max_duration_seconds,
                         "min_duration_seconds": remix.timeline_min_duration_seconds,
                         "min_repeat_seconds": remix.timeline_min_repeat_seconds,
                         "min_groove_confidence": remix.timeline_min_groove_confidence,
                         "max_transition_seconds": remix.timeline_max_transition_seconds},
            "repaint_controls": {
                "strength_modes": ["balanced"],
                "crossfade_editable": False,
                "crossfade_origin": "engine_mode_strength_contract",
                "max_latent_frames": remix.repaint_resolution_max_frames,
                "max_wav_seconds": remix.repaint_resolution_max_wav_seconds,
            },
            "intermediate_format": remix.intermediate_format,
            "limitations": {
                "other": "Puede contener guitarra, piano, sintetizadores, pads y efectos juntos.",
                "transformed_groups": "La separación es estimada; escucha la mezcla para valorar fugas y alineación.",
                "voice": "Cover aproxima o resintetiza la voz; conservar reutiliza su grabación separada.",
                "classification": "La clasificación de la fuente no cambia el prompt ni el plan elegido.",
                "repaint_normalization": ("El motor normaliza el nivel del audio antes de repintar: en los "
                                          "modos conservador y equilibrado la onda fuera del tramo se "
                                          "conserva con su forma, pero el resultado puede llevar un cambio "
                                          "global de nivel. La exportación final aplica el master configurado."),
                "repaint_controls": "La fuerza actúa solo en equilibrado. El motor deriva las transiciones WAV/latentes del modo y la fuerza; los controles crossfade independientes no tienen efecto.",
            },
        }

    def _new_job(self, source: Path, prompt: str) -> dict:
        return {"job_id": uuid.uuid4().hex, "status": "queued", "phase": "En cola",
                "source": source.name, "prompt": prompt, "error": None, "events": [],
                "started": time.monotonic(), "created_at": self.now()}

    def prepare(self, request, source, reference, duration, measured=None) -> dict:
        validate_project(request, duration, self.settings)
        timeline = timeline_plan(request, duration, self.settings, measured)
        config = self.settings.remix
        transform = request.scope != "groups" or "transform" in request.groups.values()
        if transform:
            result = self.music.preview(project_generation(request, source, reference, self.settings))
            for key, field_name in {
                "audio_cover_strength": "cover_strength", "cover_noise_strength": "cover_noise_strength",
                "repaint_mode": "repaint_mode", "repaint_strength": "repaint_strength",
                "repaint_wav_crossfade_sec": "repaint_wav_crossfade_sec",
                "repaint_latent_crossfade_frames": "repaint_latent_crossfade_frames",
            }.items():
                if key in result["provenance"]:
                    result["provenance"][key] = "request" if getattr(request, field_name) is not None else "configuration"
            for key in ("task_type", "audio_format"):
                result["provenance"][key] = "operation_contract"
            result["provenance"]["model"] = "configuration"
            if request.scope == "region":
                for key in ("repaint_wav_crossfade_sec", "repaint_latent_crossfade_frames"):
                    result["provenance"][key] = "engine_mode_strength_contract"
                if (request.repaint_mode or config.repaint_mode) != "balanced":
                    result["provenance"]["repaint_strength"] = "ignored_by_engine_mode"
            if request.scope == "groups":
                # No hay aún un WAV recombinado. No inventar una ruta existente.
                result["effective_parameters"]["src_audio_path"] = None
                result["provenance"]["src_audio_path"] = "pending_derived_material"
        else:
            result = {"effective_parameters": {}, "provenance": {},
                      "warnings": [constraint_rules()["limitation"],
                                   "Operación determinista: no usa motor, batch ni semilla."]}
        result["operations"] = {
            "scope": request.scope, "source": source.name,
            "source_kind": request.source_kind,
            "source_duration_seconds": duration, "groups": request.groups,
            "gains_db": {group: request.gains_db.get(group, 0.0)
                         for group, action in (request.groups or {}).items() if action != "remove"},
            "separation_required": request.scope == "groups",
            "engine_required": transform,
            "timeline": timeline,
            "preserved_groups_processing": "common_pcm_tempo_and_shared_repetition" if request.scope == "groups" else None,
            "export": {"format": "mp3", "bitrate": config.export_bitrate,
                       "sample_rate": config.sample_rate, "peak_limit_dbfs": config.peak_limit_dbfs},
        }
        result["pending_material"] = ([{
            "parameter": "src_audio_path", "path": None,
            "source": source.name,
            "groups": [group for group, action in request.groups.items() if action == "transform"],
            "operation": "Separación, tempo común y mezcla PCM de los grupos a transformar",
        }] if transform and request.scope == "groups" else [])
        if request.scope == "region":
            result["warnings"].append("El motor normaliza el nivel global antes de repintar; el master final puede cambiar el nivel fuera del intervalo.")
            if (request.repaint_mode or config.repaint_mode) == "aggressive":
                result["warnings"].append("El modo agresivo no garantiza conservar el audio fuera del intervalo.")
        if request.scope == "groups":
            result["warnings"].append("La separación es estimada: acompañamiento agrupa instrumentos; la mezcla transformada depende de material aún por preparar.")
            if timeline["tempo_ratio"] != 1:
                result["warnings"].append("El BPM común procesa también las grabaciones conservadas, sin cambiar el tono. El BPM original medido se puede revisar.")
        if request.scope == "full" and request.bpm:
            result["warnings"].append("En canción completa se mide cada variante y se ajusta después su tempo sin cambiar el tono. La duración natural y la parte a repetir se calculan tras generar; una medición incierta produce un error.")
            result["pending_material"].append({"parameter": "variant_tempo", "path": None,
                "operation": "Medir cada variante, ajustar su tempo por DSP y verificar el BPM resultante",
                "derived_fields": ["natural_duration_seconds", "tempo_ratio", "mapped_repeat_start", "mapped_repeat_end"]})
        if request.scope == "region" and request.bpm:
            result["warnings"].append("En Tramo el BPM es orientativo: condiciona al motor, sin ajuste posterior del audio.")
        if timeline["method"] == "repeat_crossfade":
            result["warnings"].append("La ampliación repite material con fundidos; no compone partes nuevas.")
        return result

    async def _prepare(self, request):
        source = self.find_audio(request.source_name, request.source_kind)
        reference = self.find_audio(request.reference_name, request.reference_kind) if request.reference_name else None
        digest = await asyncio.to_thread(source_digest, source)
        def duration_seconds():
            with source.open("rb") as stream:
                return len(AudioSegment.from_file(stream, format=source.suffix.lstrip("."))) / 1000
        duration = await asyncio.to_thread(duration_seconds)
        try:
            validate_project(request, duration, self.settings)
            measured = (await asyncio.to_thread(self.measure_bpm, source)
                        if request.scope == "groups" and request.bpm is not None and request.source_bpm is None else None)
            prepared = self.prepare(request, source, reference, duration, measured)
            if digest != await asyncio.to_thread(source_digest, source):
                raise ValueError("La fuente cambió durante la vista previa; vuelve a seleccionar el audio")
            prepared["operations"]["source_digest"] = digest
        except (ValueError, MusicEngineError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return source, reference, duration, prepared

    async def preview(self, request: RemixProjectRequest) -> dict:
        return (await self._prepare(request))[3]

    async def create(self, request: RemixProjectRequest, background_tasks: BackgroundTasks) -> dict:
        from source_understanding import completed_analysis_for

        source, reference, duration, prepared = await self._prepare(request)
        # Se comprueba tras el único await de admisión, antes de registrar el job.
        if reason := self.busy():
            raise HTTPException(status_code=409, detail=reason)
        job = self._new_job(source, request.prompt)
        job["project"] = request.model_dump()
        job["source_analysis"] = completed_analysis_for(source)
        job["duration_seconds"] = duration
        job.update(effective_parameters=prepared["effective_parameters"],
                   provenance=prepared["provenance"], warnings=prepared["warnings"],
                   operations=prepared["operations"], pending_material=prepared["pending_material"])
        self.remember(self.remix_jobs, job["job_id"], job)
        self.save()
        background_tasks.add_task(self.run, job, source, reference, request, duration)
        return {"job_id": job["job_id"], "status": job["status"]}

    async def separate(self, request: SeparateGroupsRequest, background_tasks: BackgroundTasks) -> dict:
        source = self.find_audio(request.file_name, request.source_kind)
        if reason := self.busy():
            raise HTTPException(status_code=409, detail=reason)
        job = self._new_job(source, source.name)
        job["source_kind"] = request.source_kind
        self.remember(self.separate_jobs, job["job_id"], job)
        self.save()
        background_tasks.add_task(self.run_separate, job, source)
        return {"job_id": job["job_id"], "status": "queued"}

    async def run_separate(self, job: dict, source: Path) -> None:
        job["compute_active"] = True
        try:
            async with COMPUTE_LOCK:
                self.cancelled(job)
                job["status"] = "running"
                self.event(job, "Separando los cuatro grupos del original")
                digest = await asyncio.to_thread(source_digest, source)
                result = await self._groups(source, job, self.settings.outputs_dir,
                                            f"grupos-{job['job_id'][:12]}")
                self.cancelled(job)
                if digest != await asyncio.to_thread(source_digest, source):
                    raise ValueError("La fuente cambió durante la separación; vuelve a separar el original")
                job.update(status="succeeded", phase="Grupos listos", result=result,
                           source_digest=digest,
                           completed_at=self.now(), elapsed_seconds=time.monotonic() - job["started"])
        except Exception as exc:
            self._fail(job, exc)
        finally:
            job["compute_active"] = False
            self.save()

    async def _groups(self, source, job, out_dir, stem):
        return await asyncio.to_thread(
            SeparatorService.separate_groups, source, out_dir, stem,
            self.settings.remix, lambda: bool(job.get("cancelled")),
        )

    async def _replace_unmeasured_variant(self, job, request, work, index, path,
                                          engine_source, reference, natural_duration,
                                          draw, config):
        """Pide una sola muestra nueva y archiva la que no se pudo comprobar."""
        generation = project_generation(request, engine_source, reference, self.settings)
        seed_max = config.parameters["seed"]["max"]
        seed = replacement_request_seed(request.seed, self.settings.generation.batch_size, draw, seed_max)
        generation.batch_size = 1
        generation.seed = seed
        generation.use_random_seed = seed is None
        payload = self.music.build_payload(generation)

        def update(status):
            self.cancelled(job)
            job["status"] = "running"
            job["engine_progress"] = status.progress
            job["progress_ratio"] = status.moving_progress()
            job["engine_progress_text"] = status.progress_text or ""
            job["phase"] = _visible_phase(status)

        job["engine_active"] = True
        try:
            task_id, _detail = await self.music.submit(generation)
            ids = job.setdefault("engine_task_ids", [])
            current = job.get("engine_task_id")
            if current and current not in ids:
                ids.append(current)
            job["engine_task_id"] = task_id
            ids.append(task_id)
            self.save()
            final = await self.music.wait(task_id, on_update=update)
        finally:
            job["engine_active"] = False
        self.cancelled(job)
        if not final.succeeded:
            raise MusicEngineError(final.error or "El motor terminó sin audio válido")
        tracks = [item for item in final.tracks if item.file]
        if len(tracks) != 1:
            raise MusicEngineError(f"El motor devolvió {len(tracks)} variantes; se pidió 1")
        rejected = work / f"variante-{index + 1}-no-verificable-{draw}.wav"
        path.replace(rejected)
        await self.music.download(tracks[0].file, path)
        seconds = await self.music.verify_audio(path) / 1000
        if abs(seconds - natural_duration) > config.duration_tolerance_seconds:
            raise MusicEngineError(
                f"El motor cambió la duración: {seconds:g}s frente a {natural_duration:g}s; "
                "no se mezclan timelines distintas")
        return path, tracks[0], payload

    async def _measured_full_variant(self, job, request, work, index, path, track,
                                     engine_source, reference, natural_duration,
                                     source_duration, config):
        """Mide, ajusta y comprueba. Si no se puede medir, pide otra muestra."""
        retries = full_groove_retries(config)
        state = {"path": path, "track": track, "payload": None, "plan": None, "processing": None}

        async def measure():
            self.cancelled(job)
            self.event(job, f"Midiendo el BPM de la variante {index + 1}")
            return await asyncio.to_thread(required_measured_tempo, state["path"])

        async def adjust(measured):
            self.cancelled(job)
            engine_duration = await self.music.verify_audio(state["path"]) / 1000
            plan = full_variant_plan(request, source_duration, engine_duration, self.settings, measured)
            adjusted = work / f"tempo-variante-{index + 1}.wav"
            self.event(job, f"Ajustando el BPM de la variante {index + 1} sin cambiar el tono")
            processing = await asyncio.to_thread(
                MixerService.tempo_audio, state["path"], adjusted, plan["tempo_ratio"],
                plan["natural_duration_seconds"], config)
            processing.update(input_path=str(state["path"]), output_path=str(adjusted))
            post = await asyncio.to_thread(required_measured_tempo, adjusted)
            verify_requested_tempo(post, request.bpm, config, "después del ajuste DSP")
            plan.update(beat_clock_bpm=post["bpm_measured"],
                        beat_clock_origin="adjusted_audio_measurement")
            state["plan"] = plan
            state["processing"] = processing
            return post

        async def replace(draw, exc):
            if str(exc).startswith("Audio demasiado corto"):
                self.event(job, f"La variante {index + 1} queda demasiado corta para comprobar el tempo; "
                           "se pide otra muestra")
            else:
                self.event(job, f"La variante {index + 1} no tiene un pulso medible; se pide otra muestra")
            state["path"], state["track"], state["payload"] = await self._replace_unmeasured_variant(
                job, request, work, index, state["path"], engine_source, reference,
                natural_duration, draw, config)

        measured, verified, draws = await accept_verified_draw(measure, adjust, replace, retries)
        return (state["path"], state["track"], measured, state["plan"], draws, state["payload"],
                verified, state["processing"])

    def _fail(self, job: dict, error: Exception) -> None:
        logger.error(f"Proyecto/separación {job['job_id']} falló: {error}")
        job.update(status="failed", phase="Cancelado" if job.get("cancelled") else "Error",
                   error="Cancelado por el usuario" if job.get("cancelled") else str(error),
                   completed_at=self.now(), elapsed_seconds=time.monotonic() - job["started"])

    async def run(self, job, source, reference, request, duration) -> None:
        config = self.settings.remix
        work = self.settings.outputs_dir / "_remix" / job["job_id"]
        work.mkdir(parents=True, exist_ok=True)
        originals = {}
        targets = []
        job["compute_active"] = True
        try:
            async with COMPUTE_LOCK:
                self.cancelled(job)
                job["status"] = "running"
                digest = await asyncio.to_thread(source_digest, source)
                if digest != job["operations"]["source_digest"]:
                    raise ValueError("La fuente cambió después de solicitar el remix; vuelve a seleccionar el audio")
                job["source_digest"] = digest
                plan = job["operations"]["timeline"]
                natural_duration = plan["natural_duration_seconds"] or duration
                engine_source = source
                if request.scope == "groups":
                    self.event(job, "Separando los grupos del original")
                    for item in reversed(list(self.separate_jobs.values())):
                        if (item.get("status") != "succeeded" or item.get("source_digest") != digest
                                or not isinstance(item.get("result"), dict)):
                            continue
                        try:
                            originals = await asyncio.to_thread(SeparatorService.validate_groups,
                                item["result"], self.settings.outputs_dir, duration, config)
                        except (ValueError, RuntimeError, OSError) as exc:
                            logger.warning(f"Separación cacheada rechazada: {exc}")
                            continue
                        job["operations"]["separation_origin"] = "validated_cache"
                        break
                    if not originals:
                        result = await self._groups(source, job, work, "original")
                        originals = {item["id"]: work / item["file_name"] for item in result["groups"]}
                        job["operations"]["separation_origin"] = "new"
                    job["operations"]["separation_signature"] = SeparatorService.signature(config)
                    self.cancelled(job)
                    if plan["tempo_ratio"] != 1:
                        self.event(job, "Cambiando el BPM de todas las pistas juntas")
                        originals = await asyncio.to_thread(MixerService.tempo_groups, originals, work,
                            plan["tempo_ratio"], natural_duration, config)
                        self.cancelled(job)
                    job["operations"]["prepared_groups"] = {key: str(path) for key, path in originals.items()}
                    targets = [key for key, action in request.groups.items() if action == "transform"]
                    if targets:
                        engine_source = work / "material-a-transformar.wav"
                        await asyncio.to_thread(MixerService.mix_groups,
                                                [(originals[key], 0.0) for key in targets],
                                                engine_source, natural_duration, config.sample_rate)
                    job["preserved_groups"] = [key for key, action in request.groups.items() if action == "keep"]
                if digest != await asyncio.to_thread(source_digest, source):
                    raise ValueError("La fuente cambió durante la preparación; vuelve a solicitar el remix")
                self.cancelled(job)
                generated = []
                if request.scope != "groups" or targets:
                    task = "repaint" if request.scope == "region" else "cover"
                    self.event(job, f"Transformando el audio original con {task}")
                    generation = project_generation(request, engine_source, reference, self.settings)
                    job["effective_parameters"] = self.music.build_payload(generation)
                    if request.scope == "groups":
                        job["provenance"]["src_audio_path"] = "derived_material"
                    job["pending_material"] = ([item for item in job["pending_material"]
                                                if item.get("parameter") == "variant_tempo"])

                    def update(status):
                        self.cancelled(job)
                        job["status"] = "running"
                        job["engine_progress"] = status.progress
                        job["progress_ratio"] = status.moving_progress()
                        job["engine_progress_text"] = status.progress_text or ""
                        job["phase"] = _visible_phase(status)

                    job["engine_active"] = True
                    try:
                        task_id, _ = await self.music.submit(generation)
                        job["engine_task_id"] = task_id
                        self.save()
                        final = await self.music.wait(task_id, on_update=update)
                    finally:
                        job["engine_active"] = False
                    self.cancelled(job)
                    if not final.succeeded:
                        raise MusicEngineError(final.error or "El motor terminó sin audio válido")
                    for index, track in enumerate(item for item in final.tracks if item.file):
                        path = work / f"variante-{index + 1}.wav"
                        await self.music.download(track.file, path)
                        seconds = await self.music.verify_audio(path) / 1000
                        if abs(seconds - natural_duration) > config.duration_tolerance_seconds:
                            raise MusicEngineError(f"El motor cambió la duración: {seconds:g}s frente a {natural_duration:g}s; no se mezclan timelines distintas")
                        generated.append((path, track))
                    if len(generated) != self.settings.generation.batch_size:
                        raise MusicEngineError(f"El motor devolvió {len(generated)} variantes; se pidieron {self.settings.generation.batch_size}")
                else:
                    generated = [(None, None)]
                exported, metadata, publications = [], [], []
                for index, (path, track) in enumerate(generated):
                    self.cancelled(job)
                    timeline = path
                    variant_plan = dict(plan)
                    tempo_before = None
                    tempo_after_adjust = None
                    tempo_processing = None
                    groove_replacements = 0
                    replacement_parameters = None
                    if request.scope == "full" and request.bpm is not None:
                        (path, track, tempo_before, variant_plan, groove_replacements,
                         replacement_parameters, tempo_after_adjust, tempo_processing) = (
                            await self._measured_full_variant(
                                job, request, work, index, path, track, engine_source, reference,
                                natural_duration, duration, config))
                        timeline = Path(tempo_processing["output_path"])
                    if request.scope == "groups":
                        transformed = {}
                        targets = [key for key, action in request.groups.items() if action == "transform"]
                        if path and len(targets) == 1:
                            self.event(job, f"Separando grupos transformados de la variante {index + 1}")
                            result = await self._groups(path, job, work, f"transformada-{index + 1}")
                            self.cancelled(job)
                            separated = {item["id"]: work / item["file_name"] for item in result["groups"]}
                            track_path = work / f"pista-transformada-{index + 1}.wav"
                            mounted = await asyncio.to_thread(
                                MixerService.render_single_transform, path, separated, request.groups,
                                originals[targets[0]], track_path, config)
                            transformed[targets[0]] = track_path
                            warning = mounted.get("warning")
                            if warning and warning not in job.setdefault("warnings", []):
                                job["warnings"].append(warning)
                            self.event(job, f"Montando la pista transformada de la variante {index + 1}")
                        elif path:
                            self.event(job, f"Separando grupos transformados de la variante {index + 1}")
                            result = await self._groups(path, job, work, f"transformada-{index + 1}")
                            self.cancelled(job)
                            transformed = {item["id"]: work / item["file_name"] for item in result["groups"]}
                        parts = [(originals[key] if action == "keep" else transformed[key], request.gains_db.get(key, 0.0))
                                 for key, action in request.groups.items() if action != "remove"]
                        timeline = work / f"mezcla-{index + 1}.wav"
                        self.event(job, f"Recombinando la variante {index + 1} sobre la timeline original")
                        await asyncio.to_thread(MixerService.mix_groups, parts, timeline, natural_duration, config.sample_rate)
                    self.cancelled(job)
                    arrangement = {"method": "original", "repetitions": 0,
                                   "duration_seconds": variant_plan["natural_duration_seconds"], "transition_seconds": 0.0}
                    if variant_plan["method"] == "repeat_crossfade":
                        self.event(job, f"Ampliando la variante {index + 1} con partes y transiciones")
                        extended = work / f"arreglo-{index + 1}.wav"
                        arrangement = await asyncio.to_thread(MixerService.extend_timeline, timeline, extended, variant_plan, config)
                        timeline = extended
                        self.cancelled(job)
                    stem = self.safe_name(request.output_name or f"{source.stem}-remix", "remix")
                    staged_output = work / f"exportada-{index + 1}.mp3"
                    self.event(job, f"Exportando la variante {index + 1}")
                    mastering = await asyncio.to_thread(MixerService.export_remix, timeline, staged_output, config)
                    self.cancelled(job)
                    final_seconds = await self.music.verify_audio(staged_output) / 1000
                    if abs(final_seconds - variant_plan["target_duration_seconds"]) > config.duration_tolerance_seconds:
                        raise ValueError("La duración final no corresponde al arreglo solicitado")
                    if request.scope == "full" and request.bpm is not None:
                        measured = await asyncio.to_thread(
                            required_measured_tempo, staged_output, arrangement, config)
                    else:
                        measured = await asyncio.to_thread(self.measure_bpm, staged_output)
                    self.cancelled(job)
                    if request.scope == "full" and request.bpm is not None:
                        verify_requested_tempo(measured, request.bpm, config, "después del arreglo y exportación")
                    variant = {"file_name": None, "intermediate_path": str(timeline),
                               "seed": track.seed if track else None,
                               "seed_origin": track.seed_origin if track else "not_applicable",
                               "engine_metas": track.metas if track else {},
                               "duration_seconds": final_seconds, "arrangement": arrangement,
                               "timeline": variant_plan, "tempo_measured": measured,
                               "groove_replacements": groove_replacements,
                               "replacement_parameters": replacement_parameters,
                               "tempo_before": tempo_before, "tempo_after_adjust": tempo_after_adjust,
                               "tempo_processing": tempo_processing, **mastering}
                    asked_seed = request.seed if track else None
                    if groove_replacements and track:
                        asked_seed = replacement_request_seed(
                            request.seed, self.settings.generation.batch_size, groove_replacements,
                            config.parameters["seed"]["max"])
                    variant_operations = {**job["operations"], "timeline": variant_plan,
                                          "tempo_before": tempo_before, "tempo_processing": tempo_processing,
                                          "tempo_after_adjust": tempo_after_adjust,
                                          "tempo_after": measured,
                                          "groove_replacements": groove_replacements,
                                          "replacement_parameters": replacement_parameters}
                    ficha = dict(prompt=request.prompt, project=request.model_dump(),
                                 effective_parameters=job.get("effective_parameters"),
                                 source_analysis=job.get("source_analysis"), source_digest=digest,
                                 mastering=mastering, duration_seconds=final_seconds, bpm=request.bpm,
                                 operations=variant_operations, arrangement=arrangement,
                                 seed=variant["seed"], seed_origin=variant["seed_origin"],
                                 seed_requested=asked_seed,
                                 groove_replacements=groove_replacements,
                                 replacement_parameters=replacement_parameters,
                                 provenance=job.get("provenance"), **(measured or {}))
                    publications.append((staged_output, stem, ficha, variant))
                    metadata.append(variant)
                self.cancelled(job)
                # Todas las variantes han pasado sus verificaciones. No hay
                # awaits entre el checkpoint y la publicación del lote.
                for staged_output, stem, ficha, variant in publications:
                    output = self.unique_output(stem, ".mp3")
                    staged_output.replace(output)
                    self.carry_ficha(source, output, "remix-project", **ficha)
                    variant["file_name"] = output.name
                    exported.append(output.name)
                job["operations"]["variant_timelines"] = [item["timeline"] for item in metadata]
                job["pending_material"] = []
                job.update(status="succeeded", phase="Listo", completed_at=self.now(),
                           elapsed_seconds=time.monotonic() - job["started"],
                           result={"mix": exported[0], "variants": exported, "metadata": metadata,
                                   "scope": request.scope, "groups": request.groups,
                                   "source": source.name, "source_kind": request.source_kind,
                                   "source_classification": request.source_classification,
                                   "classification_origin": request.classification_origin,
                                   "source_analysis": job.get("source_analysis"),
                                   "duration_seconds": metadata[0]["duration_seconds"],
                                   "source_duration_seconds": duration, "timeline": metadata[0]["timeline"],
                                   "preserved_groups": job.get("preserved_groups", [])})
        except Exception as exc:
            self._fail(job, exc)
        finally:
            job["compute_active"] = False
            self.save()
