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
    # El análisis escucha la canción entera hasta este tope, no un único
    # fragmento central de 30 s: la descripción debe hablar del tema completo.
    max_seconds: float = 240.0
    poll_interval: float = 3.0
    timeout_seconds: float = 1800.0
    max_history: int = 30
    catalog_path: str = str(Path(__file__).with_name("source_categories.json"))


class SourceAnalysisRequest(BaseModel):
    source_name: str
    source_kind: Literal["upload", "output"]
    # Tramo elegido en la onda (segundos). Sin tramo, el análisis escoge el
    # tema entero o su centro, como antes.
    region_start: float | None = None
    region_end: float | None = None


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


def _make_clip(source: Path, destination: Path, seconds: float,
               region_start: float | None = None,
               region_end: float | None = None) -> dict:
    """Recorta el tramo pedido, como máximo `seconds`.

    Sin tramo pedido se conserva la elección automática: el tema entero si cabe
    en el tope y, si no, su centro (para no analizar solo la intro). Con tramo
    pedido se respeta su inicio y se corta al llegar al tope; `truncated`
    declara que no se escuchó todo lo marcado.
    """
    if seconds <= 0:
        raise ValueError("source_analysis.max_seconds debe ser positivo")
    audio = AudioSegment.from_file(source)
    if not len(audio):
        raise ValueError("El audio no contiene muestras")
    total = len(audio)
    total_seconds = total / 1000
    if region_start is None and region_end is None:
        length = min(total, round(seconds * 1000))
        start = (total - length) // 2
        heard_until = total
    else:
        if region_start is not None and region_start < 0:
            raise ValueError("El inicio del tramo no puede ser negativo")
        begin = float(region_start or 0.0)
        finish = min(float(region_end), total_seconds) if region_end is not None else total_seconds
        if begin >= total_seconds:
            raise ValueError("El tramo empieza después del final del audio")
        if finish <= begin:
            raise ValueError("El tramo elegido no tiene duración")
        start = round(begin * 1000)
        heard_until = start + round((finish - begin) * 1000)
        length = min(heard_until - start, round(seconds * 1000))
    audio[start:start + length].export(destination, format="wav")
    return {"start": start / 1000, "end": (start + length) / 1000,
            "source_duration": total_seconds,
            "truncated": start + length < heard_until}


def visible_analysis_phase(_progress_text: str) -> str:
    """El sondeo del motor trae su último log. La mesa solo enseña esta frase."""
    return "El modelo local analiza el audio"


async def analyze_source(music: Any, source: Path, settings: SourceAnalysisSettings,
                         update: Callable[[str], None],
                         region_start: float | None = None,
                         region_end: float | None = None) -> dict:
    """Invoke native audio-to-codes + local LM and read its raw analysis result."""
    from music_service import GenerationRequest, MusicEngineError

    descriptor, temp_name = tempfile.mkstemp(prefix="musicia-analysis-", suffix=".wav")
    import os
    os.close(descriptor)
    clip = Path(temp_name)
    try:
        update("Preparando un fragmento del audio original")
        audio_range = await asyncio.to_thread(_make_clip, source, clip, settings.max_seconds,
                                              region_start, region_end)
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
            try:
                # Sin chequeo de vida previo: el sondeo no reinicia el motor
                # que está analizando (misma regla que `status()`).
                raw = await music._request("POST", music.engine.result_path,
                                           json={"task_id_list": [task_id]},
                                           check_alive=False)
            except MusicEngineError as exc:
                # Un corte de transporte no cierra el análisis: se reintenta
                # hasta el plazo, como en la espera de una generación.
                if not music.poll_interrupted(exc):
                    raise
                logger.warning(f"Sondeo del análisis interrumpido: {exc}; se reintenta")
                if time.monotonic() >= deadline:
                    raise MusicEngineError(
                        "Tiempo agotado en el análisis local del audio") from exc
                await asyncio.sleep(settings.poll_interval)
                continue
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

    async def run(job_id: str, source: Path, region_start: float | None = None,
                  region_end: float | None = None):
        job = analysis_jobs[job_id]
        try:
            async with COMPUTE_LOCK:
                job.update(status="running", phase="Analizando audio")
                result = await analyze_source(music, source, settings.source_analysis,
                                              lambda phase: job.update(phase=phase),
                                              region_start, region_end)
                job.update(status="succeeded", phase="Análisis disponible", result=result)
        except Exception as exc:
            logger.exception("Fallo real en análisis de fuente")
            job.update(status="failed", phase="Error de análisis", error=str(exc))

    @app.post("/music/remix/analyze")
    async def submit(request: SourceAnalysisRequest, background: BackgroundTasks):
        source = find_audio(request.source_name, request.source_kind)
        # El tramo forma parte de la firma: analizar otra zona del mismo audio
        # es otro análisis, no el resultado cacheado de la anterior.
        signature = (str(source), source.stat().st_mtime_ns, source.stat().st_size,
                     request.region_start, request.region_end)
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
                                 "phase": "Esperando análisis", "error": None,
                                 "region_start": request.region_start,
                                 "region_end": request.region_end}
        _cache[signature] = job_id
        terminal = [key for key, job in analysis_jobs.items()
                    if job["status"] in {"failed", "succeeded"}]
        for key in terminal[:-max(1, settings.source_analysis.max_history)]:
            analysis_jobs.pop(key, None)
        for key in list(_cache):
            if _cache[key] not in analysis_jobs:
                _cache.pop(key)
        background.add_task(run, job_id, source, request.region_start, request.region_end)
        return {"job_id": job_id, "cached": False}

    @app.get("/music/remix/analyze/{job_id}")
    async def status(job_id: str):
        if job_id not in analysis_jobs:
            raise HTTPException(404, detail="No existe ese análisis")
        return analysis_jobs[job_id]
