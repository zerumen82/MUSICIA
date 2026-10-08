"""API de Musicia: creación, mezcla y remix de música con IA en local.

Endpoints
---------
GET  /api/info              información del servicio
GET  /health                estado real del motor local ACE-Step
POST /music/generate        crea una generación real en el motor local
GET  /music/status/{job_id} estado y resultado de una generación
GET  /music/audio/{name}    descarga el audio generado
POST /audio/remix/ai        remix con IA (voz original + base nueva)
... (el resto, en orden de aparición más abajo)

Nada aquí es simulado: cada endpoint hace el trabajo real y devuelve error si falla.
"""

from __future__ import annotations

import asyncio
import json
import mimetypes
import os
import re
import signal
import socket
import subprocess
import time
import urllib.parse
import uuid
from contextlib import asynccontextmanager
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncIterator, Literal

from fastapi import BackgroundTasks, FastAPI, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger
from pydantic import BaseModel, Field

from config import BACKEND_DIR, PROJECT_ROOT, get_settings
from audio_analysis import analyze_audio, detect_groove
from audio_service import (
    MAX_GAIN_DB as PROC_MAX_GAIN_DB,
    MAX_FADE_MS as PROC_MAX_FADE_MS,
    MIN_GAIN_DB as PROC_MIN_GAIN_DB,
    process_audio,
)
from mixer_service import (
    MIN_GROOVE_CONFIDENCE, TARGET_LUFS, MixerService, bars_duration_seconds, crossfade,
    first_beat_seconds, force_tempo, make_loop, measure_loudness, normalize_track,
    plan_alignment, plan_vocal_arrangement,
)
from separator_service import SeparatorService
from separator_service import free_vram_mb
from separator_service import is_available as separator_available
from separator_service import pick_device
from prompt_enhancer import enhance_prompt
from prompt_style import analyze_prompt, style_caption
from genre_glossary import search as glossary_search, combine as glossary_combine
from music_service import (
    GenerationRequest,
    MusicEngineError,
    MusicService,
    lyrics_are_song,
)

settings = get_settings()
music = MusicService(settings)

# Seguimiento de generaciones en curso. El motor es quien decide el estado real;
# aquí solo guardamos la salida descargada y los datos de la tarea.
jobs: dict[str, dict[str, Any]] = {}


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    _load_history()
    await music.start()
    logger.info("Musicia API lista | motor ACE-Step: " + settings.acestep.base_url)
    yield
    await music.aclose()


app = FastAPI(title="Musicia API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Esquemas
# ---------------------------------------------------------------------------


class MixRequest(BaseModel):
    base_track: str
    vocal_track: str
    output_name: str | None = None
    base_volume: float = 0
    vocal_volume: float = 0
    align: bool = Field(default=False, description="Cuadrar tempo y fase de la voz con la base")
    normalize_lufs: bool = Field(default=True, description="Normalizar a -14 LUFS con pico -1 dBTP")
    base_kind: str | None = Field(default=None, description="upload | output: de qué lista viene la base")
    vocal_kind: str | None = Field(default=None, description="upload | output: de qué lista viene la voz")


class MixPlanRequest(BaseModel):
    """Pide la propuesta de alineación ANTES de mezclar (transparencia)."""

    base_track: str
    vocal_track: str
    base_kind: str | None = Field(default=None, description="upload | output: de qué lista viene la base")
    vocal_kind: str | None = Field(default=None, description="upload | output: de qué lista viene la voz")


class SeparateRequest(BaseModel):
    """Extrae la voz de una pista (voces + base) para poder remezclar."""

    file_name: str
    output_name: str | None = None
    source_kind: str | None = Field(default=None, description="upload | output: de qué lista viene")


class TempoRequest(BaseModel):
    """Fuerza el tempo de una pista (para bootlegs: medio/doble tiempo)."""

    file_name: str
    bpm: float | None = Field(default=None, description="Tempo objetivo en BPM")
    mode: str = Field(default="half", description="half | double | bpm")
    output_name: str | None = None
    source_kind: str | None = Field(default=None, description="upload | output: de qué lista viene")


class LoopRequest(BaseModel):
    """Exporta un loop. Sin segundos, corta los compases configurados desde el golpe."""

    file_name: str
    seconds: float | None = Field(default=None, gt=1, le=120)
    start_seconds: float = Field(default=0, ge=0)
    output_name: str | None = None
    source_kind: str | None = Field(default=None, description="upload | output: de qué lista viene")


class CrossfadeRequest(BaseModel):
    """Funde varias pistas igualando su tempo (estilo DJ)."""

    tracks: list[str]
    fade_seconds: float = 4.0
    output_name: str | None = None
    track_kinds: list[str | None] | None = Field(
        default=None, description="upload | output por pista, en el mismo orden que tracks"
    )


class AiRemixRequest(BaseModel):
    """Reestilo con IA (cover nativo): el motor oye la pista y la reviste.

    Fuerza manual manda; vacía = la deduce el prompt. Duración vacía = la
    del tema. Letra vacía = reestilo instrumental (el motor no clona voces).
    """

    file_name: str
    prompt: str = Field(min_length=3, description="Estilo nuevo del reestilo")
    bpm: float | None = None
    output_name: str | None = None
    duration_seconds: float | None = Field(default=None, description="Duración elegida; vacía = la del tema")
    lyrics: str | None = Field(default=None, description="Letra nueva; vacía = instrumental")
    source_kind: str | None = Field(default=None, description="upload | output: de qué lista viene")
    cover_strength: float | None = Field(
        default=None, description="Fuerza manual del cover (0-1); vacío = la deduce del prompt"
    )
    mode: Literal["reestilar", "voz"] = Field(
        default="reestilar",
        description="reestilar = el motor oye tu pista y la reviste (la voz cambia); voz = tu voz se conserva y la música es nueva",
    )


class MusicGenRequest(BaseModel):
    prompt: str = Field(min_length=1, description="Descripción del estilo musical")
    lyrics: str | None = Field(default=None, description="Letra; obligatoria si no es instrumental")
    instrumental: bool | None = None
    output_name: str | None = Field(default=None, description="Nombre de la canción que elige el usuario")
    duration_seconds: float | None = None
    bpm: int | None = None
    key_scale: str | None = None
    time_signature: str | None = None
    language: str | None = None
    inference_steps: int | None = None
    guidance_scale: float | None = None
    seed: int | None = None
    batch_size: int | None = None
    audio_format: str | None = None
    model: str | None = None
    task_type: str | None = Field(default=None, description="text2music, cover o repaint")
    source_name: str | None = Field(default=None, description="Audio de origen para cover y repaint")
    source_kind: str | None = Field(default=None, description="upload | output: de qué lista viene el origen")
    repaint_start: float | None = None
    repaint_end: float | None = None
    cover_strength: float | None = None
    use_format: bool | None = Field(
        default=None, description="El LM formatea caption y letra; vacío = lo que diga la config"
    )


class AudioProcessRequest(BaseModel):
    """Post-proceso de un audio existente en outputs/ (por nombre, nunca rutas)."""

    file_name: str
    output_name: str | None = None
    gain_db: float = 0.0
    fade_in_ms: int = 0
    fade_out_ms: int = 0
    trim_start_s: float = 0.0
    trim_end_s: float | None = None


class RemixRequest(BaseModel):
    """Remix real de un audio subido o generado: efectos DSP con pydub."""

    file_name: str
    output_name: str | None = None
    source_kind: str | None = Field(default=None, description="upload | output: de qué lista viene")
    tempo: float = 1.0          # 0.5 = mitad de velocidad, 2.0 = doble
    pitch_semitones: float = 0.0
    reverse: bool = False
    gain_db: float = 0.0
    fade_in_ms: int = 0
    fade_out_ms: int = 0
    trim_start_s: float = 0.0
    trim_end_s: float | None = None


class EnhancePromptRequest(BaseModel):
    """Mejora de prompt por reglas locales de producción."""

    prompt: str
    bpm: int | None = None


class RemixPromptRequest(BaseModel):
    """Petición de prompt sugerido para remixar/re-crear un audio subido."""

    file_name: str
    kind: str = "musica"   # musica | voz | mixta | otro
    source_kind: str | None = Field(default=None, description="upload | output: de qué lista viene")


class RenameRequest(BaseModel):
    """Nuevo nombre de una pista existente (biblioteca o subidas)."""

    new_name: str = Field(min_length=1, description="Nombre que elige el usuario, con o sin extensión")
    source_kind: str | None = Field(default=None, description="upload | output: de qué lista viene")


class DeleteManyRequest(BaseModel):
    """Borrado en bloque de la biblioteca (spec/02 [L2]): una petición, reporte por archivo."""

    names: list[str] = Field(min_length=1, max_length=100, description="Nombres de MP3 en outputs/, 1 a 100")


class WriteLyricsRequest(BaseModel):
    """Petición de letra automática al LM local del motor (spec A3)."""

    prompt: str = Field(min_length=1, description="Descripción del tema y del estilo")
    lyrics: str = Field(default="", description="Letra previa del usuario: se estructura y mejora")
    language: str | None = None
    duration_seconds: float | None = None
    bpm: int | None = None
    key_scale: str | None = None


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------


def _safe_name(raw: str | None, fallback: str, suffix: str = "") -> str:
    """Nombre de fichero seguro (sin rutas ni caracteres problemáticos).

    Conserva espacios, acentos y paréntesis para que el nombre que escribe
    el usuario sea el nombre real de su canción; solo elimina lo que Windows
    prohíbe en ficheros y lo que rompería una URL.
    """
    stem = re.sub(r"[\\/]+", " - ", raw or "")   # separadores → guion, nunca recortan texto
    stem = Path(stem).name
    stem = re.sub(r"[\\:*?\"<>|]+", " ", stem)   # prohibidos en Windows
    stem = re.sub(r"[^\w .()\-]", "", stem, flags=re.UNICODE)
    stem = re.sub(r"\s+", " ", stem).strip(" .-")
    stem = stem[: settings.generation.max_slug_chars].strip(" .-") or fallback
    if suffix and not stem.lower().endswith(suffix):
        stem = f"{stem}{suffix}"
    return stem


def _resolve_output(output_name: str) -> Path:
    """Resuelve un nombre dentro del directorio de salidas, bloqueando escapes."""
    candidate = (settings.outputs_dir / Path(output_name).name).resolve()
    if settings.outputs_dir not in candidate.parents:
        raise HTTPException(status_code=400, detail="Nombre de fichero no válido")
    return candidate


# Prefijo de las pistas que el usuario no ha nombrado (decisión del usuario, spec E1).
DEFAULT_STEM = "pista-sin-nombre"


def _unique_output_path(stem: str, suffix: str) -> Path:
    """Ruta libre para `stem` en outputs/, numerando: nombre, (2), (3)…

    Nunca pisa una pista existente: el usuario elige el nombre y la app
    desambigua sola (spec/02 Épica E).
    """
    candidate = _resolve_output(_safe_name(stem, DEFAULT_STEM, suffix=suffix))
    index = 2
    while candidate.exists():
        candidate = _resolve_output(
            _safe_name(f"{stem} ({index})", DEFAULT_STEM, suffix=suffix)
        )
        index += 1
        if index > 500:
            raise HTTPException(status_code=409, detail="Demasiadas versiones con ese nombre")
    return candidate


def _find_audio(name: str, kind: str | None = None) -> Path:
    """Localiza un audio en outputs/ o en uploads/.

    La UI dice de qué lista viene (`source_kind`): esa carpeta manda y la
    otra solo es reserva. Sin kind se mantiene el orden viejo (outputs
    primero) para no romper a MEZCLA, que ya desambigua a favor de bib.
    """
    if kind is None:
        resolvers = (_resolve_output, _resolve_upload)
    elif kind == "upload":
        resolvers = (_resolve_upload, _resolve_output)
    elif kind == "output":
        resolvers = (_resolve_output, _resolve_upload)
    else:
        raise HTTPException(status_code=400, detail="source_kind tiene que ser upload u output")
    for resolver in resolvers:
        try:
            candidate = resolver(name)
        except HTTPException:
            continue
        if candidate.exists():
            return candidate
    raise HTTPException(status_code=404, detail="Audio no encontrado")


def _derive_stem(source_name: str, marker: str) -> str:
    """Stem heredado de una fuente + marca (remix, ajuste, ia…), sin acumular.

    'mi-cancion-remix.mp3' + 'remix' -> 'mi-cancion-remix' (no '-remix-remix').
    """
    stem = Path(source_name).stem
    stem = re.sub(r"^[0-9a-f]{8}-", "", stem, flags=re.IGNORECASE)  # prefijo de subida
    suffix = f"-{marker}"
    if stem.lower().endswith(suffix):
        stem = stem[: -len(suffix)]
    return f"{stem}{suffix}"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _ficha_path(audio_path: Path) -> Path:
    return audio_path.with_suffix(".ficha.json")


def _write_ficha(audio_path: Path, job: dict[str, Any]) -> None:
    """Datos de la pista al lado del MP3. Sin esto, un remix posterior va a ciegas."""
    ficha = {
        "name": audio_path.name,
        "prompt": job.get("prompt"),
        "lyrics": job.get("lyrics"),
        "bpm": job.get("bpm"),
        "task_type": job.get("task_type") or "text2music",
        "source_name": job.get("source_name"),
        "seed": job.get("seed"),
        "key_scale": job.get("key_scale"),
        "time_signature": job.get("time_signature"),
        "model": job.get("model"),
        "duration_seconds": job.get("duration_seconds"),
        "created_at": job.get("created_at"),
    }
    _ficha_path(audio_path).write_text(
        json.dumps(ficha, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _drop_ficha(audio_path: Path) -> None:
    """Borra la ficha si existe. Un MP3 sin pareja no deja un JSON huérfano."""
    _ficha_path(audio_path).unlink(missing_ok=True)


def _move_ficha(source: Path, target: Path) -> None:
    """La ficha viaja con el audio al renombrar y actualiza el nombre de dentro."""
    src = _ficha_path(source)
    if not src.exists():
        return
    dest = _ficha_path(target)
    try:
        data = json.loads(src.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        data = None
    if isinstance(data, dict):
        data["name"] = target.name
        dest.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        if src != dest:
            src.unlink(missing_ok=True)
        return
    if src != dest:
        src.replace(dest)


def _carry_ficha(source: Path, target: Path, task_type: str, **overrides: Any) -> None:
    """Copia la ficha del origen al MP3 nuevo y marca qué operación lo creó."""
    data = _read_ficha(source) or {}
    data["name"] = target.name
    data["task_type"] = task_type
    data["source_name"] = source.name
    for key, value in overrides.items():
        if value is not None:
            data[key] = value
    _ficha_path(target).write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _read_ficha(audio_path: Path) -> dict[str, Any] | None:
    path = _ficha_path(audio_path)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


# ---------------------------------------------------------------------------
# Background: descarga y verificación del audio generado
# ---------------------------------------------------------------------------


def _human_phase(engine_status: int, progress_text: str, stage: str = "") -> str:
    """Traduce el estado del motor a una fase que una persona entienda."""
    if engine_status == 1:
        return "Descargando y verificando el audio"
    stage_low = (stage or "").lower()
    if stage_low == "queued":
        return "En cola del motor (esperando turno en la GPU)"
    if "start" in stage_low or "infer" in stage_low or "diffus" in stage_low:
        return "Sintetizando el audio (difusión por pasos)"
    if "vae" in stage_low or "decode" in stage_low or "tiled" in stage_low:
        return "Convirtiendo a audio final"
    text = (progress_text or "").lower()
    if "load" in text or "carg" in text:
        return "Cargando el modelo en la GPU (la primera vez tarda varios minutos)"
    if "infer" in text or "step" in text or "diffus" in text:
        return "Sintetizando el audio (difusión por pasos)"
    if "vae" in text or "decode" in text:
        return "Convirtiendo a audio final"
    if "text" in text or "lm" in text or "lyric" in text:
        return "Preparando la estructura musical"
    return "Trabajando en el motor (esto tarda 1-3 min con la GPU)"


async def _finalize_generation(job_id: str) -> None:
    """Espera al motor, descarga el audio y comprueba que no está vacío.

    Mientras espera, enriquece el job con fase humana, tiempo transcurrido
    y un registro de eventos para que la UI nunca parezca colgada.
    """
    job = jobs[job_id]
    if job.get("cancelled"):
        logger.info(f"Generación {job_id[:8]} ya cancelada antes de arrancar: no se envía nada")
        return
    started = time.monotonic()
    # No se vacían los eventos: el alta ya dejó los suyos (p. ej. el aviso
    # de «Caption compuesto»). log_event recorta a 30, no crece sin límite.

    def log_event(text: str) -> None:
        elapsed = round(time.monotonic() - started, 1)
        job["events"].append({"t": elapsed, "text": text})
        # Solo los últimos 30 eventos (no crece sin límite)
        del job["events"][:-30]
        logger.info(f"[{job_id[:8]}] +{elapsed}s {text}")

    # El trabajo pasa a CREANDO en cuanto el motor acepta la tarea:
    # si no, la UI lo mostraría en cola hasta el final.
    job["status"] = "running"
    log_event("Tarea aceptada; enviada al motor local")

    def on_update(status: Any) -> None:
        """Callback síncrono: actualiza progreso, fase y eventos."""
        _throw_if_cancelled(job)
        prev_text = job.get("engine_progress_text", "")
        job["engine_status"] = status.status
        job["engine_progress_text"] = status.progress_text or prev_text
        job["progress_ratio"] = status.progress
        job["stage"] = status.stage
        job["phase"] = _human_phase(status.status, status.progress_text, status.stage)
        job["elapsed_seconds"] = round(time.monotonic() - started, 1)
        if not status.succeeded and not status.failed:
            job["status"] = "running"
        if status.progress_text and status.progress_text != prev_text:
            log_event(status.progress_text)

    try:
        final = await music.wait(job["engine_task_id"], on_update=on_update)
        _throw_if_cancelled(job)
        if not final.succeeded:
            raise MusicEngineError(final.error or "El motor terminó la tarea con error")

        log_event("Audio generado por el motor; descargando…")
        job["phase"] = "Descargando el audio desde el motor"

        tracks = [item for item in final.tracks if item.file]
        if not tracks:
            raise MusicEngineError("El motor no devolvió ningún archivo de audio")
        if len(tracks) > 1:
            log_event(f"El motor devolvió {len(tracks)} variantes (batch 2): se guardan todas.")

        saved: list[str] = []
        first_duration_ms = 0
        first_metas = None
        first_caption = None
        for index, track in enumerate(tracks):
            if index == 0:
                output_path = _resolve_output(job["output_name"])
            else:
                variant_stem = f"{Path(job['output_name']).stem}-v{index + 1}"
                output_path = _unique_output_path(_safe_name(variant_stem, DEFAULT_STEM), ".mp3")
            await music.download(track.file, output_path)
            if index == 0:
                log_event("Audio descargado; verificando duración…")
                job["phase"] = "Verificando el audio generado"
            duration_ms = await music.verify_audio(output_path)
            if job.get("task_type") in {"cover", "repaint"}:
                if index == 0:
                    log_event(f"Igualando el volumen al master ({TARGET_LUFS:g} LUFS)")
                    job["phase"] = f"Master a {TARGET_LUFS:g} LUFS"
                mastered = output_path.with_name(f"{output_path.stem}-master.mp3")
                try:
                    job["loudness"] = await asyncio.to_thread(normalize_track, output_path, mastered)
                    mastered.replace(output_path)
                finally:
                    mastered.unlink(missing_ok=True)
                duration_ms = await music.verify_audio(output_path)
            if index == 0:
                first_duration_ms, first_metas, first_caption = duration_ms, track.metas, track.prompt
            saved.append(output_path.name)
            _write_ficha(output_path, job)

        job.update(
            status="succeeded",
            phase="Lista",
            duration_seconds=round(first_duration_ms / 1000, 2),
            metas=first_metas,
            engine_caption=first_caption,
            variants=saved,
            elapsed_seconds=round(time.monotonic() - started, 1),
            completed_at=_now(),
        )
        log_event(f"Completado: {', '.join(saved)} ({first_duration_ms / 1000:.1f} s)")
        logger.info(f"Generación {job_id} lista: {', '.join(saved)} ({first_duration_ms / 1000:.1f} s)")
    except Exception as exc:  # noqa: BLE001 - el error real se propaga al estado del job
        if job.get("cancelled"):
            job.update(status="failed", phase="Cancelado", error=CANCELLED_MESSAGE,
                       completed_at=_now())
            log_event("Cancelado por el usuario: no se descarga nada")
        else:
            job.update(status="failed", error=str(exc), phase="Error", completed_at=_now())
            log_event(f"Fallo: {exc}")
            logger.error(f"Generación {job_id} falló: {exc}")
    _save_history()


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.get("/api/info")
async def root() -> dict[str, Any]:
    return {
        "service": "Musicia",
        "mode": "local",
        "engine": settings.acestep.base_url,
        "model": settings.generation.model,
    }


@app.get("/health")
async def health() -> dict[str, Any]:
    """Estado real del motor: si no responde, lo decimos claramente."""
    engine_status = await music.health()
    return {
        "api": "ok",
        "engine_url": settings.acestep.base_url,
        "engine": engine_status,
    }


@app.post("/audio/mix")
async def mix_audio(request: MixRequest) -> dict[str, Any]:
    stem = _safe_name(request.output_name, Path(settings.mixer.default_output_name).stem)
    output_path = _unique_output_path(stem, ".mp3")
    for label, gain in (
        ("base_volume", request.base_volume),
        ("vocal_volume", request.vocal_volume),
    ):
        if not settings.mixer.min_gain_db <= gain <= settings.mixer.max_gain_db:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"{label} debe estar entre {settings.mixer.min_gain_db} y "
                    f"{settings.mixer.max_gain_db} dB"
                ),
            )
    # Las pistas llegan por nombre; la UI dice de qué lista viene cada una.
    def _resolve_track(name: str, kind: str | None) -> str:
        return str(_find_audio(name, kind))

    base_path = _resolve_track(request.base_track, request.base_kind)
    vocal_path = _resolve_track(request.vocal_track, request.vocal_kind)
    try:
        arrangement = plan_vocal_arrangement(Path(base_path), Path(vocal_path), settings.mixer)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    try:
        alignment = None
        if arrangement:
            info = MixerService.arrange_vocals(
                base_path,
                vocal_path,
                str(output_path),
                arrangement,
                request.base_volume,
                request.vocal_volume,
                normalize_lufs=request.normalize_lufs,
                fade_s=settings.mixer.vocal_slice_fade_s,
            )
        else:
            if request.align:
                alignment = _mix_alignment(
                    request.base_track, request.vocal_track, request.base_kind, request.vocal_kind
                )
            info = MixerService.mix_tracks(
                base_path,
                vocal_path,
                str(output_path),
                request.base_volume,
                request.vocal_volume,
                alignment=alignment,
                normalize_lufs=request.normalize_lufs,
            )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Mezcla falló: {exc}")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    _carry_ficha(
        Path(base_path),
        output_path,
        "mix",
        source_name=f"{request.base_track} + {request.vocal_track}",
    )
    return {
        "status": "success",
        "file_path": str(output_path),
        "file_name": output_path.name,
        "alignment": info.get("applied", False),
        "arranged": bool(arrangement),
        "pieces": None if arrangement is None else arrangement["pieces"],
        "loudness": info.get("loudness", {}),
        "target_lufs": TARGET_LUFS,
        "note": (
            arrangement["explanation"] if arrangement else
            None if alignment else
            "No se aplicó cuadre: el tempo no era fiable o el ajuste era excesivo."
        ),
    }


# El cover del motor oye el audio de origen: a fuerza alta la melodía se
# queda, a fuerza baja manda el caption. Estas palabras del prompt eligen
# la fuerza (config, nunca mágicas): "sin melodías" pide soltar el tema,
# "como la original" pide agarrarlo.
_NO_MELODY_WORDS = ("sin melod", "no melody", "without melody", "solo bater", "solo ritmo", "solo percusi")
_LIKE_ORIGINAL_WORDS = ("como la original", "como el original", "similar a la original",
                         "similares a la original", "similares a las originales",
                         "misma melod", "mismas melod", "igual que la original",
                         "igual al original", "fiel a la original", "fiel al original",
                         "like the original")


def remix_cover_strength_for(prompt: str) -> tuple[float, str | None]:
    """Fuerza del cover del remix-IA según lo que pide el prompt.

    Devuelve (fuerza, aviso): "sin melodías" suelta el tema (fuerza baja),
    "como la original" lo agarra (fuerza alta; el cover nativo sí puede
    cumplirlo porque oye el tema). La rama que llama decide qué hace.
    """
    text = (prompt or "").lower()
    if any(w in text for w in _NO_MELODY_WORDS):
        return settings.generation.remix_cover_strength_no_melody, None
    if any(w in text for w in _LIKE_ORIGINAL_WORDS):
        return settings.generation.remix_cover_strength_like_original, "like-original"
    return settings.generation.remix_cover_strength, None


def _mix_alignment(
    base_name: str, vocal_name: str, base_kind: str | None = None, vocal_kind: str | None = None
) -> dict | None:
    """Calcula el plan de cuadre de una pareja de pistas.

    Devuelve None si no es seguro cuadrar (groove poco fiable o ajuste
    demasiado grande): es preferible mezclar sin tocar a destrozarla.
    """
    try:
        base_groove = detect_groove(_find_audio(base_name, base_kind))
        vocal_groove = detect_groove(_find_audio(vocal_name, vocal_kind))
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=f"No se puede cuadrar automáticamente: {exc}",
        ) from exc
    return plan_alignment(base_groove, vocal_groove)


@app.post("/audio/mix/plan")
async def audio_mix_plan(request: MixPlanRequest) -> dict[str, Any]:
    """Propone el ajuste para cuadrar las baterías, sin mezclar nada.

    Responde tempo y fase de cada pista y el ajuste exacto (ratio + desfase)
    que se aplicaría, para que el usuario lo vea antes de darle a MEZCLAR.
    """
    base_path = _find_audio(request.base_track, request.base_kind)
    vocal_path = _find_audio(request.vocal_track, request.vocal_kind)
    try:
        arrangement = plan_vocal_arrangement(base_path, vocal_path, settings.mixer)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if arrangement:
        return {
            "plan": None,
            "arrange": {
                "pieces": arrangement["pieces"],
                "vocal_seconds": arrangement["vocal_seconds"],
                "base_seconds": arrangement["base_seconds"],
                "first_at": arrangement["placements"][0]["at"],
                "last_at": arrangement["placements"][-1]["at"],
            },
            "explanation": arrangement["explanation"],
        }
    plan = _mix_alignment(request.base_track, request.vocal_track, request.base_kind, request.vocal_kind)
    if plan is None:
        return {
            "plan": None,
            "arrange": None,
            "explanation": (
                "No se puede cuadrar con seguridad (el tempo de alguna pista no "
                "es fiable o el ajuste sería enorme). Se mezclará sin tocar el tempo."
            ),
        }
    return {
        "plan": plan,
        "arrange": None,
        "explanation": (
            f"La base va a {plan['base_bpm']:.0f} bpm y la voz a "
            f"{plan['vocal_bpm']:.0f} bpm: se ajusta el tempo "
            f"×{plan['tempo_ratio']:.3f} y se desplaza la voz "
            f"{plan['delay_ms']:+.0f} ms para que la batería cuadre. "
            "El tono no cambia."
        ),
    }


@app.get("/audio/groove/{name}")
async def audio_groove(name: str, source_kind: str | None = None) -> dict[str, Any]:
    """Tempo y fase del golpe de una pista (lo que usa el cuadre y el remixer)."""
    try:
        return detect_groove(_find_audio(name, source_kind))
    except HTTPException:
        raise
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def _tempo_plan(mode: str, bpm: float | None, current_bpm: float) -> tuple[float, str]:
    """Traduce half | double | bpm al factor de ffmpeg. Otro modo es un error."""
    if mode == "bpm":
        if not bpm:
            raise ValueError("Indica el BPM objetivo")
        return float(bpm) / float(current_bpm), f"{round(bpm)}bpm"
    if mode == "double":
        return 2.0, "doble"
    if mode == "half":
        return 0.5, "medio"
    raise ValueError("mode debe ser half, double o bpm")


@app.post("/audio/tempo")
async def audio_tempo(request: TempoRequest) -> dict[str, Any]:
    """Fuerza el tempo: a un BPM concreto, a medio tiempo o a doble tiempo."""
    source = _find_audio(request.file_name, request.source_kind)
    try:
        current = detect_groove(source)
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    try:
        factor, marker = _tempo_plan(request.mode, request.bpm, float(current["bpm"]))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    stem = request.output_name or _derive_stem(request.file_name, marker)
    out = _unique_output_path(_safe_name(stem, DEFAULT_STEM), ".mp3")
    try:
        info = force_tempo(source, out, factor)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    _carry_ficha(source, out, "tempo")

    try:
        after = detect_groove(out)
    except ValueError:
        after = None
    return {
        "status": "success",
        "source_bpm": current["bpm"],
        "result_bpm": after["bpm"] if after else None,
        **info,
    }


@app.post("/audio/loop")
async def audio_loop(request: LoopRequest) -> dict[str, Any]:
    """Saca un loop. Sin segundos: N compases de 4/4 desde el primer golpe."""
    source = _find_audio(request.file_name, request.source_kind)
    meta: dict[str, Any] = {}
    if request.seconds is None:
        try:
            groove = await asyncio.to_thread(detect_groove, source)
        except (ValueError, FileNotFoundError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        if float(groove.get("confidence") or 0) < MIN_GROOVE_CONFIDENCE:
            raise HTTPException(
                status_code=422,
                detail=(
                    "No hay un tempo claro para cortar los compases. "
                    "Sin un golpe medible no se puede afirmar cuántos son."
                ),
            )
        bars = int(settings.mixer.loop_bars)
        beats = int(settings.mixer.beats_per_bar)
        bpm = float(groove["bpm"])
        try:
            seconds = bars_duration_seconds(bpm, bars, beats)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        if not 1 < seconds <= 120:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"{bars} compases de {beats}/4 a {bpm:.0f} bpm duran {seconds:.1f} s, "
                    "fuera de 1–120 s."
                ),
            )
        start = first_beat_seconds(groove)
        duration = float(groove.get("duration_seconds") or 0)
        if start + seconds > duration + 0.05:
            left = max(0.0, duration - start)
            raise HTTPException(
                status_code=422,
                detail=(
                    f"No caben {bars} compases desde el golpe: hacen falta {seconds:.1f} s "
                    f"y desde {start:.2f} s quedan {left:.1f} s."
                ),
            )
        meta = {"bpm": round(bpm, 2), "bars": bars, "beats_per_bar": beats}
    else:
        seconds = float(request.seconds)
        start = float(request.start_seconds)

    stem = request.output_name or (
        f"{Path(request.file_name).stem}-loop{meta['bars']}c"
        if meta
        else f"{Path(request.file_name).stem}-loop{int(seconds)}s"
    )
    out = _unique_output_path(_safe_name(stem, DEFAULT_STEM), ".mp3")
    try:
        info = await asyncio.to_thread(make_loop, source, out, seconds, start)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    _carry_ficha(source, out, "loop")
    return {"status": "success", "source": source.name, **meta, **info}


@app.post("/audio/crossfade")
async def audio_crossfade(request: CrossfadeRequest) -> dict[str, Any]:
    """Funde 2 o más pistas igualando su tempo y su volumen (mezcla de DJ)."""
    if len(request.tracks) < 2:
        raise HTTPException(status_code=400, detail="Indica al menos dos pistas")
    kinds = request.track_kinds or []
    if kinds and len(kinds) != len(request.tracks):
        raise HTTPException(status_code=400, detail="track_kinds tiene que traer un kind por pista")
    sources = [
        _find_audio(name, kinds[i] if i < len(kinds) else None)
        for i, name in enumerate(request.tracks)
    ]
    stem = request.output_name or f"crossfade-{len(sources)}"
    out = _unique_output_path(_safe_name(stem, DEFAULT_STEM), ".mp3")
    try:
        info = crossfade(sources, out, request.fade_seconds)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    _carry_ficha(
        sources[0],
        out,
        "crossfade",
        source_name=" + ".join(path.name for path in sources),
    )
    return {"status": "success", "tracks_used": sources, "loudness": measure_loudness(out), **info}


remix_jobs: dict[str, dict[str, Any]] = {}


@app.post("/audio/remix/ai")
async def audio_remix_ai(request: AiRemixRequest, background_tasks: BackgroundTasks) -> dict[str, Any]:
    """Remix con IA en pasos visibles: separa la voz, crea la base y mezcla.

    Es lo que pide un bootleg: la misma voz con música nueva hecha desde un
    prompt. Cada paso se refleja en `phase`/`events` para que la UI nunca
    parezca colgada.
    """
    source = _find_audio(request.file_name, request.source_kind)
    if (busy := _gpu_busy()):
        raise HTTPException(status_code=409, detail=busy)
    health = await music.health()
    if not health.get("reachable"):
        raise HTTPException(
            status_code=503,
            detail="El motor de música no está activo. Abre Musicia.exe y vuelve a intentarlo.",
        )

    try:
        # El análisis abre el archivo. En un hilo: /health tiene que seguir contestando.
        groove = await asyncio.to_thread(detect_groove, source)
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    job_id = uuid.uuid4().hex
    stem = _safe_name(request.output_name or Path(request.file_name).stem, DEFAULT_STEM)
    _remember(remix_jobs, job_id, {
        "job_id": job_id,
        "status": "running",
        "phase": "Preparando",
        "events": [],
        "source": source.name,
        "source_dir": "uploads" if _uploads_dir().resolve() in source.resolve().parents else "outputs",
        "prompt": request.prompt,
        "base_bpm": groove["bpm"],
        "started": time.monotonic(),
        "created_at": _now(),
    })
    background_tasks.add_task(_run_ai_remix, job_id, source, request, groove, Path(stem).stem)
    return {"status": "accepted", "job_id": job_id, "base_bpm": groove["bpm"]}


async def _mezclar_voz_en_base(
    base_path: Path,
    vocals_path: Path,
    base_bpm: int | None,
    groove: dict,
    mix_name: str,
    step: Any,
) -> tuple[Path, dict]:
    """Cuadra la voz separada sobre una base nueva y la mezcla (modo voz).

    Primero `plan_vocal_arrangement` (reparte la voz en trozos sin
    estirarla); si no hay arreglo posible, reserva con `mix_tracks` y el
    cuadre de tempos. Devuelve (mezcla, info de mezcla).
    """
    def _arrangement() -> dict | None:
        return plan_vocal_arrangement(base_path, vocals_path, settings.mixer, base_bpm=base_bpm)

    try:
        arrangement = await asyncio.to_thread(_arrangement)
    except ValueError as exc:
        raise MusicEngineError(str(exc)) from exc
    mixed = _unique_output_path(_safe_name(mix_name, DEFAULT_STEM), ".mp3")
    if arrangement:
        step(arrangement["explanation"])
        info = await asyncio.to_thread(
            MixerService.arrange_vocals,
            str(base_path),
            str(vocals_path),
            str(mixed),
            arrangement,
            normalize_lufs=True,
            fade_s=settings.mixer.vocal_slice_fade_s,
        )
        return mixed, info

    def _alignment() -> dict | None:
        if not base_bpm:
            try:
                nueva = detect_groove(base_path)
            except (ValueError, FileNotFoundError):
                return None
        else:
            nueva = {"bpm": float(base_bpm), "confidence": 1.0, "phase_ms": 0.0}
        return plan_alignment(nueva, groove)

    alignment = await asyncio.to_thread(_alignment)
    if alignment is None:
        step("La voz entra a su tempo: estirarla la deformaría.")
    else:
        step(
            f"Voz a {alignment['vocal_bpm']:.0f} bpm, base a "
            f"{alignment['base_bpm']:.0f}: se cuadra ×{alignment['tempo_ratio']:.2f}."
        )
    info = await asyncio.to_thread(
        MixerService.mix_tracks,
        str(base_path),
        str(vocals_path),
        str(mixed),
        alignment=alignment,
        normalize_lufs=True,
    )
    return mixed, info


async def _modo_conservar_voz(
    job_id: str,
    job: dict[str, Any],
    source: Path,
    request: AiRemixRequest,
    groove: dict,
    stem: str,
    caption: str,
    step: Any,
    on_update: Any,
) -> None:
    """Modo voz (spec/02 [R5]): tu voz se conserva, la música es nueva.

    Separa la voz (demucs), genera base instrumental con el SFT al tempo
    del tema (medido; el pedido manda) y la cuadra debajo de la voz. La
    letra no se usa: la voz la pone tu grabación. Las variantes del batch
    se mezclan todas; el usuario elige en BIBLIOTECA.
    """
    started = job.get("started") or time.monotonic()
    step("Modo conservar voz: separo tu voz y genero música nueva debajo.")
    if (request.lyrics or "").strip():
        step("En este modo la letra no se usa: la voz la pone tu grabación.")
    step("Separando la voz de la pista original…")
    # demucs es un proceso largo. Si corre en el bucle de la API,
    # /health no contesta y la pastilla dice APAGADO con el motor vivo.
    stems = await asyncio.to_thread(
        SeparatorService.separate, source, settings.outputs_dir, f"{stem}-orig"
    )
    _throw_if_cancelled(job)
    vocals_path = settings.outputs_dir / stems["vocals"]
    _carry_ficha(source, vocals_path, "vocals")
    # La base separada por demucs también lleva ficha: sin ella aparece en
    # BIBLIOTECA como una versión final cuando es una pieza intermedia.
    _carry_ficha(source, settings.outputs_dir / stems["base"], "instrumental")
    step(f"Voz separada ({stems['device']}): se guarda aparte y mezclada.")
    measured_bpm = float(groove.get("bpm") or 0)
    base_bpm = int(round(request.bpm)) if request.bpm else (int(round(measured_bpm)) or None)
    if base_bpm:
        step(f"La base nueva se pide a {base_bpm} bpm ({'tu tempo' if request.bpm else 'el medido de tu tema'}).")
    else:
        step("Sin tempo fiable: la base sale al aire que le dé el estilo.")
    source_s = float(groove.get("duration_seconds") or 0)
    duration = request.duration_seconds or min(source_s or 120.0, settings.generation.max_duration_seconds)
    step(f"Pidiendo la base nueva ({duration:g} s) con tu prompt, modelo estricto…")
    task_id, _ = await music.submit(
        GenerationRequest(
            prompt=caption,
            lyrics=None,
            instrumental=True,
            duration_seconds=duration,
            bpm=base_bpm,
            model=settings.generation.remix_model,
        )
    )
    final = await music.wait(task_id, on_update=on_update)
    _throw_if_cancelled(job)
    if not final.succeeded:
        raise MusicEngineError(final.error or "El motor terminó con error")
    tracks = [item for item in final.tracks if item.file]
    if not tracks:
        raise MusicEngineError("El motor no devolvió audio")
    saved: list[str] = []
    for index, track in enumerate(tracks):
        suffix = "" if len(tracks) == 1 else f"-v{index + 1}"
        base_path = _unique_output_path(_safe_name(f"{stem}-base{suffix}", DEFAULT_STEM), ".mp3")
        await music.download(track.file, base_path)
        # La base es pieza intermedia (la final es la mezcla con tu voz):
        # task "instrumental" para que BIBLIOTECA la aparte de las finales.
        _carry_ficha(source, base_path, "instrumental", prompt=request.prompt)
        step(f"Cuadrando tu voz sobre la base {index + 1}/{len(tracks)}…")
        mixed, info = await _mezclar_voz_en_base(
            base_path, vocals_path, base_bpm, groove,
            f"{stem}-con-voz{suffix}", step,
        )
        _throw_if_cancelled(job)
        _carry_ficha(source, mixed, "remix", prompt=request.prompt)
        saved.append(mixed.name)
    job["elapsed_seconds"] = round(time.monotonic() - started, 1)
    loudness = await asyncio.to_thread(measure_loudness, settings.outputs_dir / saved[0])
    step(f"Listo: {len(saved)} mezcla(s) con tu voz en BIBLIOTECA.")
    job.update(
        status="succeeded",
        phase="Listo",
        result={
            "mix": saved[0],
            "variants": saved,
            "vocals": vocals_path.name,
            "with_vocals": True,
            "mode": "voz",
        },
        loudness=loudness,
    )


async def _run_ai_remix(
    job_id: str, source: Path, request: AiRemixRequest, groove: dict, stem: str
) -> None:
    """Ejecuta el remix con IA paso a paso (stem → base IA → mezcla)."""
    job = remix_jobs[job_id]
    started = time.monotonic()

    def step(text: str) -> None:
        _throw_if_cancelled(job)
        job["phase"] = text
        job["events"].append({"t": round(time.monotonic() - started, 1), "text": text})
        del job["events"][:-30]
        job["elapsed_seconds"] = round(time.monotonic() - started, 1)
        logger.info(f"[remix {job_id[:8]}] {text}")

    if job.get("cancelled"):
        logger.info(f"Remix {job_id[:8]} ya cancelado antes de arrancar: no se toca nada")
        return

    try:
        gen = settings.generation
        guidance_remix = gen.guidance_by_model.get(gen.remix_model, gen.guidance_scale)
        steps_remix = gen.steps_by_model.get(gen.remix_model, gen.inference_steps)
        step(
            f"Modelo del motor: {gen.remix_model} (guidance {guidance_remix:g}, "
            f"{steps_remix} pasos: el prompt pesa más que en el turbo)."
        )
        # El remix usa el MISMO caption compuesto que CREAR (spec/02 [R2]).
        caption_remix = style_caption(request.prompt)
        if caption_remix != request.prompt:
            step("Caption compuesto con el estilo que pides (igual que CREAR).")

        def on_update(status: Any) -> None:
            _throw_if_cancelled(job)
            prev = job.get("engine_phase") or ""
            job["engine_progress"] = status.progress
            job["progress_ratio"] = status.progress
            text = (status.progress_text or status.stage or "").strip()
            job["engine_phase"] = text
            # La UI pinta `phase`. Un corte del sondeo no puede dejarla en Error.
            job["phase"] = _human_phase(status.status, text, status.stage)
            job["status"] = "running"
            job["elapsed_seconds"] = round(time.monotonic() - started, 1)
            if text and text != prev:
                job["events"].append({"t": job["elapsed_seconds"], "text": text})
                del job["events"][:-30]

        # Modo conservar-voz (spec/02 [R5]): tu voz se separa y la música
        # es nueva; la fuerza no aplica y la letra no se usa.
        if request.mode == "voz":
            await _modo_conservar_voz(
                job_id, job, source, request, groove, stem, caption_remix, step, on_update
            )
            return

        # Cover nativo (spec/02 [R2]): el motor OYE la pista y la reviste
        # del estilo pedido, conservando la estructura (música-guía del
        # modelo: la UI «Remix» es una operación cover). Fuerza manual manda;
        # en auto la deduce el prompt (doc: 0,3-0,5 cambios grandes,
        # 0,7-0,9 sutiles).
        auto_strength, _melody_note = remix_cover_strength_for(request.prompt)
        if request.cover_strength is None:
            strength = auto_strength
            step(f"Fuerza auto {strength:g} según lo que pides.")
        else:
            strength = min(max(float(request.cover_strength), 0.0), 1.0)
            step(f"Fuerza manual {strength:g} (0 = otro tema, 1 = casi el mismo).")
        escrita = (request.lyrics or "").strip()
        letra = escrita if lyrics_are_song(escrita) else ""
        if escrita and not letra:
            step("La letra no es una canción: el reestilo sale instrumental.")
        elif letra:
            step("La versión canta tu letra nueva con el estilo pedido.")
        else:
            step("Sin letra nueva: el reestilo sale instrumental (el motor no clona tu voz).")
        if request.duration_seconds:
            step(f"Duración pedida: {float(request.duration_seconds):g} s (si no, la del tema).")
        if request.bpm:
            step(f"Tempo pedido: {float(request.bpm):g} bpm (si no, el del tema).")
        step(f"Reestilando «{source.name}»: el motor oye tu pista, no una base nueva…")
        task_id, _ = await music.submit(
            GenerationRequest(
                prompt=caption_remix,
                lyrics=letra or None,
                instrumental=not letra,
                duration_seconds=request.duration_seconds,
                bpm=int(round(request.bpm)) if request.bpm else None,
                model=settings.generation.remix_model,
                task_type="cover",
                source_path=str(source),
                cover_strength=strength,
            )
        )
        final = await music.wait(task_id, on_update=on_update)
        _throw_if_cancelled(job)
        if not final.succeeded:
            raise MusicEngineError(final.error or "El motor terminó con error")
        # Batch 2 (spec/02 [R3]): el motor devuelve hasta 2 variantes; se
        # guardan TODAS y el usuario elige en BIBLIOTECA. Sin batch, una sola.
        tracks = [item for item in final.tracks if item.file]
        if not tracks:
            raise MusicEngineError("El motor no devolvió audio")
        step(f"Descargando {len(tracks)} variante(s)…")
        saved: list[str] = []
        for index, track in enumerate(tracks):
            name = stem if len(tracks) == 1 else f"{stem}-v{index + 1}"
            out_path = _unique_output_path(_safe_name(name, DEFAULT_STEM), ".mp3")
            await music.download(track.file, out_path)
            _carry_ficha(source, out_path, "remix", prompt=request.prompt)
            saved.append(out_path.name)
        loudness = await asyncio.to_thread(measure_loudness, settings.outputs_dir / saved[0])
        step(f"Reestilo listo: {len(saved)} variante(s) en BIBLIOTECA.")
        job.update(
            status="succeeded",
            phase="Listo",
            result={
                "mix": saved[0],
                "variants": saved,
                "with_vocals": bool(letra),
                "cover_strength": strength,
            },
            loudness=loudness,
        )
    except Exception as exc:  # noqa: BLE001
        if job.get("cancelled"):
            job.update(status="failed", phase="Cancelado", error=CANCELLED_MESSAGE,
                       elapsed_seconds=round(time.monotonic() - started, 1))
        else:
            logger.error(f"Remix IA falló ({job_id}): {exc}")
            job.update(status="failed", phase="Error", error=str(exc),
                       elapsed_seconds=round(time.monotonic() - started, 1))
    _save_history()


@app.get("/audio/remix/ai/{job_id}")
async def audio_remix_ai_status(job_id: str) -> dict[str, Any]:
    """Progreso real del remix con IA (pasos, eventos y resultado)."""
    job = remix_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Ese remix no existe")
    return _public_side_job(job)


@app.get("/audio/separate/status")
async def audio_separate_status() -> dict[str, Any]:
    """¿Está el motor de separación instalado? (la UI lo dice, no lo inventa)"""
    return {
        "available": separator_available(),
        "device": pick_device(),
        "message": (
            "Separación de voces disponible."
            if separator_available()
            else "Separación no instalada: sigue usándose el mezclado normal."
        ),
    }


separate_jobs: dict[str, dict[str, Any]] = {}

_GPU_ACTIVE = {"queued", "running"}


def _gpu_busy() -> str | None:
    """En 8 GB solo cabe un trabajo pesado. El segundo espera."""
    if any(job.get("status") in _GPU_ACTIVE for job in jobs.values()):
        return "Hay una generación en la GPU. Espera a que termine: en 8 GB no caben dos a la vez."
    if any(job.get("status") in _GPU_ACTIVE for job in remix_jobs.values()):
        return "Hay un remix con IA en curso. Espera a que termine antes de usar la GPU."
    if any(job.get("status") in _GPU_ACTIVE for job in separate_jobs.values()):
        return "Hay una separación en curso. demucs y el motor no caben juntos en 8 GB."
    return None


async def _run_separate(job_id: str, source: Path, stem: str) -> None:
    """demucs en un hilo: la API sigue respondiendo mientras separa."""
    job = separate_jobs[job_id]
    if job.get("cancelled"):
        logger.info(f"Separación {job_id[:8]} ya cancelada antes de arrancar: no se toca nada")
        return
    job["status"] = "running"
    _push_event(job, "Separando la voz")
    try:
        result = await asyncio.to_thread(
            SeparatorService.separate, source, settings.outputs_dir, stem
        )
        _throw_if_cancelled(job)
        _carry_ficha(source, settings.outputs_dir / result["vocals"], "vocals")
        _carry_ficha(source, settings.outputs_dir / result["base"], "instrumental")
        _push_event(job, "Voces y base listas")
        job.update(
            status="succeeded",
            phase="Lista",
            device=result["device"],
            vocals=result["vocals"],
            base=result["base"],
        )
    except Exception as exc:  # noqa: BLE001
        job["elapsed_seconds"] = _live_elapsed(job)
        if job.get("cancelled"):
            job.update(status="failed", phase="Cancelado", error=CANCELLED_MESSAGE)
        else:
            logger.error(f"Separación {job_id} falló: {exc}")
            job.update(status="failed", phase="Error", error=str(exc))
    _save_history()


@app.post("/audio/separate")
async def audio_separate(request: SeparateRequest, background_tasks: BackgroundTasks) -> dict[str, Any]:
    """Arranca la extracción de voz y base. El trabajo sigue en GET /audio/separate/{job_id}."""
    if (busy := _gpu_busy()):
        raise HTTPException(status_code=409, detail=busy)
    source = _find_audio(request.file_name, request.source_kind)
    stem = _safe_name(
        request.output_name or Path(request.file_name).stem, "separacion"
    )
    stem = Path(stem).stem
    job_id = uuid.uuid4().hex
    _remember(separate_jobs, job_id, {
        "job_id": job_id,
        "status": "queued",
        "phase": "En cola",
        "source": source.name,
        "prompt": source.name,
        "error": None,
        "events": [],
        "started": time.monotonic(),
        "created_at": _now(),
    })
    _push_event(separate_jobs[job_id], "En cola")
    background_tasks.add_task(_run_separate, job_id, source, _safe_name(stem, "separacion"))
    return {"job_id": job_id, "status": "queued"}


@app.get("/audio/separate/{job_id}")
async def audio_separate_status_job(job_id: str) -> dict[str, Any]:
    job = separate_jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Esa separación no existe")
    return _public_side_job(job)


@app.get("/music/config")
async def music_config() -> dict[str, Any]:
    """Valores por defecto y límites del motor, para que el frontend no los invente."""
    return asdict(settings.generation)


@app.get("/music/models")
async def music_models() -> dict[str, Any]:
    """Qué modelo está permitido en esta GPU y cuáles ve el motor.

    No cambia el modelo. Cargar otro descargaría el turbo y, con el XL o el
    base, puede no caber en 8 GB.
    """
    configured = settings.generation.model
    allowed = list(settings.generation.allowed_models)
    available: list[str] = []
    loaded = None
    lm_loaded = None
    error = None
    try:
        info = await music.engine_info()
        loaded = info.get("loaded_model")
        lm_loaded = info.get("loaded_lm_model")
        data = await music.list_models()
        rows: list[Any] = []
        if isinstance(data, dict) and isinstance(data.get("models"), list):
            rows = data["models"]
        elif isinstance(data, dict) and isinstance(data.get("data"), list):
            rows = data["data"]
        elif isinstance(data, list):
            rows = data
        for item in rows:
            if not isinstance(item, dict):
                continue
            ident = str(item.get("id") or item.get("name") or "")
            short = ident.split("/")[-1].strip()
            if short and short not in available:
                available.append(short)
    except (MusicEngineError, Exception) as exc:  # noqa: BLE001 - el listado no debe tumbar el panel
        error = str(exc)
    return {
        "configured": configured,
        "allowed": allowed,
        "remix_model": settings.generation.remix_model,
        "loaded": loaded,
        "loaded_lm": lm_loaded,
        "available": available,
        "vram_free_mb": await asyncio.to_thread(free_vram_mb),
        "error": error,
        "note": (
            "En 8 GB cabe un modelo cada vez: el motor cambia entre turbo y remix "
            "al vuelo. El XL y el base no se cargan desde aquí."
        ),
    }


@app.post("/music/generate")
async def generate_music(
    request: MusicGenRequest, background_tasks: BackgroundTasks
) -> dict[str, Any]:
    """Envía la generación al motor local y sigue el resultado en segundo plano."""
    if (busy := _gpu_busy()):
        raise HTTPException(status_code=409, detail=busy)
    job_id = uuid.uuid4().hex
    audio_format = request.audio_format or settings.generation.audio_format
    # Tarea y modelo efectivos: VERSIÓN/TRAMO (cover/repaint) van al modelo de
    # remix si no se pide otro. El mismo criterio aplica build_payload.
    task = request.task_type or settings.generation.task_type
    model = settings.generation.model_for(task, request.model)
    # Nombre elegido por el usuario; si no, "pista-sin-nombre" numerado (spec E1).
    suffix = f".{audio_format}"
    stem = _safe_name(request.output_name, DEFAULT_STEM)
    output_name = _unique_output_path(stem, suffix).name

    # Fail-fast (deuda T7): si el motor no responde, no colgar la petición.
    health = await music.health()
    if not health.get("reachable"):
        raise HTTPException(
            status_code=503,
            detail=(
                "El motor de música no está activo. Ejecuta scripts\\open_musicia.ps1 "
                "o deja los servicios activos al cerrar la ventana."
            ),
        )

    try:
        # El caption compuesto (frase + estilo EN + detalles) viaja al
        # motor en TODOS los caminos (CREAR, versión, tramo, otra
        # versión, re-crear): antes solo lo componían MEJORAR y el
        # remix IA, y el resto mandaba la frase en crudo. La ficha y
        # la barra guardan la frase del usuario (job["prompt"]).
        caption = style_caption(request.prompt)
        task_id, initial_status = await music.submit(
            GenerationRequest(
                prompt=caption,
                lyrics=request.lyrics,
                instrumental=request.instrumental,
                duration_seconds=request.duration_seconds,
                bpm=request.bpm,
                key_scale=request.key_scale,
                time_signature=request.time_signature,
                language=request.language,
                inference_steps=request.inference_steps,
                guidance_scale=request.guidance_scale,
                seed=request.seed,
                batch_size=request.batch_size,
                audio_format=audio_format,
                model=model,
                task_type=task,
                source_path=str(_find_audio(request.source_name, request.source_kind)) if request.source_name else None,
                repaint_start=request.repaint_start,
                repaint_end=request.repaint_end,
                cover_strength=request.cover_strength,
                use_format=request.use_format,
            )
        )
    except MusicEngineError as exc:
        logger.error(f"No se pudo enviar la generación al motor: {exc}")
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    _remember(jobs, job_id, {
        "job_id": job_id,
        "engine_task_id": task_id,
        "status": initial_status,
        "engine_status": 0,
        "prompt": request.prompt,
        "instrumental": (
            settings.generation.instrumental if request.instrumental is None else request.instrumental
        ),
        "output_name": output_name,
        "lyrics": request.lyrics,
        "bpm": request.bpm,
        "key_scale": request.key_scale,
        "time_signature": request.time_signature,
        "model": model,
        "task_type": task,
        "source_name": request.source_name,
        "seed": request.seed,
        "created_at": _now(),
        "progress": "",
        "progress_ratio": 0.0,
        "stage": "queued",
        "phase": "Enviada al motor local",
        "elapsed_seconds": 0.0,
        "events": [],
        "duration_seconds": None,
        "error": None,
    })
    if caption != (request.prompt or ""):
        jobs[job_id]["events"].append({"t": 0.0, "text": "Caption compuesto con el estilo que pides."})
        logger.info("Caption compuesto con el estilo que pide el prompt (igual que CREAR).")
    background_tasks.add_task(_finalize_generation, job_id)

    return {
        "status": initial_status,
        "job_id": job_id,
        "engine_task_id": task_id,
        "status_url": f"/music/status/{job_id}",
    }


@app.get("/music/status/{job_id}")
async def music_status(job_id: str) -> dict[str, Any]:
    job = jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Generación no encontrada")
    payload = dict(job)
    if job["status"] in {"succeeded"}:
        payload["audio_url"] = f"/music/audio/{job['output_name']}"
    return payload


def _live_elapsed(job: dict[str, Any]) -> float:
    """Segundos desde el arranque si el trabajo sigue. Si no, el valor guardado."""
    started = job.get("started")
    if isinstance(started, (int, float)) and job.get("status") in _GPU_ACTIVE:
        return round(time.monotonic() - started, 1)
    return float(job.get("elapsed_seconds") or 0.0)


def _push_event(job: dict[str, Any], text: str) -> None:
    """Anota fase y evento con el reloj real. La UI enseña los últimos."""
    job["phase"] = text
    elapsed = _live_elapsed(job)
    job["elapsed_seconds"] = elapsed
    events = job.setdefault("events", [])
    events.append({"t": elapsed, "text": text})
    del events[:-30]


def _remember(store: dict[str, Any], job_id: str, job: dict[str, Any]) -> None:
    """Guarda un job podando historial viejo: los activos no se tocan nunca,
    de los terminados se quedan los últimos `job_history` (config, 30).
    Sin esto los tres diccionarios crecen sin límite en sesiones largas y
    /music/jobs (sondeado cada 3 s) engorda en cada respuesta."""
    store[job_id] = job
    cap = settings.job_history
    terminal = [jid for jid, j in store.items() if j.get("status") not in _GPU_ACTIVE]
    if len(terminal) > cap:
        for jid in sorted(terminal, key=lambda j: store[j].get("created_at") or "")[: len(terminal) - cap]:
            del store[jid]


CANCELLED_MESSAGE = "Cancelado por el usuario"

# Historial en disco (spec/02 [Q1]): la API olvida al reiniciar; el fichero
# no. Estado de ejecución, no biblioteca: fuera de outputs/ y con gitignore.
HISTORY_FILE = BACKEND_DIR / "job_history.json"

# Campos que sobreviven al reinicio por familia (solo lo que la UI enseña;
# nada de handles ni tiempos monotonicos, que no valen tras arrancar).
_MUSIC_KEPT = (
    "job_id", "status", "phase", "prompt", "instrumental", "output_name",
    "lyrics", "bpm", "key_scale", "time_signature", "model", "task_type",
    "source_name", "seed", "created_at", "completed_at", "elapsed_seconds",
    "duration_seconds", "error",
)
_REMIX_KEPT = (
    "job_id", "status", "phase", "source", "source_dir", "prompt", "base_bpm",
    "created_at", "completed_at", "elapsed_seconds", "result", "error",
)
_SEPARATE_KEPT = (
    "job_id", "status", "phase", "source", "prompt", "device", "vocals",
    "base", "created_at", "completed_at", "elapsed_seconds", "error",
)


def _throw_if_cancelled(job: dict[str, Any]) -> None:
    """Aborta el runner si el usuario lo paró: la excepción la recoge el
    except del runner y deja failed/Cancelado (nunca pisa con otro estado)."""
    if job.get("cancelled"):
        raise MusicEngineError(CANCELLED_MESSAGE)


def _snapshot_job(kept: tuple[str, ...], job: dict[str, Any]) -> dict[str, Any]:
    snap = {key: job.get(key) for key in kept}
    snap["events"] = list((job.get("events") or [])[-5:])
    snap["restored"] = True
    return snap


def _save_history() -> None:
    """Foto del historial en disco: se llama al terminar cada trabajo y al
    cancelar. Escritura atómica (tmp + replace) para no dejar medio fichero."""
    try:
        data = {
            "music": [_snapshot_job(_MUSIC_KEPT, j) for j in jobs.values()],
            "remix": [_snapshot_job(_REMIX_KEPT, j) for j in remix_jobs.values()],
            "separate": [_snapshot_job(_SEPARATE_KEPT, j) for j in separate_jobs.values()],
        }
        tmp = HISTORY_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, HISTORY_FILE)
    except OSError as exc:
        logger.warning(f"No se pudo guardar el historial de trabajos: {exc}")


def _load_history() -> None:
    """Al arrancar: recupera el historial y marca interrumpidos los que
    quedaron activos (el motor perdió su tarea al caer la API)."""
    try:
        raw = HISTORY_FILE.read_text(encoding="utf-8")
    except OSError:
        return
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        logger.warning(f"Historial ilegible, se empieza vacío: {exc}")
        return
    if not isinstance(data, dict):
        return
    for key, store in (("music", jobs), ("remix", remix_jobs), ("separate", separate_jobs)):
        rows = data.get(key)
        if not isinstance(rows, list):
            continue
        for item in rows:
            if not isinstance(item, dict) or not item.get("job_id"):
                continue
            item.setdefault("events", [])
            if item.get("status") in _GPU_ACTIVE:
                item["status"] = "failed"
                item["phase"] = "Interrumpido"
                item["error"] = "Interrumpido: la API se reinició antes de terminar"
                item["completed_at"] = _now()
            _remember(store, item["job_id"], item)
    logger.info(f"Historial recuperado de {HISTORY_FILE.name}")


def _public_side_job(job: dict[str, Any]) -> dict[str, Any]:
    """El sondeo ve el mismo reloj y el mismo porcentaje que la cola."""
    view = dict(job)
    view["elapsed_seconds"] = _live_elapsed(job)
    ratio = job.get("progress_ratio")
    if ratio is None:
        ratio = job.get("engine_progress") or 0.0
    view["progress_ratio"] = float(ratio or 0.0)
    view["events"] = list((job.get("events") or [])[-5:])
    return view


def _side_job_view(job: dict[str, Any]) -> dict[str, Any]:
    """Remix IA y separación, en la misma cola que las generaciones."""
    result = job.get("result") if isinstance(job.get("result"), dict) else {}
    output_name = result.get("mix") or result.get("base") or job.get("base")
    status = job.get("status")
    return {
        "job_id": job["job_id"],
        "status": status,
        "prompt": job.get("prompt") or job.get("source") or "",
        "progress": "",
        "progress_ratio": job.get("engine_progress") or 0.0,
        "stage": job.get("source") or "",
        "phase": job.get("phase") or "",
        "elapsed_seconds": _live_elapsed(job),
        "events": (job.get("events") or [])[-5:],
        "output_name": output_name,
        "duration_seconds": None,
        "error": job.get("error"),
        "created_at": "",
        "audio_url": f"/music/audio/{output_name}" if status == "succeeded" and output_name else None,
    }


def _job_view(job: dict[str, Any]) -> dict[str, Any]:
    """Vista de un job para la cola: progreso humano y tiempos incluidos."""
    return {
        "job_id": job["job_id"],
        "status": job["status"],
        "prompt": job.get("prompt", ""),
        "progress": job.get("progress", ""),
        "progress_ratio": job.get("progress_ratio", 0.0),
        "stage": job.get("stage", ""),
        "phase": job.get("phase", ""),
        "elapsed_seconds": job.get("elapsed_seconds", 0.0),
        "events": job.get("events", [])[-5:],
        "output_name": job.get("output_name"),
        "duration_seconds": job.get("duration_seconds"),
        "error": job.get("error"),
        "created_at": job.get("created_at"),
        "audio_url": f"/music/audio/{job['output_name']}" if job["status"] == "succeeded" else None,
    }


@app.get("/music/jobs")
async def music_jobs() -> dict[str, Any]:
    """Cola de trabajos de esta sesión: activos y últimos terminados.

    La UI la consulta para mostrar el panel de trabajos; si se cierra la
    ventana, los jobs siguen aquí (mientras la API viva).
    """
    order = {"running": 0, "queued": 1, "succeeded": 2, "failed": 3}
    views = [_job_view(j) for j in jobs.values()]
    views.extend(_side_job_view(j) for j in remix_jobs.values())
    views.extend(_side_job_view(j) for j in separate_jobs.values())
    items = sorted(
        views,
        key=lambda j: (order.get(j["status"], 4), j.get("created_at") or ""),
    )
    return {"items": items, "library_version": _library_version()}


def _library_version() -> float:
    """Huella de lo que enseña BIBLIOTECA: el mtime más nuevo de outputs/*.mp3
    (el mismo glob que /music/library). Cualquier alta, mezcla, versión o
    borrado que cambie lo visible cambia la huella, y la UI refresca al
    verla cambiar: no depende de transiciones de la cola (que fallan con
    trabajos encadenados o endpoints síncronos sin job, spec/02 [R1])."""
    newest = 0.0
    try:
        paths = settings.outputs_dir.glob("*.mp3")
    except OSError:
        return newest
    for path in paths:
        try:
            mtime = path.stat().st_mtime
        except OSError:
            continue
        if mtime > newest:
            newest = mtime
    return newest


def _job_uses_motor(job: dict[str, Any], store: str) -> bool:
    """¿Merece la pena matar el motor al cancelar? Solo si estaba trabajando:
    una generación en marcha sí; una separación (demucs local) o algo aún en
    cola, no. Un remix separando la voz tampoco: el motor sigue libre."""
    if job.get("status") != "running":
        return False
    if store == "separate":
        return False
    if store == "remix" and str(job.get("phase") or "").startswith("Separando"):
        return False
    return True


def _motor_pid_on_port(port: int) -> int | None:
    """PID escuchando en el puerto (stdlib: netstat). None si no hay nadie."""
    try:
        proc = subprocess.run(
            ["netstat", "-ano", "-p", "TCP"], capture_output=True, text=True, timeout=15,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    for line in proc.stdout.splitlines():
        parts = line.split()
        if len(parts) < 5 or parts[0] != "TCP" or parts[3] != "LISTENING":
            continue
        host_port = parts[1].rsplit(":", 1)
        if len(host_port) != 2 or host_port[1] != str(port):
            continue
        try:
            return int(parts[4])
        except ValueError:
            continue
    return None


def _port_is_free(port: int) -> bool:
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    probe.settimeout(1.0)
    try:
        probe.connect(("127.0.0.1", port))
        return False
    except OSError:
        return True
    finally:
        probe.close()


async def _restart_engine_after_cancel() -> str:
    """Mata el proceso del motor y pide su rearranque con ensure_local
    (el script ya sabe no duplicar y respetar HOLD de SALIR). Devuelve la
    nota honesta para el job: recargar el modelo tarda minutos."""
    try:
        port = urllib.parse.urlsplit(settings.acestep.base_url).port or 8001
    except ValueError:
        port = 8001
    pid = await asyncio.to_thread(_motor_pid_on_port, port)
    if pid is None:
        note = "El motor ya no estaba corriendo."
    else:
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError as exc:
            return f"No se pudo parar el motor (PID {pid}): {exc}"
        for _ in range(20):
            if await asyncio.to_thread(_port_is_free, port):
                break
            await asyncio.sleep(0.5)
        note = f"Motor parado (PID {pid})."
    script = PROJECT_ROOT / "scripts" / "ensure_local.ps1"
    try:
        subprocess.Popen(  # noqa: S603,S607 - script propio del proyecto, ruta fija
            ["powershell", "-ExecutionPolicy", "Bypass", "-File", str(script)],
            cwd=str(PROJECT_ROOT),
            stdout=open(PROJECT_ROOT / "logs" / "ensure-relaunch.log", "a", encoding="utf-8"),
            stderr=subprocess.STDOUT,
            creationflags=getattr(subprocess, "DETACHED_PROCESS", 0),
        )
        note += " Rearranque pedido: si no vuelve solo, reabre Musicia."
    except OSError as exc:
        note += f" No se pudo pedir el rearranque: {exc}"
    logger.info(f"Motor reiniciado tras cancelar: {note}")
    return note


@app.post("/music/jobs/{job_id}/cancel")
async def cancel_job(job_id: str) -> dict[str, Any]:
    """Para un trabajo en curso (spec/02 [Q2]): se suelta sin descargar nada.
    El motor no sabe cancelar: si estaba trabajando se mata su proceso y se
    relanza (recargar el modelo tarda minutos); si no, solo se marca."""
    for store_name, store in (("music", jobs), ("remix", remix_jobs), ("separate", separate_jobs)):
        if job_id in store:
            job = store[job_id]
            break
    else:
        raise HTTPException(status_code=404, detail="Ese trabajo no existe")
    if job.get("status") not in _GPU_ACTIVE:
        raise HTTPException(status_code=409, detail="El trabajo ya terminó")
    job["cancelled"] = True
    note = ""
    if _job_uses_motor(job, store_name):
        note = await _restart_engine_after_cancel()
    error = CANCELLED_MESSAGE + (f" {note}" if note else "")
    job.update(status="failed", phase="Cancelado", error=error, completed_at=_now())
    _save_history()
    logger.info(f"Trabajo {job_id[:8]} cancelado ({store_name}){': ' + note if note else ''}")
    return {"status": "cancelled", "job_id": job_id, "note": note or CANCELLED_MESSAGE}


@app.get("/music/audio/{name}")
async def music_audio(name: str) -> FileResponse:
    path = _resolve_output(name)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Audio no generado todavía")
    # MIME por extensión (hoy todo es mp3; si un día hay wav no mentirá).
    media_type, _ = mimetypes.guess_type(path.name)
    return FileResponse(path, media_type=media_type or "audio/mpeg", filename=path.name)


@app.get("/music/library")
async def music_library() -> dict[str, Any]:
    """Lista los MP3 reales del directorio de salidas (biblioteca local)."""
    outputs = settings.outputs_dir
    items = []
    for path in sorted(outputs.glob("*.mp3"), key=lambda p: p.stat().st_mtime, reverse=True):
        stat = path.stat()
        ficha = _read_ficha(path)
        items.append(
            {
                "name": path.name,
                "size_bytes": stat.st_size,
                "modified": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
                "bpm": None if ficha is None else ficha.get("bpm"),
                "key_scale": None if ficha is None else ficha.get("key_scale"),
                "lyrics": None if ficha is None else ficha.get("lyrics"),
                "model": None if ficha is None else ficha.get("model"),
                "task_type": None if ficha is None else ficha.get("task_type"),
                "prompt": None if ficha is None else ficha.get("prompt"),
            }
        )
    return {"outputs_dir": str(outputs), "items": items}


# ---------------------------------------------------------------------------
# Subida y remix de audio del usuario
# ---------------------------------------------------------------------------

UPLOADS_SUBDIR = "uploads"
ALLOWED_UPLOAD_SUFFIXES = {".mp3", ".wav"}
MAX_UPLOAD_BYTES = 50 * 1024 * 1024  # 50 MB


def _uploads_dir() -> Path:
    d = settings.outputs_dir / UPLOADS_SUBDIR
    d.mkdir(parents=True, exist_ok=True)
    return d


def _resolve_upload(name: str) -> Path:
    candidate = (_uploads_dir() / Path(name).name).resolve()
    uploads = _uploads_dir().resolve()
    # Comparación insensible a mayúsculas (Windows) y robusta a unresolved paths
    if not str(candidate).lower().startswith(str(uploads).lower() + os.sep):
        raise HTTPException(status_code=400, detail="Nombre de fichero no válido")
    return candidate


@app.post("/audio/upload")
async def audio_upload(file: UploadFile) -> dict[str, Any]:
    """Guarda un MP3/WAV real en outputs/uploads/ y lo analiza (DSP puro).

    Devuelve features + hipótesis (música/voz/mixta) para que la UI
    pregunte al usuario qué quiere hacer. Nunca se asume nada.
    """
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_UPLOAD_SUFFIXES:
        raise HTTPException(status_code=400, detail="Solo se aceptan ficheros .mp3 y .wav")

    data = await file.read()
    if len(data) == 0:
        raise HTTPException(status_code=400, detail="Fichero vacío")
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="El fichero supera los 50 MB")

    stem = Path(file.filename).stem
    safe = _safe_name(stem, "upload", suffix=suffix)
    target = _uploads_dir() / f"{uuid.uuid4().hex[:8]}-{safe}"
    target.write_bytes(data)

    try:
        analysis = analyze_audio(target)
    except (ValueError, FileNotFoundError) as exc:
        target.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 - fichero corrupto/no decodificable
        target.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=f"Audio no decodificable: {exc}") from exc

    logger.info(f"Subida analizada: {target.name} ({analysis['duration_seconds']}s)")
    return {"status": "success", "file_name": target.name, "analysis": analysis}


@app.get("/audio/uploads")
async def list_uploads() -> dict[str, Any]:
    """Lista los audios subidos (MP3 y WAV)."""
    items = []
    for path in sorted(_uploads_dir().iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if path.suffix.lower() in ALLOWED_UPLOAD_SUFFIXES:
            stat = path.stat()
            items.append(
                {
                    "name": path.name,
                    "size_bytes": stat.st_size,
                    "modified": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
                }
            )
    return {"dir": str(_uploads_dir()), "items": items}


@app.get("/audio/uploads/file/{name}")
async def upload_file(name: str) -> FileResponse:
    """Sirve un audio subido para reproducirlo/descargarlo."""
    path = _resolve_upload(name)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Audio no encontrado")
    media = "audio/wav" if path.suffix.lower() == ".wav" else "audio/mpeg"
    return FileResponse(path, media_type=media, filename=path.name)


@app.delete("/audio/uploads/{name}")
async def delete_upload(name: str) -> dict[str, Any]:
    path = _resolve_upload(name)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Audio no encontrado")
    path.unlink()
    _drop_ficha(path)
    logger.info(f"Subida borrada: {path.name}")
    return {"status": "deleted", "name": path.name}


@app.get("/music/style_options")
async def music_style_options(prompt: str = "") -> dict[str, Any]:
    """Chips y capas detectadas de un prompt (datos de prompt_style, sin LM).

    La UI pinta lo que este catálogo dice: chips sugeridos según el género
    detectado y marca activos los detalles ya escritos. Determinista y
    barato: se puede pedir en cada pulsación.
    """
    return analyze_prompt(prompt)


@app.get("/music/genre_glossary")
def music_genre_glossary(q: str = "", limit: int = 50) -> dict[str, Any]:
    """Glosario real de estilos: catálogo de Musicia + vocabulario del motor.

    `genres_vocab.txt` es la whitelist con la que el motor restringe el campo
    genres: lo que no está ahí, el modelo no puede escribirlo. Es el glosario
    de estilos y subestilos tal y como los entiende él, no una lista propia.
    """
    return glossary_search(q, limit=limit)


@app.get("/music/genre_glossary/combine")
def music_genre_glossary_combine(a: str = "", b: str = "", limit: int = 50) -> dict[str, Any]:
    """Combinaciones de dos estilos que existen en el vocabulario del modelo.

    Ejemplo real: techno + hardcore devuelve «hardcore techno». Si la mezcla
    no está en el archivo, la lista sale vacía (nunca se inventa una forma).
    """
    return glossary_combine(a, b, limit=limit)


@app.post("/music/enhance_prompt")
async def music_enhance_prompt(request: EnhancePromptRequest) -> dict[str, Any]:
    """Enriquece un prompt con reglas de producción musical (determinista)."""
    try:
        return enhance_prompt(request.prompt, bpm=request.bpm)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/audio/remix_prompt")
async def audio_remix_prompt(request: RemixPromptRequest) -> dict[str, Any]:
    """Sugiere un prompt para remixar/re-crear un audio, desde su análisis DSP real.

    Re-analiza el fichero (análisis puro, rápido) y compone un prompt base
    según el tipo confirmado por el usuario; lo enriquece con las reglas de
    producción. Devuelve el prompt y en qué se basa (transparencia).
    """
    source = _find_audio(request.file_name, request.source_kind)

    try:
        a = analyze_audio(source)
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    kind = request.kind if request.kind in {"musica", "voz", "mixta", "otro"} else "musica"
    bases = {
        "musica": "pieza musical inspirada en una referencia con carácter similar",
        "voz": "base musical suave para acompañar una voz protagonista",
        "mixta": "versión renovada de un tema con música y voz, mismo espíritu",
        "otro": "textura sonora evocadora basada en una referencia ambiental",
    }
    parts = [bases[kind]]
    if a.get("bpm"):
        parts.append(f"{a['bpm']} bpm")
    parts.append("graves marcados" if a.get("bass_ratio", 0) >= 0.55 else "mezcla equilibrada y brillante")
    parts.append("textura continua y fluida" if a.get("dynamics_std_db", 0) < 9 else "dinámica expresiva")
    if a.get("silence_ratio", 0) >= 0.15:
        parts.append("con respiraciones y pausas")

    try:
        enhanced = enhance_prompt(", ".join(parts), bpm=a.get("bpm"))
        prompt = enhanced["enhanced"]
        additions = enhanced["additions"]
    except ValueError:
        prompt = ", ".join(parts)
        additions = []

    return {
        "prompt": prompt,
        "additions": additions,
        "basis": {
            "bpm": a.get("bpm"),
            "bass_ratio": a.get("bass_ratio"),
            "dynamics_std_db": a.get("dynamics_std_db"),
            "duration_seconds": a.get("duration_seconds"),
            "kind": kind,
        },
    }


@app.get("/audio/peaks/{name}")
async def audio_peaks(
    name: str, buckets: int = 400, source_kind: str | None = None
) -> dict[str, Any]:
    """Picós de amplitud para pintar la forma de onda en el editor visual.

    Devuelve `buckets` valores 0..1 (máx por intervalo), Python puro.
    `source_kind` (upload | output) desambigua homónimos igual que el resto:
    esa lista manda y la otra solo es reserva.
    """
    if not 50 <= buckets <= 2000:
        raise HTTPException(status_code=400, detail="buckets debe estar entre 50 y 2000")

    from audio_analysis import ANALYSIS_RATE
    from pydub import AudioSegment
    import math

    source = _find_audio(name, source_kind)

    try:
        audio = (
            AudioSegment.from_file(source)
            .set_channels(1)
            .set_frame_rate(ANALYSIS_RATE)
            .set_sample_width(2)
        )
        samples = list(audio.get_array_of_samples())
        if not samples:
            raise ValueError("Audio sin muestras")
        size = max(1, len(samples) // buckets)
        peaks = []
        for i in range(buckets):
            chunk = samples[i * size:(i + 1) * size]
            if chunk:
                peaks.append(min(1.0, max(abs(min(chunk)), abs(max(chunk))) / 32768.0))
            else:
                peaks.append(0.0)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.error(f"Picós falló: {exc}")
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {
        "name": source.name,
        "duration_seconds": round(len(audio) / 1000.0, 2),
        "buckets": len(peaks),
        "peaks": [round(p, 4) for p in peaks],
    }


@app.post("/audio/remix")
async def audio_remix(request: RemixRequest) -> dict[str, Any]:
    """Remix DSP real: tempo (speed), pitch (resample), reverse, gain, fades, recorte.

    Acepta audio de outputs/ (biblioteca) o de uploads/ (subidas), como mix y peaks.
    """
    # Busca en la lista que dice la UI (source_kind); sin ella, outputs primero.
    source = _find_audio(request.file_name, request.source_kind)

    if not 0.5 <= request.tempo <= 2.0:
        raise HTTPException(status_code=400, detail="tempo debe estar entre 0.5 y 2.0")
    if not -12 <= request.pitch_semitones <= 12:
        raise HTTPException(status_code=400, detail="pitch_semitones debe estar entre -12 y +12")
    if not PROC_MIN_GAIN_DB <= request.gain_db <= PROC_MAX_GAIN_DB:
        raise HTTPException(status_code=400, detail="gain_db fuera de rango (-24 a +24)")
    if not 0 <= request.fade_in_ms <= PROC_MAX_FADE_MS:
        raise HTTPException(status_code=400, detail="fade_in_ms fuera de rango (0-10000)")
    if not 0 <= request.fade_out_ms <= PROC_MAX_FADE_MS:
        raise HTTPException(status_code=400, detail="fade_out_ms fuera de rango (0-10000)")

    output_name = request.output_name
    stem = _safe_name(output_name, DEFAULT_STEM) if output_name else _derive_stem(request.file_name, "remix")
    output_path = _unique_output_path(stem, ".mp3")

    try:
        from pydub import AudioSegment

        audio = AudioSegment.from_file(source)

        start_ms = max(0, int(request.trim_start_s * 1000))
        end_ms = len(audio) if request.trim_end_s is None else int(request.trim_end_s * 1000)
        if start_ms >= len(audio) or end_ms <= start_ms:
            raise ValueError("Recorte vacío: revisa inicio y fin")
        audio = audio[max(0, start_ms):min(end_ms, len(audio))]

        if request.reverse:
            audio = audio.reverse()
        if request.pitch_semitones != 0:
            # Pitch por resample (efecto de velocidad de cinta; clásico en remix)
            new_rate = int(audio.frame_rate * (2.0 ** (request.pitch_semitones / 12.0)))
            audio = audio._spawn(
                audio.raw_data,
                overrides={"frame_rate": new_rate},
            ).set_frame_rate(44100)
        if request.tempo != 1.0:
            # Tempo = cambiar velocidad de reproducción (compone con el pitch aquí)
            new_rate = int(audio.frame_rate * request.tempo)
            audio = audio._spawn(
                audio.raw_data,
                overrides={"frame_rate": new_rate},
            ).set_frame_rate(44100)
        if request.fade_in_ms > 0:
            audio = audio.fade_in(int(request.fade_in_ms))
        if request.fade_out_ms > 0:
            audio = audio.fade_out(int(request.fade_out_ms))
        if request.gain_db != 0.0:
            audio = audio + request.gain_db

        output_path.parent.mkdir(parents=True, exist_ok=True)
        audio.export(output_path, format="mp3")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        logger.error(f"Remix falló: {exc}")
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    _carry_ficha(source, output_path, "remix")
    logger.info(f"Remix OK: {output_path.name} ({len(audio) / 1000:.1f}s)")
    return {
        "status": "success",
        "file_name": output_path.name,
        "duration_seconds": round(len(audio) / 1000.0, 2),
    }


@app.delete("/music/audio/{name}")
async def delete_audio(name: str) -> dict[str, Any]:
    """Borra un MP3 real del directorio de salidas."""
    path = _resolve_output(name)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Audio no encontrado")
    path.unlink()
    _drop_ficha(path)
    logger.info(f"Audio borrado: {path.name}")
    return {"status": "deleted", "name": path.name}


@app.post("/music/audio/delete_many")
async def delete_many_audio(request: DeleteManyRequest) -> dict[str, Any]:
    """Borra un bloque de MP3 de la biblioteca en una sola petición (spec/02 [L2]).

    Cada nombre se resuelve y borra igual que el borrado individual (con su
    ficha). Lo inexistente se reporta en `not_found` sin tumbar el resto.
    """
    deleted: list[str] = []
    not_found: list[str] = []
    for name in request.names:
        try:
            path = _resolve_output(name)
        except HTTPException:
            not_found.append(name)
            continue
        if not path.exists():
            not_found.append(name)
            continue
        path.unlink()
        _drop_ficha(path)
        deleted.append(path.name)
    logger.info(f"Bloque borrado: {len(deleted)} ok, {len(not_found)} no encontrados")
    return {"status": "deleted", "deleted": deleted, "not_found": not_found}


@app.post("/audio/process")
async def audio_process(request: AudioProcessRequest) -> dict[str, Any]:
    """Post-proceso real (gain/fade/recorte) de un audio de outputs/ con pydub."""
    source = _resolve_output(request.file_name)
    if not source.exists():
        raise HTTPException(status_code=404, detail="Audio de origen no encontrado")

    stem = _safe_name(request.output_name, DEFAULT_STEM) if request.output_name else _derive_stem(request.file_name, "edit")
    output_path = _unique_output_path(stem, ".mp3")

    if not PROC_MIN_GAIN_DB <= request.gain_db <= PROC_MAX_GAIN_DB:
        raise HTTPException(status_code=400, detail="gain_db fuera de rango (-24 a +24)")
    if not 0 <= request.fade_in_ms <= PROC_MAX_FADE_MS:
        raise HTTPException(status_code=400, detail="fade_in_ms fuera de rango (0-10000)")
    if not 0 <= request.fade_out_ms <= PROC_MAX_FADE_MS:
        raise HTTPException(status_code=400, detail="fade_out_ms fuera de rango (0-10000)")

    try:
        duration_ms = process_audio(
            source=source,
            output=output_path,
            gain_db=request.gain_db,
            fade_in_ms=request.fade_in_ms,
            fade_out_ms=request.fade_out_ms,
            trim_start_s=request.trim_start_s,
            trim_end_s=request.trim_end_s,
        )
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        logger.error(f"Post-proceso falló: {exc}")
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    _carry_ficha(source, output_path, "edit")
    logger.info(f"Post-proceso OK: {output_path.name} ({duration_ms / 1000:.1f}s)")
    return {
        "status": "success",
        "file_name": output_path.name,
        "duration_seconds": round(duration_ms / 1000.0, 2),
    }


@app.post("/music/write_lyrics")
async def music_write_lyrics(request: WriteLyricsRequest) -> dict[str, Any]:
    """Letra automática desde el LM local del motor (híbrido: el usuario edita).

    Delega en `/format_input` del motor solo si el campo está vacío. Con
    frases del usuario no se llama: el LM las sustituye por otro texto y,
    mientras genera, `/health` deja de contestar y la pastilla pasa a APAGADO.
    """
    escritas = request.lyrics.strip()
    if escritas:
        logger.info("write_lyrics: frases del usuario, sin LM")
        return {
            "lyrics": escritas,
            "source": "tus_frases",
            "caption": request.prompt,
            "bpm": None,
            "key_scale": None,
            "time_signature": None,
            "vocal_language": request.language,
            "warning": (
                "He construido la canción con tus frases "
                "(verso, estribillo y puente)."
            ),
        }

    health = await music.health()
    if not health.get("reachable"):
        raise HTTPException(
            status_code=503,
            detail=(
                "El motor de música no está activo. Abre Musicia.exe y vuelve a intentarlo."
            ),
        )
    try:
        result = await music.write_lyrics(
            caption=request.prompt,
            lyrics=request.lyrics,
            language=request.language,
            duration_seconds=request.duration_seconds,
            bpm=request.bpm,
            key_scale=request.key_scale,
        )
    except Exception as exc:  # noqa: BLE001
        # El LM puede no estar listo (arranque en frío). Si el usuario escribió
        # frases, nunca fallamos: se construye la canción con ellas.
        logger.warning(f"write_lyrics: motor no disponible ({exc})")
        if request.lyrics.strip():
            return {
                "lyrics": request.lyrics.strip(),
                "source": "tus_frases",
                "caption": request.prompt,
                "bpm": None,
                "key_scale": None,
                "time_signature": None,
                "vocal_language": request.language,
                "warning": (
                    "El motor de letras todavía no estaba listo; he construido la "
                    "canción con tus frases. Pulsa GENERAR cuando quieras."
                ),
            }
        raise HTTPException(
            status_code=503,
            detail=(
                "El motor de letras no está listo todavía (arrancando). "
                "Escribe dos frases y pulsa otra vez ESCRIBIRLA POR MÍ."
            ),
        ) from exc

    lyrics_text = str(result.get("lyrics") or "")
    if not lyrics_text.strip():
        raise HTTPException(
            status_code=502,
            detail="El motor no devolvió letra. Escribe la tuya: el campo está editable.",
        )

    # El LM local (0.6B) a menudo devuelve solo estructura instrumental o
    # degenera en texto repetido. No lo disimulamos: si el usuario ya escribió
    # algo, se devuelve SU texto (la app lo estructura); si no, se avisa.
    outside_brackets = re.sub(r"\[[^\]]*\]", " ", lyrics_text)
    words = re.findall(r"[^\W\d_]{2,}", outside_brackets, flags=re.UNICODE)
    instrumental_only = "instrumental" in lyrics_text.lower() and len(words) < 12

    # ¿Ha aportado algo nuevo sobre lo que escribió el usuario?
    user_words = {
        w.lower() for w in re.findall(r"[^\W\d_]{3,}", request.lyrics, flags=re.UNICODE)
    }
    new_words = {w.lower() for w in words} - user_words

    # ¿Es texto degenerado (una línea repetida en bucle)?
    lines = [l.strip() for l in lyrics_text.splitlines() if l.strip()]
    repetition = 0.0
    if lines:
        counts: dict[str, int] = {}
        for line in lines:
            counts[line] = counts.get(line, 0) + 1
        repetition = max(counts.values()) / len(lines)
    degenerate = repetition >= 0.4 and len(lines) >= 4

    useless = instrumental_only or degenerate or (request.lyrics.strip() and len(new_words) < 8)
    warning = None
    source = "modelo"
    if useless:
        if request.lyrics.strip():
            # El usuario puso sus frases: se usan esas, no se le devuelve nada.
            lyrics_text = request.lyrics.strip()
            source = "tus_frases"
            warning = (
                "El motor no ha ampliado tu letra; he construido la canción "
                "con tus frases (verso, estribillo y puente)."
            )
        else:
            warning = (
                "El LM local no ha compuesto letra. Escribe dos frases y pulsa "
                "otra vez ESCRIBIRLA POR MÍ: la canción se construye con ellas."
            )

    bpm = result.get("bpm")
    if not isinstance(bpm, (int, float)) or not 40 <= bpm <= 220:
        bpm = None  # el LM a veces propone 300 bpm: se descarta

    return {
        "lyrics": lyrics_text,
        "source": source,
        "caption": result.get("caption"),
        "bpm": bpm,
        "key_scale": result.get("key_scale"),
        "time_signature": result.get("time_signature"),
        "vocal_language": result.get("vocal_language") or request.language,
        "warning": warning,
    }


@app.patch("/music/audio/{name}")
async def rename_audio(name: str, request: RenameRequest) -> dict[str, Any]:
    """Renombra un audio de outputs/ o uploads/ (spec E1), sin pisar otros.

    El nombre se sanea con `_safe_name` y si ya existe se numera: nombre,
    (2), (3)… Renombrar en línea no rompe referencias porque las URLs viajan
    siempre por nombre, nunca por ruta.
    """
    source = _find_audio(name, request.source_kind)
    stem = _safe_name(request.new_name, DEFAULT_STEM)
    # Desambigua dentro del MISMO directorio donde vive el fichero.
    suffix = source.suffix or ".mp3"
    target = source.with_name(f"{stem}{suffix}")
    index = 2
    while target.exists() and target != source:
        target = source.with_name(f"{stem} ({index}){suffix}")
        index += 1
        if index > 500:
            raise HTTPException(status_code=409, detail="Demasiadas versiones con ese nombre")
    if target == source:
        return {"status": "unchanged", "name": source.name}
    source.rename(target)
    _move_ficha(source, target)
    logger.info(f"Audio renombrado: {source.name} -> {target.name}")
    return {"status": "renamed", "name": target.name, "renamed_from": source.name}


# ---------------------------------------------------------------------------
# UI de escritorio: la API sirve el build del frontend para Electron.
# El monta se hace al final para no tapar las rutas de la API.
# ---------------------------------------------------------------------------

_DIST = PROJECT_ROOT / "frontend" / "dist"
if _DIST.is_dir():
    app.mount("/", StaticFiles(directory=str(_DIST), html=True), name="ui")
    logger.info(f"UI de escritorio servida desde {_DIST}")
else:
    logger.warning(f"Sin UI: falta el build del frontend en {_DIST} (npm run build)")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=settings.host, port=settings.port)