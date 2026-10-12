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

from mixer_service import MixerService
from music_service import GenerationRequest, MusicEngineError
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
    """Identifica las muestras de origen, no solo un nombre reutilizable."""
    with source.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


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
        if request.bpm is not None and any(action == "keep" for action in request.groups.values()):
            raise ValueError("Para conservar grabaciones sin desalinearlas, mantén el tempo del original")
        if request.lyrics and request.groups.get("vocals") != "transform":
            raise ValueError("Una letra nueva requiere transformar el grupo de voz")
        if request.instrumental is True and request.groups.get("vocals") == "keep":
            raise ValueError("Conservar la voz y eliminarla mediante instrumental son instrucciones incompatibles")
    elif request.groups is not None or request.gains_db:
        raise ValueError("Los grupos y sus volúmenes solo se aplican al ámbito Por pistas")


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
            },
            "intermediate_format": remix.intermediate_format,
            "limitations": {
                "other": "Puede contener guitarra, piano, sintetizadores, pads y efectos juntos.",
                "transformed_groups": "La separación es estimada; escucha la mezcla para valorar fugas y alineación.",
                "voice": "Cover aproxima o resintetiza la voz; conservar reutiliza su grabación separada.",
                "classification": "La clasificación de la fuente no cambia el prompt ni el plan elegido.",
            },
        }

    def _new_job(self, source: Path, prompt: str) -> dict:
        return {"job_id": uuid.uuid4().hex, "status": "queued", "phase": "En cola",
                "source": source.name, "prompt": prompt, "error": None, "events": [],
                "started": time.monotonic(), "created_at": self.now()}

    async def create(self, request: RemixProjectRequest, background_tasks: BackgroundTasks) -> dict:
        from source_understanding import completed_analysis_for

        source = self.find_audio(request.source_name, request.source_kind)
        reference = self.find_audio(request.reference_name, request.reference_kind) if request.reference_name else None
        duration = await asyncio.to_thread(lambda: len(AudioSegment.from_file(source)) / 1000)
        try:
            validate_project(request, duration, self.settings)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        # Se comprueba tras el único await de admisión, antes de registrar el job.
        if reason := self.busy():
            raise HTTPException(status_code=409, detail=reason)
        job = self._new_job(source, request.prompt)
        job["project"] = request.model_dump()
        job["source_analysis"] = completed_analysis_for(source)
        job["duration_seconds"] = duration
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
        try:
            async with COMPUTE_LOCK:
                self.cancelled(job)
                job["status"] = "running"
                self.event(job, "Separando los cuatro grupos del original")
                result = await self._groups(source, job, self.settings.outputs_dir,
                                            f"grupos-{job['job_id'][:12]}")
                self.cancelled(job)
                job.update(status="succeeded", phase="Grupos listos", result=result,
                           source_digest=await asyncio.to_thread(source_digest, source),
                           completed_at=self.now(), elapsed_seconds=time.monotonic() - job["started"])
        except Exception as exc:
            self._fail(job, exc)
        finally:
            self.save()

    async def _groups(self, source, job, out_dir, stem):
        return await asyncio.to_thread(
            SeparatorService.separate_groups, source, out_dir, stem,
            self.settings.remix, lambda: bool(job.get("cancelled")),
        )

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
        try:
            async with COMPUTE_LOCK:
                self.cancelled(job)
                job["status"] = "running"
                digest = await asyncio.to_thread(source_digest, source)
                job["source_digest"] = digest
                engine_source = source
                if request.scope == "groups":
                    self.event(job, "Separando los grupos del original")
                    cached = next((item.get("result") for item in reversed(list(self.separate_jobs.values()))
                                   if item.get("status") == "succeeded" and item.get("source_digest") == digest
                                   and isinstance(item.get("result"), dict)
                                   and all((self.settings.outputs_dir / group["file_name"]).is_file()
                                           for group in item["result"].get("groups", []))), None)
                    if cached and cached.get("groups"):
                        originals = {item["id"]: self.settings.outputs_dir / item["file_name"]
                                     for item in cached["groups"]}
                    else:
                        result = await self._groups(source, job, work, "original")
                        originals = {item["id"]: work / item["file_name"] for item in result["groups"]}
                    targets = [key for key, action in request.groups.items() if action == "transform"]
                    if targets:
                        engine_source = work / "material-a-transformar.wav"
                        await asyncio.to_thread(MixerService.mix_groups,
                                                [(originals[key], 0.0) for key in targets],
                                                engine_source, duration, config.sample_rate)
                    job["preserved_groups"] = [key for key, action in request.groups.items() if action == "keep"]
                self.cancelled(job)
                generated = []
                if request.scope != "groups" or targets:
                    task = "repaint" if request.scope == "region" else "cover"
                    self.event(job, f"Transformando el audio original con {task}")
                    generation = GenerationRequest(
                        prompt=request.prompt, lyrics=request.lyrics, instrumental=request.instrumental,
                        task_type=task, source_path=str(engine_source),
                        reference_path=str(reference) if reference else None,
                        duration_seconds=None, bpm=request.bpm, seed=request.seed,
                        model=self.settings.generation.remix_model,
                        audio_format=config.intermediate_format,
                        cover_strength=(self.settings.generation.remix_cover_strength
                                        if request.cover_strength is None else request.cover_strength),
                        cover_noise_strength=(config.cover_noise_strength if request.cover_noise_strength is None
                                              else request.cover_noise_strength),
                        repaint_start=request.region_start, repaint_end=request.region_end,
                        repaint_mode=request.repaint_mode or config.repaint_mode,
                        repaint_strength=config.repaint_strength if request.repaint_strength is None else request.repaint_strength,
                        repaint_wav_crossfade_sec=(config.repaint_wav_crossfade_sec if request.repaint_wav_crossfade_sec is None
                                                  else request.repaint_wav_crossfade_sec),
                        repaint_latent_crossfade_frames=(config.repaint_latent_crossfade_frames if request.repaint_latent_crossfade_frames is None
                                                        else request.repaint_latent_crossfade_frames),
                    )
                    job["effective_parameters"] = self.music.build_payload(generation)

                    def update(status):
                        self.cancelled(job)
                        job["status"] = "running"
                        job["engine_progress"] = status.progress
                        job["progress_ratio"] = status.progress
                        job["phase"] = status.progress_text or status.stage or "Transformando el original"

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
                        if abs(seconds - duration) > config.duration_tolerance_seconds:
                            raise MusicEngineError(f"El motor cambió la duración: {seconds:g}s frente a {duration:g}s; no se mezclan timelines distintas")
                        generated.append((path, track))
                    if len(generated) != self.settings.generation.batch_size:
                        raise MusicEngineError(f"El motor devolvió {len(generated)} variantes; se pidieron {self.settings.generation.batch_size}")
                else:
                    generated = [(None, None)]
                exported, metadata = [], []
                for index, (path, track) in enumerate(generated):
                    self.cancelled(job)
                    timeline = path
                    if request.scope == "groups":
                        transformed = {}
                        if path:
                            self.event(job, f"Separando grupos transformados de la variante {index + 1}")
                            result = await self._groups(path, job, work, f"transformada-{index + 1}")
                            transformed = {item["id"]: work / item["file_name"] for item in result["groups"]}
                        parts = [(originals[key] if action == "keep" else transformed[key], request.gains_db.get(key, 0.0))
                                 for key, action in request.groups.items() if action != "remove"]
                        timeline = work / f"mezcla-{index + 1}.wav"
                        self.event(job, f"Recombinando la variante {index + 1} sobre la timeline original")
                        await asyncio.to_thread(MixerService.mix_groups, parts, timeline, duration, config.sample_rate)
                    stem = self.safe_name(request.output_name or f"{source.stem}-remix", "remix")
                    output = self.unique_output(stem, ".mp3")
                    self.event(job, f"Exportando la variante {index + 1}")
                    mastering = await asyncio.to_thread(MixerService.export_remix, timeline, output, config)
                    self.cancelled(job)
                    await self.music.verify_audio(output)
                    measured = await asyncio.to_thread(self.measure_bpm, output)
                    variant = {"file_name": output.name, "intermediate_path": str(timeline),
                               "seed": track.metas.get("seed") if track else None,
                               "engine_metas": track.metas if track else {}, **mastering}
                    self.carry_ficha(source, output, "remix-project", prompt=request.prompt,
                                     project=request.model_dump(), effective_parameters=job.get("effective_parameters"),
                                     source_analysis=job.get("source_analysis"),
                                     source_digest=digest, mastering=mastering,
                                     seed=variant["seed"], **(measured or {}))
                    exported.append(output.name)
                    metadata.append(variant)
                self.cancelled(job)
                job.update(status="succeeded", phase="Listo", completed_at=self.now(),
                           elapsed_seconds=time.monotonic() - job["started"],
                           result={"mix": exported[0], "variants": exported, "metadata": metadata,
                                   "scope": request.scope, "groups": request.groups,
                                   "source": source.name, "source_kind": request.source_kind,
                                   "source_classification": request.source_classification,
                                   "classification_origin": request.classification_origin,
                                   "source_analysis": job.get("source_analysis"),
                                   "duration_seconds": duration,
                                   "preserved_groups": job.get("preserved_groups", [])})
        except Exception as exc:
            self._fail(job, exc)
        finally:
            self.save()
