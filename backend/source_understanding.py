"""Audio understanding by the installed local model; never a prompt rewriter.

Genre families are data, applied to the model's AUDIO-derived metadata.
No filename inference, fabricated probability, or generation of a new song.
"""
from __future__ import annotations

import asyncio
import json
import re
import tempfile
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Literal

from fastapi import BackgroundTasks, HTTPException
from loguru import logger
from pydantic import BaseModel
from pydub import AudioSegment


@dataclass
class SourceAnalysisSettings:
    sample_seconds: float = 30.0
    poll_interval: float = 3.0
    timeout_seconds: float = 1800.0
    max_history: int = 30
    catalog_path: str = str(Path(__file__).with_name("source_categories.json"))


class SourceAnalysisRequest(BaseModel):
    source_name: str
    source_kind: Literal["upload", "output"]


analysis_jobs: dict[str, dict[str, Any]] = {}
_cache: dict[tuple, str] = {}


def active_analysis() -> str | None:
    return next((job_id for job_id, job in analysis_jobs.items()
                 if job["status"] in {"queued", "running"}), None)


def completed_analysis_for(source: Path) -> dict | None:
    """Snapshot of an actual analysis of this current file, for project provenance."""
    signature = (str(source), source.stat().st_mtime_ns, source.stat().st_size)
    job = analysis_jobs.get(_cache.get(signature), {})
    if job.get("status") != "succeeded":
        return None
    return json.loads(json.dumps(job["result"]))


def category_catalog(settings: SourceAnalysisSettings) -> dict:
    return json.loads(Path(settings.catalog_path).read_text(encoding="utf-8"))


def classify_metadata(metadata: dict, catalog: dict) -> dict:
    """Classify available audio-derived terms, leaving ambiguous material unknown."""
    metas = metadata.get("metas") or {}
    genres = metadata.get("genre") or metas.get("genres") or ""
    description = metadata.get("prompt") or metas.get("caption") or ""
    # Use the structured musical genre, not arbitrary caption mentions such
    # as "no electronic instruments". Missing genres stay undetermined.
    text = str(genres).casefold()
    hits = {
        family: [term for term in catalog[family]
                 if re.search(rf"(?<!\w){re.escape(term.casefold())}(?!\w)", text)]
        for family in ("electronic", "non_electronic")
    }
    electronic, other = bool(hits["electronic"]), bool(hits["non_electronic"])
    classification = "mixed" if electronic and other else (
        "electronic" if electronic else "non_electronic" if other else "unknown")
    from genre_glossary import glossary_line
    return {"classification": classification, "genres": genres,
            "glossary_genre": glossary_line(str(genres)),
            "description": description, "evidence": hits,
            "categories": catalog["categories"], "explanation": catalog["explanation"],
            "method": "ACE-Step full_analysis_only", "confidence": None,
            "classification_basis": "audio-derived genre metadata"}


def _make_clip(source: Path, destination: Path, seconds: float) -> dict:
    if seconds <= 0:
        raise ValueError("source_analysis.sample_seconds debe ser positivo")
    audio = AudioSegment.from_file(source)
    if not len(audio):
        raise ValueError("El audio no contiene muestras")
    length = min(len(audio), round(seconds * 1000))
    start = (len(audio) - length) // 2
    audio[start:start + length].export(destination, format="wav")
    return {"start": start / 1000, "end": (start + length) / 1000,
            "source_duration": len(audio) / 1000}


def visible_analysis_phase(_progress_text: str) -> str:
    """El sondeo del motor trae su último log. La mesa solo enseña esta frase."""
    return "El modelo local analiza el audio"


async def analyze_source(music: Any, source: Path, settings: SourceAnalysisSettings,
                         update: Callable[[str], None]) -> dict:
    """Invoke native audio-to-codes + local LM and read its raw analysis result."""
    from music_service import GenerationRequest, MusicEngineError

    descriptor, temp_name = tempfile.mkstemp(prefix="musicia-analysis-", suffix=".wav")
    import os
    os.close(descriptor)
    clip = Path(temp_name)
    try:
        update("Preparando un fragmento del audio original")
        audio_range = await asyncio.to_thread(_make_clip, source, clip, settings.sample_seconds)
        request = GenerationRequest(prompt="", instrumental=True, source_path=str(clip),
                                    task_type="cover", duration_seconds=None)
        payload = music.build_payload(request)
        payload.update(full_analysis_only=True, src_audio_path=str(clip), batch_size=1)
        update("El modelo local analiza el audio")
        accepted = await music._request("POST", music.engine.submit_path, json=payload)
        task_id = accepted.get("task_id")
        if not task_id:
            raise MusicEngineError(f"El análisis no devolvió task_id: {accepted}")
        deadline = time.monotonic() + settings.timeout_seconds
        while True:
            raw = await music._request("POST", music.engine.result_path,
                                       json={"task_id_list": [task_id]})
            item = raw[0] if isinstance(raw, list) and raw else raw
            if isinstance(item, dict):
                state = int(item.get("status", 0))
                if item.get("progress_text"):
                    update(visible_analysis_phase(str(item["progress_text"])))
                result = item.get("result")
                if isinstance(result, str):
                    result = json.loads(result) if result else []
                if state == 2:
                    raise MusicEngineError(f"El análisis del motor falló: {result or item}")
                if state == 1:
                    metadata = result[0] if isinstance(result, list) and result else result
                    if not isinstance(metadata, dict):
                        raise MusicEngineError("El motor terminó sin metadatos de análisis")
                    found = classify_metadata(metadata, category_catalog(settings))
                    found.update(analysis_range=audio_range, engine_task_id=task_id,
                                 source_name=source.name,
                                 model_metadata=metadata.get("metas", {}))
                    return found
            if time.monotonic() >= deadline:
                raise MusicEngineError("Tiempo agotado en el análisis local del audio")
            await asyncio.sleep(settings.poll_interval)
    finally:
        clip.unlink(missing_ok=True)


def register_source_understanding(app: Any, music: Any, settings: Any,
                                  find_audio: Callable, gpu_busy: Callable | None = None,
                                  lifecycle: Any = None):
    from remix_project import COMPUTE_LOCK

    async def run(job_id: str, source: Path):
        job = analysis_jobs[job_id]
        try:
            async with COMPUTE_LOCK:
                job.update(status="running", phase="Analizando audio")
                result = await analyze_source(music, source, settings.source_analysis,
                                              lambda phase: job.update(phase=phase))
                job.update(status="succeeded", phase="Análisis disponible", result=result)
        except Exception as exc:
            logger.exception("Fallo real en análisis de fuente")
            job.update(status="failed", phase="Error de análisis", error=str(exc))

    @app.post("/music/remix/analyze")
    async def submit(request: SourceAnalysisRequest, background: BackgroundTasks):
        source = find_audio(request.source_name, request.source_kind)
        signature = (str(source), source.stat().st_mtime_ns, source.stat().st_size)
        cached = _cache.get(signature)
        if cached in analysis_jobs and analysis_jobs[cached]["status"] != "failed":
            return {"job_id": cached, "cached": True}
        busy = gpu_busy() if gpu_busy else active_analysis()
        if busy:
            raise HTTPException(409, detail="Hay una operación en curso; analiza al terminar")
        if lifecycle is not None:
            await lifecycle.ensure_awake()
        if not (await music.health()).get("reachable"):
            raise HTTPException(503, detail="El motor local de análisis no está activo")
        # Health yields to concurrent requests: reserve only after rechecking.
        busy = gpu_busy() if gpu_busy else active_analysis()
        if busy:
            raise HTTPException(409, detail="Hay una operación en curso; analiza al terminar")
        job_id = uuid.uuid4().hex
        analysis_jobs[job_id] = {"job_id": job_id, "status": "queued",
                                 "phase": "Esperando análisis", "error": None}
        _cache[signature] = job_id
        terminal = [key for key, job in analysis_jobs.items()
                    if job["status"] in {"failed", "succeeded"}]
        for key in terminal[:-max(1, settings.source_analysis.max_history)]:
            analysis_jobs.pop(key, None)
        for key in list(_cache):
            if _cache[key] not in analysis_jobs:
                _cache.pop(key)
        background.add_task(run, job_id, source)
        return {"job_id": job_id, "cached": False}

    @app.get("/music/remix/analyze/{job_id}")
    async def status(job_id: str):
        if job_id not in analysis_jobs:
            raise HTTPException(404, detail="No existe ese análisis")
        return analysis_jobs[job_id]
