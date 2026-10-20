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
from mixer_service import MIN_PHASE_SHIFT_MS, MixerService, plan_alignment, run_ffmpeg
from music_service import GenerationRequest, MusicEngineError, engine_is_converting
from prompt_constraints import rules as constraint_rules, validate_explicit_constraints
from prompt_style import style_caption
from style_translator import style_for_engine
from separator_service import SeparatorService
from source_understanding import category_catalog
from remix_recovery import (RECEIPT_NAME, atomic_json, build_receipt,
                            receipt_digest, validate_receipt, work_directory)

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
        raise ValueError("Indica inicio y fin del recorte")
    if request.repeat_start is not None and (
            not math.isfinite(request.repeat_start) or not math.isfinite(request.repeat_end)
            or not 0 <= request.repeat_start < request.repeat_end <= duration):
        raise ValueError("El recorte debe estar dentro de la canción original")
    if request.transition_seconds is not None and (
            not math.isfinite(request.transition_seconds)
            or not 0 < request.transition_seconds <= config.timeline_max_transition_seconds):
        raise ValueError("La transición debe ser positiva y estar dentro del límite configurado")
    if any(value is not None for value in (request.repeat_start, request.repeat_end, request.transition_seconds)) and request.duration_seconds is None:
        raise ValueError("El recorte requiere una duración mayor que la canción")
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
        marked = request.repeat_start is not None
        return {"source_duration_seconds": duration, "natural_duration_seconds": None,
                "target_duration_seconds": request.duration_seconds, "tempo_ratio": None,
                "source_bpm": None, "source_bpm_origin": "pending_generated_measurement",
                "bpm_measured": None, "bpm_confidence": None, "target_bpm": request.bpm,
                "repeat_start": request.repeat_start if marked else None,
                "repeat_end": request.repeat_end if marked else None,
                "mapped_repeat_start": None, "mapped_repeat_end": None,
                "transition_seconds": 0.0,
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
        raise ValueError("El recorte solo se aplica al alargar la canción")
    marked = request.repeat_start is not None
    start = request.repeat_start if marked else None
    end = request.repeat_end if marked else None
    mapped_start = mapped_end = None
    if marked:
        mapped_start, mapped_end = start / ratio, end / ratio
        if expanding and mapped_end - mapped_start < config.timeline_min_repeat_seconds:
            raise ValueError("El recorte es demasiado corto para usarlo como sample")
    return {"source_duration_seconds": duration, "natural_duration_seconds": natural,
            "target_duration_seconds": target, "tempo_ratio": ratio,
            "source_bpm": source_bpm, "source_bpm_origin": origin,
            "bpm_measured": measured.get("bpm_measured"), "bpm_confidence": measured.get("bpm_confidence"),
            "target_bpm": request.bpm, "repeat_start": start, "repeat_end": end,
            "beat_clock_bpm": request.bpm if request.scope == "groups" else None,
            "beat_clock_origin": "requested_common_tempo" if request.scope == "groups" and request.bpm else "not_required",
            "mapped_repeat_start": mapped_start, "mapped_repeat_end": mapped_end,
            "transition_seconds": 0.0,
            "method": "continue_bed" if expanding else "original",
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
                repeat_start=request.repeat_start, repeat_end=request.repeat_end)
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


def groups_tempo_ratio(measured_bpm: float, requested_bpm: float, config) -> float | None:
    """Relación de un solo atempo para que la mezcla cumpla el BPM pedido.

    None si la medición ya cae dentro de la tolerancia. No usa un BPM fijo
    ni convierte una lectura incierta: el medidor tiene que haber devuelto
    un número antes de llamar aquí.
    """
    if (isinstance(measured_bpm, bool) or not isinstance(measured_bpm, (int, float))
            or not math.isfinite(measured_bpm) or measured_bpm <= 0
            or isinstance(requested_bpm, bool) or not isinstance(requested_bpm, (int, float))
            or not math.isfinite(requested_bpm) or requested_bpm <= 0):
        raise ValueError("No hay un BPM medido y pedido para cumplir el tempo")
    tolerance = config.tempo_verify_tolerance_bpm
    if isinstance(tolerance, bool) or not isinstance(tolerance, (int, float)) or not math.isfinite(tolerance) or tolerance < 0:
        raise ValueError("La tolerancia de verificación BPM debe ser finita y no negativa")
    if abs(float(measured_bpm) - float(requested_bpm)) <= tolerance:
        return None
    return float(requested_bpm) / float(measured_bpm)


def whole_song_repeat_plan(plan: dict, config) -> dict | None:
    """Abre la repetición a la canción entera.

    None si el tramo elegido ya la cubre o el plan no tiene duración natural.
    No cambia el tempo ni la duración pedida, y no convierte una lectura
    incierta en un BPM.
    """
    natural = plan.get("natural_duration_seconds")
    start = plan.get("mapped_repeat_start")
    end = plan.get("mapped_repeat_end")
    tolerance = config.duration_tolerance_seconds
    if (isinstance(natural, bool) or not isinstance(natural, (int, float)) or not math.isfinite(natural) or natural <= 0
            or isinstance(start, bool) or not isinstance(start, (int, float)) or not math.isfinite(start)
            or isinstance(end, bool) or not isinstance(end, (int, float)) or not math.isfinite(end)
            or end <= start
            or isinstance(tolerance, bool) or not isinstance(tolerance, (int, float))
            or not math.isfinite(tolerance) or tolerance < 0):
        return None
    if float(end) - float(start) >= float(natural) - tolerance:
        return None
    updated = dict(plan)
    updated["mapped_repeat_start"] = 0.0
    updated["mapped_repeat_end"] = float(natural)
    source = plan.get("source_duration_seconds")
    if (not isinstance(source, bool) and isinstance(source, (int, float))
            and math.isfinite(source) and source > 0):
        updated["repeat_start"] = 0.0
        updated["repeat_end"] = float(source)
    return updated


def uncertain_extension_fallback(exc: BaseException, scope: str, plan: dict | None,
                                 bed_measured, config) -> dict | None:
    """Medición de la base que sigue acreditando el tempo de una ampliación incierta [R17].

    None si el trabajo debe seguir fallando: el error no es de groove, el
    ámbito no es Por pistas, el método no continúa la base o la base no
    tiene una medición fiable. No convierte una lectura incierta en un
    BPM: devuelve la medición ya verificada de la base de antes de
    continuar, que es la que el detector sí midió.
    """
    if not audio_has_no_usable_groove(exc) or scope != "groups":
        return None
    if not plan or plan.get("method") != "continue_bed":
        return None
    measured = bed_measured or {}
    try:
        require_measured_tempo(measured, config, "de la base antes de continuar")
    except ValueError:
        return None
    return measured


def uncertain_mix_notice(exc: BaseException, requested_bpm) -> str | None:
    """Aviso de entrega cuando la mezcla de grupos no tiene pulso medible.

    Decisión del usuario, 2026-10-19: si tras intentar cuadrar el bombo la
    mezcla sigue sin ritmo fiable, el trabajo se entrega y este aviso dice
    que su tempo no se ajustó al pedido ni queda garantizado. None si el
    error no es de groove (configuración, BPM medido fuera de tolerancia) o
    si no se pidió BPM: esos casos siguen fallando como antes. No convierte
    una lectura incierta en un BPM ni afirma que el audio no sufrió ningún
    procesado: el tempo común de Por pistas y el cuadre de bombo pueden haber
    corrido antes; lo que no se hizo es ajustar la mezcla al BPM pedido.
    """
    if requested_bpm is None or not audio_has_no_usable_groove(exc):
        return None
    return (f"El ritmo de la mezcla no se pudo medir con fiabilidad; su tempo no se "
            f"ajustó al BPM pedido. El BPM pedido ({requested_bpm:g}) no queda garantizado.")


def mark_uncertain_mix_tempo(plan: dict, exc: BaseException) -> None:
    """Deja escrito en el plan que el tempo de la mezcla no está acreditado."""
    plan["beat_clock_bpm"] = None
    plan["beat_clock_origin"] = "unverified_uncertain_groove"
    plan["tempo_verification"] = "uncertain_at_mix"
    plan["tempo_verification_error"] = str(exc)


def _shift_audio_to_kick(source: Path, output: Path, delay_ms: float) -> Path:
    """Coloca el golpe en el instante del bombo de referencia. Un desfase mínimo no se toca."""
    if abs(delay_ms) < MIN_PHASE_SHIFT_MS:
        return source
    if delay_ms > 0:
        run_ffmpeg(
            ["-i", str(source), "-af", f"adelay=delays={delay_ms:.1f}:all=1",
             "-c:a", "pcm_f32le", "-f", "wav", str(output)],
            output,
        )
    else:
        cut = abs(delay_ms) / 1000.0
        run_ffmpeg(
            ["-i", str(source), "-af", f"atrim=start={cut:.6f},asetpts=PTS-STARTPTS",
             "-c:a", "pcm_f32le", "-f", "wav", str(output)],
            output,
        )
    return output


def square_mix_on_original_kick(parts, movable, reference_drums: Path, new_drums: Path,
                                output: Path, work: Path, index: int, duration: float, config):
    """Cuadra la música nueva con el bombo original y rehace la mezcla.

    None si alguno de los dos bombos no se puede medir o el salto de tempo
    no es seguro. No convierte una lectura incierta en un BPM: el llamador
    vuelve a medir la mezcla.
    """
    if not movable:
        return None
    work.mkdir(parents=True, exist_ok=True)
    try:
        reference = detect_groove(reference_drums)
        fresh = detect_groove(new_drums)
    except (ValueError, FileNotFoundError, OSError):
        return None
    if plan_alignment(reference, fresh) is None:
        return None
    ratio = groups_tempo_ratio(fresh["bpm"], reference["bpm"], config)
    prepared = {}
    measure_paths = list(dict.fromkeys([*movable, new_drums]))
    for path in measure_paths:
        if ratio is None:
            prepared[path] = path
            continue
        seconds = MixerService.inspect_pcm(path)["duration_seconds"]
        dest = work / f"cuadre-tempo-{index}-{path.stem}.wav"
        MixerService.tempo_audio(path, dest, ratio, seconds / ratio, config)
        prepared[path] = dest
    try:
        aligned_kick = detect_groove(prepared[new_drums])
    except (ValueError, FileNotFoundError, OSError):
        return None
    alignment = plan_alignment(reference, aligned_kick)
    if alignment is None:
        return None
    delay = float(alignment["delay_ms"])
    shifted = {}
    for path in dict.fromkeys(movable):
        shifted[path] = _shift_audio_to_kick(
            prepared[path], work / f"cuadre-fase-{index}-{path.stem}.wav", delay)
    mixed = [(shifted.get(path, path), gain) for path, gain in parts]
    MixerService.mix_groups(mixed, output, duration, config.sample_rate)
    return {"timeline": output, "delay_ms": round(delay, 1), "tempo_ratio": ratio}


def apply_groups_mix_tempo(plan: dict, mix_seconds: float, ratio: float,
                           requested_duration: float | None, config) -> dict:
    """Timeline después del atempo de la mezcla, con la duración que se pidió.

    La relación es la de ese atempo. Si no hay duración pedida, el resultado
    es la mezcla ya ajustada, sin rellenarla hasta la duración anterior.
    Si la mezcla ajustada pasa de la duración pedida, se dice el mínimo y no
    se recorta. Si cabe, se conserva el objetivo y se amplía solo si falta.
    """
    start, end = plan.get("mapped_repeat_start"), plan.get("mapped_repeat_end")
    marked = start is not None or end is not None
    if (isinstance(mix_seconds, bool) or not isinstance(mix_seconds, (int, float))
            or not math.isfinite(mix_seconds) or mix_seconds <= 0
            or isinstance(ratio, bool) or not isinstance(ratio, (int, float))
            or not math.isfinite(ratio) or ratio <= 0):
        raise ValueError("No hay una duración y una relación válidas para el tempo de la mezcla")
    if marked and (isinstance(start, bool) or not isinstance(start, (int, float)) or not math.isfinite(start)
                   or isinstance(end, bool) or not isinstance(end, (int, float)) or not math.isfinite(end)
                   or end <= start):
        raise ValueError("No hay una duración y una relación válidas para el tempo de la mezcla")
    updated = dict(plan)
    adjusted = float(mix_seconds) / float(ratio)
    scale = adjusted / float(mix_seconds)
    if marked:
        updated["mapped_repeat_start"] = float(start) * scale
        updated["mapped_repeat_end"] = float(end) * scale
    updated["natural_duration_seconds"] = adjusted
    updated["tempo_ratio"] = float(ratio)
    updated["tempo_method"] = "measured_pcm_atempo"
    if requested_duration is None:
        updated["target_duration_seconds"] = adjusted
        updated["method"] = "original"
        updated["transition_seconds"] = 0.0
        return updated
    if (isinstance(requested_duration, bool) or not isinstance(requested_duration, (int, float))
            or not math.isfinite(requested_duration) or requested_duration <= 0):
        raise ValueError("La duración objetivo no es válida")
    if adjusted > float(requested_duration):
        minimum = math.ceil(adjusted)
        raise ValueError("La duración objetivo debe ser igual o mayor que la canción al tempo elegido: "
                         f"mínimo {minimum} s ({minimum // 60}:{minimum % 60:02d})")
    updated["target_duration_seconds"] = float(requested_duration)
    updated["transition_seconds"] = 0.0
    if float(requested_duration) > adjusted:
        updated["method"] = "continue_bed"
        if marked:
            span = updated["mapped_repeat_end"] - updated["mapped_repeat_start"]
            if span < config.timeline_min_repeat_seconds:
                raise ValueError("El recorte es demasiado corto para usarlo como sample")
    else:
        updated["method"] = "original"
    return updated


def continuation_limits(config) -> tuple[float, float, int, int]:
    """Mínimo, máximo, tope de trozos y lote de una continuación."""
    minimum = config.continuation_min_seconds
    maximum = config.continuation_max_seconds
    chunks = config.continuation_max_chunks
    batch = config.continuation_batch_size
    if any(isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0
           for value in (minimum, maximum)):
        raise ValueError("La continuación necesita un tramo mínimo y máximo positivos")
    if float(maximum) < float(minimum):
        raise ValueError("El tramo máximo de la continuación tiene que cubrir el mínimo")
    if isinstance(chunks, bool) or not isinstance(chunks, int) or chunks < 1:
        raise ValueError("El número de trozos de la continuación tiene que ser un entero positivo")
    if isinstance(batch, bool) or not isinstance(batch, int) or batch < 1:
        raise ValueError("El lote de la continuación tiene que ser un entero positivo")
    return float(minimum), float(maximum), chunks, batch


def continuation_spans(bed_seconds: float, target_seconds: float, config) -> list[dict]:
    """Trozos que alargan la base hasta la duración pedida.

    Cada trozo empieza donde acaba el anterior. El motor instalado genera
    el final; no se rellena repitiendo el recorte.
    """
    minimum, maximum, chunk_limit, _batch = continuation_limits(config)
    if any(isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0
           for value in (bed_seconds, target_seconds)):
        raise ValueError("La continuación necesita la duración de la base y la duración pedida")
    spans = []
    cursor = float(bed_seconds)
    while cursor < float(target_seconds):
        if len(spans) >= chunk_limit:
            raise ValueError("La duración pedida no cabe en los trozos de continuación configurados")
        remaining = float(target_seconds) - cursor
        added = remaining if remaining >= minimum else minimum
        if added > maximum:
            added = maximum
        spans.append({"start": cursor, "end": cursor + added})
        cursor += added
    return spans


def sample_window(plan: dict, bed_seconds: float, config) -> dict | None:
    """Recorte marcado dentro de la base ya creada. None si no hay recorte."""
    start, end = plan.get("mapped_repeat_start"), plan.get("mapped_repeat_end")
    if start is None and end is None:
        return None
    tolerance = config.duration_tolerance_seconds
    if (isinstance(start, bool) or not isinstance(start, (int, float)) or not math.isfinite(start)
            or isinstance(end, bool) or not isinstance(end, (int, float)) or not math.isfinite(end)
            or end <= start or start < 0
            or not isinstance(bed_seconds, (int, float)) or isinstance(bed_seconds, bool)
            or not math.isfinite(bed_seconds) or end > float(bed_seconds) + tolerance):
        raise ValueError("El recorte no cabe en la base creada")
    return {"start": float(start), "end": min(float(end), float(bed_seconds))}


def continuation_generation(request, bed: Path, span: dict, seed, settings) -> GenerationRequest:
    """Repaint del final de la base ya creada, con el mismo estilo y el mismo BPM.

    audio_duration queda en la duración del archivo. El final pedido, por
    delante del archivo, es el silencio que el motor rellena.
    """
    if not style_caption(request.prompt):
        raise ValueError("Para continuar la base hace falta el texto de estilo")
    _minimum, _maximum, _chunks, batch = continuation_limits(settings.remix)
    config = settings.remix
    return GenerationRequest(
        prompt=style_for_engine(request.prompt, settings),
        constraint_prompt=style_caption(request.prompt),
        lyrics=request.lyrics, instrumental=request.instrumental,
        task_type="repaint", source_path=str(bed), duration_seconds=None,
        bpm=request.bpm, seed=seed, batch_size=batch,
        model=settings.generation.remix_model, audio_format=config.intermediate_format,
        repaint_start=span["start"], repaint_end=span["end"],
        repaint_mode=request.repaint_mode or config.repaint_mode,
        repaint_strength=config.repaint_strength if request.repaint_strength is None else request.repaint_strength,
    )


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


def unmeasured_variant_notice(index: int) -> str:
    """Aviso cuando una variante de canción completa se queda fuera del lote."""
    return f"La variante {index + 1} no tenía un pulso medible; no se publicó."


def full_bpm_preview_notice() -> str:
    """Aviso que viaja con el trabajo. No dice que una sola variante tumba el lote."""
    return (
        "En canción completa se mide cada variante y se ajusta después su tempo sin cambiar el tono. "
        "La duración natural se calcula tras generar. "
        "Si pides más, el motor continúa el final de esa base y el recorte marcado entra una vez al empezar lo que sobra. "
        "Agotadas las muestras, la variante sin pulso no se publica. "
        "Si otra midió, se publica esa y el trabajo lo dice. "
        "Si ninguna mide, sigue el error del detector. "
        "Un BPM medido fuera de tolerancia detiene todo el lote y no pide otra generación."
    )


def full_variant_failure(exc: BaseException) -> str:
    """Una variante sin pulso se aparta. Cualquier otro fallo para el lote."""
    if audio_has_no_usable_groove(exc):
        return "withhold"
    return "raise"


def unpublished_batch_error(kept: int, withheld: list[BaseException]) -> BaseException | None:
    """Si nadie quedó medible, se conserva el error del detector y no se publica."""
    if kept > 0 or not withheld:
        return None
    return withheld[-1]


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
    lyrics = request.lyrics
    instrumental = request.instrumental
    external_voice = False
    if request.scope == "groups":
        voice_action = (request.groups or {}).get("vocals")
        if voice_action == "keep":
            external_voice = True
            instrumental = True
            lyrics = None
        elif voice_action == "remove":
            instrumental = True
            lyrics = None
    return GenerationRequest(
        prompt=style_for_engine(request.prompt, settings),
        constraint_prompt=style_caption(request.prompt),
        lyrics=lyrics, instrumental=instrumental,
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
        external_voice=external_voice,
    )


class RemixProjectRuntime:
    def __init__(self, app, music, settings, remix_jobs, separate_jobs, find_audio,
                 busy, remember, public_job, event, save, unique_output, safe_name,
                 carry_ficha, measure_bpm, now, cancelled, lifecycle=None):
        self.music, self.settings = music, settings
        self.lifecycle = lifecycle
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
                         "max_transition_seconds": remix.timeline_max_transition_seconds,
                         "continuation_min_seconds": remix.continuation_min_seconds,
                         "continuation_max_seconds": remix.continuation_max_seconds},
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
        if timeline["method"] == "continue_bed" and not style_caption(request.prompt):
            raise ValueError("Para continuar la base hace falta el texto de estilo")
        config = self.settings.remix
        transform = request.scope != "groups" or "transform" in request.groups.values()
        continues = timeline["method"] == "continue_bed"
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
            warnings = [constraint_rules()["limitation"]]
            if not continues:
                warnings.append("Operación determinista: no usa motor, batch ni semilla.")
            result = {"effective_parameters": {}, "provenance": {}, "warnings": warnings}
        result["operations"] = {
            "scope": request.scope, "source": source.name,
            "source_kind": request.source_kind,
            "source_duration_seconds": duration, "groups": request.groups,
            "gains_db": {group: request.gains_db.get(group, 0.0)
                         for group, action in (request.groups or {}).items() if action != "remove"},
            "separation_required": request.scope == "groups",
            "engine_required": transform or continues,
            "timeline": timeline,
            "preserved_groups_processing": "common_pcm_tempo" if request.scope == "groups" else None,
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
            if request.bpm:
                result["warnings"].append(
                    "Con BPM pedido se mide la mezcla y se ajusta su tempo sin cambiar el tono. "
                    "Si el ritmo de la mezcla no se puede medir con fiabilidad, su tempo no se "
                    "ajusta al pedido y el trabajo se entrega con un aviso: el BPM pedido no "
                    "queda garantizado.")
        if request.scope == "full" and request.bpm:
            result["warnings"].append(full_bpm_preview_notice())
            result["pending_material"].append({"parameter": "variant_tempo", "path": None,
                "operation": "Medir cada variante, ajustar su tempo por DSP y verificar el BPM resultante",
                "derived_fields": ["natural_duration_seconds", "tempo_ratio", "mapped_repeat_start", "mapped_repeat_end"]})
        if request.scope == "region" and request.bpm:
            result["warnings"].append("En Tramo el BPM es orientativo: condiciona al motor, sin ajuste posterior del audio.")
        if timeline["method"] in {"continue_bed", "pending_generated_timeline"} and timeline.get("target_duration_seconds"):
            result["warnings"].append(
                "Si pides más duración, el motor continúa el final de la base ya creada. "
                "El recorte marcado entra una vez al empezar esa parte.")
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
            prepared = await asyncio.to_thread(
                self.prepare, request, source, reference, duration, measured)
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
        chosen_name = (request.output_name or "").strip()
        if chosen_name:
            job["output_name"] = chosen_name
        job["project"] = request.model_dump()
        job["source_analysis"] = completed_analysis_for(source)
        job["duration_seconds"] = duration
        job.update(effective_parameters=prepared["effective_parameters"],
                   provenance=prepared["provenance"], warnings=prepared["warnings"],
                   operations=prepared["operations"], pending_material=prepared["pending_material"])
        self.remember(self.remix_jobs, job["job_id"], job)
        self.save()
        runner = self._run_with_engine_lease if prepared["operations"]["engine_required"] else self.run
        background_tasks.add_task(runner, job, source, reference, request, duration)
        return {"job_id": job["job_id"], "status": job["status"]}

    async def _run_with_engine_lease(self, *args, **kwargs) -> None:
        if self.lifecycle is None:
            await self.run(*args, **kwargs)
            return
        async with self.lifecycle.operation():
            await self.run(*args, **kwargs)

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
        generation = await asyncio.to_thread(
            project_generation, request, engine_source, reference, self.settings)
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

    async def _continue_bed(self, job, request, work, index, bed, variant_plan, track):
        """Alarga la base ya creada y mete el recorte una vez al empezar lo que sobra."""
        config = self.settings.remix
        target = float(variant_plan["target_duration_seconds"])
        bed_seconds = await self.music.verify_audio(bed) / 1000
        window = sample_window(variant_plan, bed_seconds, config)
        spans = continuation_spans(bed_seconds, target, config) if target > bed_seconds else []
        current = bed
        chunks = []
        _minimum, _maximum, _chunk_limit, batch = continuation_limits(config)

        def on_update(status):
            self.cancelled(job)
            job["status"] = "running"
            job["engine_progress"] = status.progress
            job["progress_ratio"] = status.moving_progress()
            job["engine_progress_text"] = status.progress_text or ""
            job["phase"] = _visible_phase(status)

        for number, span in enumerate(spans, start=1):
            self.cancelled(job)
            self.event(job, f"Continuando la base de la variante {index + 1}, trozo {number}")
            seed = track.seed if track is not None and track.seed is not None else request.seed
            generation = await asyncio.to_thread(
                continuation_generation, request, current, span, seed, self.settings)
            job["engine_active"] = True
            try:
                task_id, _detail = await self.music.submit(generation)
                job["engine_task_id"] = task_id
                self.save()
                final = await self.music.wait(task_id, on_update=on_update)
            finally:
                job["engine_active"] = False
            self.cancelled(job)
            if not final.succeeded:
                raise MusicEngineError(final.error or "El motor terminó sin audio válido")
            ready = [item for item in final.tracks if item.file]
            if len(ready) != batch:
                raise MusicEngineError(
                    f"El motor devolvió {len(ready)} continuaciones; se pidió {batch}")
            produced = ready[0]
            dest = work / f"continuacion-{index + 1}-{number}.wav"
            await self.music.download(produced.file, dest)
            seconds = await self.music.verify_audio(dest) / 1000
            if abs(seconds - span["end"]) > config.duration_tolerance_seconds:
                raise MusicEngineError(
                    f"La continuación duró {seconds:g} s y el trozo pedía {span['end']:g} s")
            chunks.append({
                "start": span["start"], "end": span["end"], "file_name": dest.name,
                "seed": produced.seed, "seed_origin": produced.seed_origin,
            })
            current = dest
        self.cancelled(job)
        extended = work / f"arreglo-{index + 1}.wav"
        info = await asyncio.to_thread(
            MixerService.finish_continuation, current, bed, extended, window,
            bed_seconds, target, config)
        return extended, {**info, "chunks": chunks, "bed_seconds": bed_seconds}

    def _fail(self, job: dict, error: Exception) -> None:
        logger.error(f"Proyecto/separación {job['job_id']} falló: {error}")
        job.update(status="failed", phase="Cancelado" if job.get("cancelled") else "Error",
                   error="Cancelado por el usuario" if job.get("cancelled") else str(error),
                   completed_at=self.now(), elapsed_seconds=time.monotonic() - job["started"])

    async def finish_downloaded(self, job, source, reference, request, duration, receipt,
                                *, before_publish=None) -> None:
        """Completa explícitamente WAV verificados, sin enviar otra tarea al motor."""
        await self.run(job, source, reference, request, duration, downloaded=receipt,
                       before_publish=before_publish)

    async def run(self, job, source, reference, request, duration, *, downloaded=None,
                  before_publish=None) -> None:
        config = self.settings.remix
        work = work_directory(self.settings.outputs_dir, job["job_id"])
        recovered = None
        if downloaded is not None:
            recovered = await validate_receipt(downloaded, job, source, reference, request,
                                               duration, self.settings, self.music)
        work.mkdir(parents=True, exist_ok=True)
        originals = {}
        targets = []
        job["compute_active"] = True
        try:
            async with COMPUTE_LOCK:
                self.cancelled(job)
                job["status"] = "running"
                if recovered is not None:
                    job["error"] = None
                    job.pop("completed_at", None)
                    self.event(job, "Completando el lote de WAV descargados, sin otra generación")
                digest = await asyncio.to_thread(source_digest, source)
                if digest != job["operations"]["source_digest"]:
                    raise ValueError("La fuente cambió después de solicitar el remix; vuelve a seleccionar el audio")
                job["source_digest"] = digest
                plan = job["operations"]["timeline"]
                natural_duration = plan["natural_duration_seconds"] or duration
                engine_source = source
                if recovered is not None:
                    _generated, originals = recovered
                    targets = [key for key, action in request.groups.items() if action == "transform"]
                    job["preserved_groups"] = [key for key, action in request.groups.items() if action == "keep"]
                elif request.scope == "groups":
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
                if recovered is not None:
                    generated = recovered[0]
                elif request.scope != "groups" or targets:
                    task = "repaint" if request.scope == "region" else "cover"
                    self.event(job, f"Transformando el audio original con {task}")
                    generation = await asyncio.to_thread(
                        project_generation, request, engine_source, reference, self.settings)
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
                    receipt = await asyncio.to_thread(build_receipt, job, source, reference, request,
                        duration, self.settings, generated, originals)
                    await asyncio.to_thread(atomic_json, work / RECEIPT_NAME, receipt)
                    job["operations"]["downloaded_batch_sha256"] = receipt_digest(receipt)
                    self.save()
                else:
                    generated = [(None, None)]
                exported, metadata, publications, withheld = [], [], [], []
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
                        try:
                            (path, track, tempo_before, variant_plan, groove_replacements,
                             replacement_parameters, tempo_after_adjust, tempo_processing) = (
                                await self._measured_full_variant(
                                    job, request, work, index, path, track, engine_source, reference,
                                    natural_duration, duration, config))
                        except ValueError as exc:
                            if full_variant_failure(exc) != "withhold":
                                raise
                            withheld.append((index, exc))
                            continue
                        timeline = Path(tempo_processing["output_path"])
                    if request.scope == "groups":
                        transformed = {}
                        separated = {}
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
                            separated = {item["id"]: work / item["file_name"] for item in result["groups"]}
                            gains = [request.gains_db.get(key, 0.0) for key in targets]
                            if len(set(gains)) == 1:
                                replaced = work / f"reemplazada-{index + 1}.wav"
                                await asyncio.to_thread(
                                    MixerService.mix_groups,
                                    [(originals[key], 0.0) for key in targets],
                                    replaced, natural_duration, config.sample_rate)
                                bed = work / f"base-transformada-{index + 1}.wav"
                                mounted = await asyncio.to_thread(
                                    MixerService.render_transformed_bed, path, separated, request.groups,
                                    replaced, bed, config)
                                warning = mounted.get("warning")
                                if warning and warning not in job.setdefault("warnings", []):
                                    job["warnings"].append(warning)
                                transformed = {key: bed for key in targets}
                            else:
                                transformed = separated
                        parts = []
                        seen = set()
                        for key, action in request.groups.items():
                            if action == "remove":
                                continue
                            gain = request.gains_db.get(key, 0.0)
                            if action == "keep":
                                parts.append((originals[key], gain))
                                continue
                            source = transformed[key]
                            if source in seen:
                                continue
                            seen.add(source)
                            parts.append((source, gain))
                        timeline = work / f"mezcla-{index + 1}.wav"
                        self.event(job, f"Recombinando la variante {index + 1} sobre la timeline original")
                        await asyncio.to_thread(MixerService.mix_groups, parts, timeline, natural_duration, config.sample_rate)
                    self.cancelled(job)
                    if request.scope == "groups" and request.bpm is not None:
                        self.event(job, f"Comprobando el tempo de la mezcla {index + 1}")
                        aligned = None
                        mix_uncertain = None
                        try:
                            mix_measured = await asyncio.to_thread(required_measured_tempo, timeline)
                        except ValueError as exc:
                            reference = originals.get("drums") if "drums" in targets else None
                            new_kick = separated.get("drums") if reference is not None else None
                            movable = []
                            for piece, _gain in parts:
                                if piece in transformed.values() and piece not in movable:
                                    movable.append(piece)
                            squared = None
                            if (audio_has_no_usable_groove(exc) and reference is not None
                                    and new_kick is not None and movable):
                                self.event(job, f"Cuadrando el bombo de la variante {index + 1} con el original")
                                squared = await asyncio.to_thread(
                                    square_mix_on_original_kick, parts, movable, reference, new_kick,
                                    work / f"mezcla-cuadrada-{index + 1}.wav", work, index + 1,
                                    natural_duration, config)
                            if squared is not None:
                                timeline = squared["timeline"]
                                aligned = squared
                                try:
                                    mix_measured = await asyncio.to_thread(required_measured_tempo, timeline)
                                except ValueError as recheck:
                                    if not audio_has_no_usable_groove(recheck):
                                        raise
                                    mix_uncertain = recheck
                                    mix_measured = None
                            else:
                                # Entrega pedida (2026-10-19): si la mezcla no tiene
                                # pulso fiable, el trabajo sale con un aviso honesto de
                                # que no se ajustó al BPM pedido. Un error ajeno al
                                # groove sigue fallando.
                                mix_uncertain = exc
                                mix_measured = None
                        self.cancelled(job)
                        if mix_uncertain is not None:
                            notice = uncertain_mix_notice(mix_uncertain, request.bpm)
                            if notice is None:
                                raise mix_uncertain
                            mark_uncertain_mix_tempo(variant_plan, mix_uncertain)
                            warnings = job.setdefault("warnings", [])
                            if aligned is not None:
                                # El cuadre sí alteró el audio: la ficha lo dice aunque
                                # la medición siga sin fiarse.
                                variant_plan["kick_alignment_delay_ms"] = aligned["delay_ms"]
                                variant_plan["kick_alignment_tempo_ratio"] = aligned["tempo_ratio"]
                                warning = ("La mezcla no tenía un pulso propio; "
                                           "el bombo nuevo se cuadró con el original.")
                                if warning not in warnings:
                                    warnings.append(warning)
                            if notice not in warnings:
                                warnings.append(notice)
                            self.event(job, f"El ritmo de la mezcla {index + 1} no se pudo medir; "
                                            "se entrega sin ajustarla al BPM pedido, con aviso")
                        else:
                            measured_bpm = require_measured_tempo(mix_measured, config, "en la mezcla de grupos")
                            if aligned is not None:
                                variant_plan["kick_alignment_delay_ms"] = aligned["delay_ms"]
                                variant_plan["kick_alignment_tempo_ratio"] = aligned["tempo_ratio"]
                                warning = ("La mezcla no tenía un pulso propio; "
                                           "el bombo nuevo se cuadró con el original.")
                                warnings = job.setdefault("warnings", [])
                                if warning not in warnings:
                                    warnings.append(warning)
                            ratio = groups_tempo_ratio(measured_bpm, request.bpm, config)
                            tempo_before = mix_measured
                            if ratio is not None:
                                seconds = await self.music.verify_audio(timeline) / 1000
                                adjusted_plan = apply_groups_mix_tempo(
                                    variant_plan, seconds, ratio, request.duration_seconds, config)
                                adjusted = work / f"tempo-mezcla-{index + 1}.wav"
                                self.event(job, f"Ajustando el BPM de la variante {index + 1} sin cambiar el tono")
                                tempo_processing = await asyncio.to_thread(
                                    MixerService.tempo_audio, timeline, adjusted, ratio,
                                    adjusted_plan["natural_duration_seconds"], config)
                                tempo_processing.update(input_path=str(timeline), output_path=str(adjusted))
                                tempo_after_adjust = await asyncio.to_thread(required_measured_tempo, adjusted)
                                verify_requested_tempo(tempo_after_adjust, request.bpm, config, "después del ajuste DSP")
                                variant_plan = adjusted_plan
                                variant_plan["beat_clock_bpm"] = tempo_after_adjust["bpm_measured"]
                                variant_plan["beat_clock_origin"] = "adjusted_audio_measurement"
                                timeline = adjusted
                            else:
                                variant_plan["beat_clock_bpm"] = mix_measured["bpm_measured"]
                                variant_plan["beat_clock_origin"] = "generated_measurement"
                        self.cancelled(job)
                    arrangement = {"method": "original", "repetitions": 0,
                                   "duration_seconds": variant_plan["natural_duration_seconds"],
                                   "transition_seconds": 0.0, "sample": {"placed": False}, "chunks": []}
                    body = timeline
                    if variant_plan["method"] == "continue_bed":
                        self.event(job, f"Continuando la base de la variante {index + 1}")
                        timeline, arrangement = await self._continue_bed(
                            job, request, work, index, body, variant_plan, track)
                        self.cancelled(job)
                    elif variant_plan["method"] == "repeat_crossfade":
                        self.event(job, f"Ampliando la variante {index + 1} con partes y transiciones")
                        extended = work / f"arreglo-{index + 1}.wav"
                        arrangement = await asyncio.to_thread(MixerService.extend_timeline, body, extended, variant_plan, config)
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
                    self.event(job, f"Comprobando el tempo de la variante {index + 1}")
                    repeated_whole_song = False
                    if request.bpm is not None and request.scope in {"full", "groups"}:
                        try:
                            measured = await asyncio.to_thread(
                                required_measured_tempo, staged_output, arrangement, config)
                        except ValueError as exc:
                            if (variant_plan.get("tempo_verification") == "uncertain_at_mix"
                                    and audio_has_no_usable_groove(exc)):
                                # La mezcla ya se entregaba sin tempo acreditado (decisión
                                # 2026-10-19): si la medición final tampoco se fía, el
                                # trabajo sigue con ese mismo aviso, sin repetir la
                                # canción entera ni bajar ningún corte del detector.
                                measured = None
                                variant_plan["final_tempo_verification"] = "uncertain_at_mix"
                                variant_plan["final_tempo_verification_error"] = str(exc)
                                self.event(job, f"El BPM final de la variante {index + 1} "
                                               "sigue sin verificarse; se entrega con aviso")
                            else:
                                widened = whole_song_repeat_plan(variant_plan, config) if (
                                    audio_has_no_usable_groove(exc)
                                    and variant_plan.get("method") == "repeat_crossfade") else None
                                if widened is None:
                                    # [R17] Por pistas que continúa la base: la mezcla ya se
                                    # midió y verificó antes de ampliar. Si la medición final
                                    # del archivo ampliado es incierta, el tempo acreditado
                                    # sigue siendo el de esa base y el trabajo se entrega con
                                    # aviso; ningún corte del detector se baja.
                                    fallback = uncertain_extension_fallback(
                                        exc, request.scope, variant_plan,
                                        tempo_after_adjust or tempo_before, config)
                                    if fallback is None:
                                        raise
                                    measured = fallback
                                    variant_plan["final_tempo_verification"] = "uncertain_after_extension"
                                    variant_plan["final_tempo_verification_error"] = str(exc)
                                    self.event(job, f"El pulso de la ampliación de la variante {index + 1} "
                                                   "no se pudo medir; se conserva el tempo de la base verificado")
                                    warning = ("La ampliación continuó la misma base, pero su pulso no se pudo "
                                               "volver a medir; el tempo acreditado es el de la base verificada "
                                               "antes de continuar.")
                                    warnings = job.setdefault("warnings", [])
                                    if warning not in warnings:
                                        warnings.append(warning)
                                    if request.bpm is not None:
                                        ratio_after = groups_tempo_ratio(
                                            measured["bpm_measured"], request.bpm, config)
                                        if ratio_after is not None:
                                            adjusted_final = work / f"tempo-final-{index + 1}.wav"
                                            self.event(job, f"Ajustando el BPM final de la variante {index + 1} sin cambiar el tono")
                                            await asyncio.to_thread(
                                                MixerService.tempo_audio, staged_output, adjusted_final, ratio_after,
                                                variant_plan["target_duration_seconds"], config)
                                            staged_output = adjusted_final
                                            final_seconds = await self.music.verify_audio(staged_output) / 1000
                                            try:
                                                measured = await asyncio.to_thread(
                                                    required_measured_tempo, staged_output, arrangement, config)
                                            except ValueError:
                                                measured = fallback
                                                variant_plan["final_tempo_verification"] = "uncertain_after_extension_and_atempo"
                                    # fall through to verify_requested_tempo below
                                else:
                                    self.event(job, f"La parte elegida no conserva el pulso; "
                                               f"se repite la canción entera en la variante {index + 1}")
                                    extended = work / f"arreglo-completo-{index + 1}.wav"
                                    arrangement = await asyncio.to_thread(
                                        MixerService.extend_timeline, body, extended, widened, config)
                                    timeline = extended
                                    self.cancelled(job)
                                    mastering = await asyncio.to_thread(
                                        MixerService.export_remix, timeline, staged_output, config)
                                    final_seconds = await self.music.verify_audio(staged_output) / 1000
                                    if abs(final_seconds - widened["target_duration_seconds"]) > config.duration_tolerance_seconds:
                                        raise ValueError("La duración final no corresponde al arreglo solicitado")
                                    measured = await asyncio.to_thread(
                                        required_measured_tempo, staged_output, arrangement, config)
                                    variant_plan = widened
                                    repeated_whole_song = True
                    else:
                        measured = await asyncio.to_thread(self.measure_bpm, staged_output)
                    self.cancelled(job)
                    if request.bpm is not None and request.scope in {"full", "groups"}:
                        if variant_plan.get("tempo_verification") == "uncertain_at_mix":
                            # La mezcla se entrega con su aviso de tempo sin acreditar
                            # (decisión 2026-10-19); no se verifica contra el BPM pedido.
                            pass
                        elif variant_plan.get("final_tempo_verification") == "uncertain_after_extension_and_atempo":
                            self.event(job, f"El BPM final de la variante {index + 1} no se pudo verificar tras el ajuste DSP; "
                                           f"se entrega con el tempo acreditado de la base ({measured['bpm_measured']} BPM)")
                        else:
                            verify_requested_tempo(measured, request.bpm, config, "después del arreglo y exportación")
                    if repeated_whole_song:
                        warning = "La parte elegida no conservaba el pulso; se repitió la canción entera."
                        warnings = job.setdefault("warnings", [])
                        if warning not in warnings:
                            warnings.append(warning)
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
                withheld_error = unpublished_batch_error(
                    len(publications), [exc for _index, exc in withheld])
                if withheld_error is not None:
                    raise withheld_error
                warnings = job.setdefault("warnings", [])
                for index, _exc in withheld:
                    notice = unmeasured_variant_notice(index)
                    if notice not in warnings:
                        warnings.append(notice)
                if before_publish is not None:
                    before_publish()
                self.event(job, "Publicando las variantes verificadas del remix")
                # Las variantes que se publican han pasado sus verificaciones.
                # No hay awaits entre el checkpoint y la publicación del lote.
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
