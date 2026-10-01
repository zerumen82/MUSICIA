"""API de Musicia: voz, mezcla y generación de música con IA en local.

Endpoints
---------
GET  /                      información del servicio
GET  /health                estado real del motor local ACE-Step
POST /tts/generate          texto -> voz (edge-tts)
GET  /voices                voces disponibles del motor de TTS
POST /audio/mix             mezcla de dos pistas con ganancia en dB
POST /music/generate        crea una generación real en el motor local
GET  /music/status/{job_id} estado y resultado de una generación
GET  /music/audio/{name}    descarga el audio generado

Nada aquí es simulado: cada endpoint hace el trabajo real y devuelve error si falla.
"""

from __future__ import annotations

import asyncio
import os
import re
import time
import uuid
from contextlib import asynccontextmanager
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncIterator

from fastapi import BackgroundTasks, FastAPI, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger
from pydantic import BaseModel, Field

from config import PROJECT_ROOT, get_settings
from audio_analysis import analyze_audio
from audio_service import (
    MAX_GAIN_DB as PROC_MAX_GAIN_DB,
    MAX_FADE_MS as PROC_MAX_FADE_MS,
    MIN_GAIN_DB as PROC_MIN_GAIN_DB,
    process_audio,
)
from mixer_service import MixerService
from prompt_enhancer import enhance_prompt
from music_service import GenerationRequest, MusicEngineError, MusicService
from tts_service import TTSService

settings = get_settings()
music = MusicService(settings)

# Seguimiento de generaciones en curso. El motor es quien decide el estado real;
# aquí solo guardamos la salida descargada y los datos de la tarea.
jobs: dict[str, dict[str, Any]] = {}


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
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


class TTSRequest(BaseModel):
    text: str
    voice: str | None = None
    output_name: str | None = None


class MixRequest(BaseModel):
    base_track: str
    vocal_track: str
    output_name: str | None = None
    base_volume: float = 0
    vocal_volume: float = 0


class MusicGenRequest(BaseModel):
    prompt: str = Field(min_length=1, description="Descripción del estilo musical")
    lyrics: str | None = Field(default=None, description="Letra; obligatoria si no es instrumental")
    instrumental: bool | None = None
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
    mood: str | None = None


class RemixPromptRequest(BaseModel):
    """Petición de prompt sugerido para remixar/re-crear un audio subido."""

    file_name: str
    kind: str = "musica"   # musica | voz | mixta | otro


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------


def _safe_name(raw: str | None, fallback: str, suffix: str = "") -> str:
    """Nombre de fichero seguro (sin rutas ni caracteresProblemáticos)."""
    stem = Path(raw).name if raw else ""
    stem = re.sub(r"[^\w.-]+", "-", stem).strip("-.") or fallback
    stem = stem[: settings.generation.max_slug_chars]
    if suffix and not stem.lower().endswith(suffix):
        stem = f"{stem}{suffix}"
    return stem


def _resolve_output(output_name: str) -> Path:
    """Resuelve un nombre dentro del directorio de salidas, bloqueando escapes."""
    candidate = (settings.outputs_dir / Path(output_name).name).resolve()
    if settings.outputs_dir not in candidate.parents:
        raise HTTPException(status_code=400, detail="Nombre de fichero no válido")
    return candidate


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


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
    started = time.monotonic()
    job["events"] = []

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
        if not final.succeeded:
            raise MusicEngineError(final.error or "El motor terminó la tarea con error")

        log_event("Audio generado por el motor; descargando…")
        job["phase"] = "Descargando el audio desde el motor"

        track = next((item for item in final.tracks if item.file), None)
        if track is None:
            raise MusicEngineError("El motor no devolvió ningún archivo de audio")

        output_path = _resolve_output(job["output_name"])
        await music.download(track.file, output_path)
        log_event("Audio descargado; verificando duración…")
        job["phase"] = "Verificando el audio generado"
        duration_ms = await music.verify_audio(output_path)

        job.update(
            status="succeeded",
            phase="Lista",
            duration_seconds=round(duration_ms / 1000, 2),
            metas=track.metas,
            engine_caption=track.prompt,
            elapsed_seconds=round(time.monotonic() - started, 1),
            completed_at=_now(),
        )
        log_event(f"Completado: {output_path.name} ({duration_ms / 1000:.1f} s)")
        logger.info(f"Generación {job_id} lista: {output_path.name} ({duration_ms / 1000:.1f} s)")
    except Exception as exc:  # noqa: BLE001 - el error real se propaga al estado del job
        job.update(status="failed", error=str(exc), phase="Error", completed_at=_now())
        log_event(f"Fallo: {exc}")
        logger.error(f"Generación {job_id} falló: {exc}")


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


@app.post("/tts/generate")
async def generate_tts(request: TTSRequest) -> dict[str, Any]:
    voice = request.voice or settings.tts.default_voice
    output_path = _resolve_output(
        _safe_name(request.output_name, settings.tts.default_output_name)
    )
    if len(request.text) > settings.tts.max_text_chars:
        raise HTTPException(
            status_code=400,
            detail=f"El texto supera los {settings.tts.max_text_chars} caracteres",
        )
    try:
        await TTSService.generate_speech(request.text, voice, str(output_path))
    except Exception as exc:
        logger.error(f"TTS falló: {exc}")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"status": "success", "file_path": str(output_path), "voice": voice}


@app.get("/voices")
async def get_voices() -> Any:
    try:
        return await TTSService.list_voices()
    except Exception as exc:
        logger.error(f"No se pudieron listar las voces: {exc}")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/audio/mix")
async def mix_audio(request: MixRequest) -> dict[str, Any]:
    output_path = _resolve_output(
        _safe_name(request.output_name, settings.mixer.default_output_name)
    )
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
    # Las pistas llegan por nombre; se resuelven contra outputs/ o uploads/.
    def _resolve_track(name: str) -> str:
        candidate = _resolve_output(name)
        if candidate.exists():
            return str(candidate)
        upload = _resolve_upload(name)
        if upload.exists():
            return str(upload)
        raise HTTPException(status_code=404, detail=f"Pista no encontrada: {name}")

    try:
        MixerService.mix_tracks(
            _resolve_track(request.base_track),
            _resolve_track(request.vocal_track),
            str(output_path),
            request.base_volume,
            request.vocal_volume,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Mezcla falló: {exc}")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"status": "success", "file_path": str(output_path)}


@app.get("/music/config")
async def music_config() -> dict[str, Any]:
    """Valores por defecto y límites del motor, para que el frontend no los invente."""
    return asdict(settings.generation)


@app.post("/music/generate")
async def generate_music(
    request: MusicGenRequest, background_tasks: BackgroundTasks
) -> dict[str, Any]:
    """Envía la generación al motor local y sigue el resultado en segundo plano."""
    job_id = uuid.uuid4().hex
    audio_format = request.audio_format or settings.generation.audio_format
    output_name = _safe_name(
        f"{job_id}-{request.prompt}", job_id, suffix=f".{audio_format}"
    )

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
        task_id, initial_status = await music.submit(
            GenerationRequest(
                prompt=request.prompt,
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
                model=request.model,
            )
        )
    except MusicEngineError as exc:
        logger.error(f"No se pudo enviar la generación al motor: {exc}")
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    jobs[job_id] = {
        "job_id": job_id,
        "engine_task_id": task_id,
        "status": initial_status,
        "engine_status": 0,
        "prompt": request.prompt,
        "instrumental": (
            settings.generation.instrumental if request.instrumental is None else request.instrumental
        ),
        "output_name": output_name,
        "created_at": _now(),
        "progress": "",
        "progress_ratio": 0.0,
        "stage": "queued",
        "phase": "Enviada al motor local",
        "elapsed_seconds": 0.0,
        "events": [],
        "duration_seconds": None,
        "error": None,
    }
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
    items = sorted(
        jobs.values(),
        key=lambda j: (order.get(j["status"], 4), j.get("created_at", "")),
    )
    return {"items": [_job_view(j) for j in items]}


@app.get("/music/audio/{name}")
async def music_audio(name: str) -> FileResponse:
    path = _resolve_output(name)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Audio no generado todavía")
    return FileResponse(path, media_type="audio/mpeg", filename=path.name)


@app.get("/music/library")
async def music_library() -> dict[str, Any]:
    """Lista los MP3 reales del directorio de salidas (biblioteca local)."""
    outputs = settings.outputs_dir
    items = []
    for path in sorted(outputs.glob("*.mp3"), key=lambda p: p.stat().st_mtime, reverse=True):
        stat = path.stat()
        items.append(
            {
                "name": path.name,
                "size_bytes": stat.st_size,
                "modified": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
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
    logger.info(f"Subida borrada: {path.name}")
    return {"status": "deleted", "name": path.name}


@app.post("/music/enhance_prompt")
async def music_enhance_prompt(request: EnhancePromptRequest) -> dict[str, Any]:
    """Enriquece un prompt con reglas de producción musical (determinista)."""
    try:
        return enhance_prompt(request.prompt, bpm=request.bpm, mood=request.mood)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/audio/remix_prompt")
async def audio_remix_prompt(request: RemixPromptRequest) -> dict[str, Any]:
    """Sugiere un prompt para remixar/re-crear un audio, desde su análisis DSP real.

    Re-analiza el fichero (análisis puro, rápido) y compone un prompt base
    según el tipo confirmado por el usuario; lo enriquece con las reglas de
    producción. Devuelve el prompt y en qué se basa (transparencia).
    """
    try:
        source = _resolve_upload(request.file_name)
    except HTTPException:
        source = _resolve_output(request.file_name)
    if not source.exists():
        raise HTTPException(status_code=404, detail="Audio no encontrado")

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
async def audio_peaks(name: str, buckets: int = 400) -> dict[str, Any]:
    """Picós de amplitud para pintar la forma de onda en el editor visual.

    Devuelve `buckets` valores 0..1 (máx por intervalo), Python puro.
    """
    if not 50 <= buckets <= 2000:
        raise HTTPException(status_code=400, detail="buckets debe estar entre 50 y 2000")

    from audio_analysis import ANALYSIS_RATE
    from pydub import AudioSegment
    import math

    source = _resolve_output(name)
    if not source.exists():
        # ¿es una subida?
        try:
            source = _resolve_upload(name)
        except HTTPException:
            raise HTTPException(status_code=404, detail="Audio no encontrado")
        if not source.exists():
            raise HTTPException(status_code=404, detail="Audio no encontrado")

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
    # Busca en outputs/ y en uploads/; usa el que exista realmente.
    source = None
    for resolver in (_resolve_output, _resolve_upload):
        try:
            candidate = resolver(request.file_name)
        except HTTPException:
            continue
        if candidate.exists():
            source = candidate
            break
    if source is None:
        raise HTTPException(status_code=404, detail="Audio no encontrado")

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

    output_name = request.output_name or f"{Path(request.file_name).stem}-remix.mp3"
    output_path = _resolve_output(_safe_name(output_name, "remix", suffix=".mp3"))

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
    logger.info(f"Audio borrado: {path.name}")
    return {"status": "deleted", "name": path.name}


@app.post("/audio/process")
async def audio_process(request: AudioProcessRequest) -> dict[str, Any]:
    """Post-proceso real (gain/fade/recorte) de un audio de outputs/ con pydub."""
    source = _resolve_output(request.file_name)
    if not source.exists():
        raise HTTPException(status_code=404, detail="Audio de origen no encontrado")

    output_name = request.output_name or f"{Path(request.file_name).stem}-edit.mp3"
    output_path = _resolve_output(_safe_name(output_name, "edit", suffix=".mp3"))

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

    logger.info(f"Post-proceso OK: {output_path.name} ({duration_ms / 1000:.1f}s)")
    return {
        "status": "success",
        "file_name": output_path.name,
        "duration_seconds": round(duration_ms / 1000.0, 2),
    }


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