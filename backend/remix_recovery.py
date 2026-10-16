"""Recibos verificables de WAV descargados; nunca envía tareas al motor."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
from dataclasses import asdict
from pathlib import Path

from music_service import GeneratedTrack

RECEIPT_NAME = "downloaded-batch.json"
RECEIPT_VERSION = 1


def receipt_digest(receipt: dict) -> str:
    """Ancla WAV y metadatos juntos en el historial independiente del recibo."""
    canonical = json.dumps(receipt, ensure_ascii=False, sort_keys=True,
                           separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_json(path: Path, value: dict | list) -> None:
    """Reemplaza un documento completo, sin exponer un JSON parcial."""
    temporary = path.with_name(path.name + ".tmp")
    try:
        with temporary.open("w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def checked_path(work: Path, relative: str) -> Path:
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
        raise ValueError("El recibo contiene una ruta relativa inválida")
    path = (work / relative).resolve()
    if not path.is_relative_to(work.resolve()) or path == work.resolve() or not path.is_file():
        raise ValueError("El archivo del recibo falta o sale de la carpeta del trabajo")
    return path


def work_directory(outputs: Path, job_id: str) -> Path:
    if not job_id or Path(job_id).name != job_id or job_id in {".", ".."}:
        raise ValueError("Identificador de trabajo inválido")
    root = (outputs / "_remix").resolve()
    if not root.is_relative_to(outputs.resolve()):
        raise ValueError("La carpeta _remix sale del directorio de salidas")
    work = (root / job_id).resolve()
    if not work.is_relative_to(root) or work == root:
        raise ValueError("La carpeta del trabajo sale de outputs/_remix")
    return work


def require_unpublished(job: dict) -> None:
    if job.get("cancelled") or "cancelad" in str(job.get("error") or "").lower():
        raise ValueError("Un trabajo cancelado no se puede recuperar")
    if job.get("status") == "succeeded" or job.get("result"):
        raise ValueError("El trabajo ya tiene resultados publicados")
    if job.get("status") not in {"running", "failed"}:
        raise ValueError("Solo se puede completar un trabajo interrumpido")
    if job.get("status") == "failed" and not str(job.get("error") or "").startswith("Interrumpido:"):
        raise ValueError("El fallo del trabajo no corresponde a una interrupción")


def batch_context(job, source, reference, request, duration, settings) -> dict:
    if request.model_dump() != job.get("project"):
        raise ValueError("La petición no coincide con el proyecto guardado")
    digest = file_digest(source)
    if digest != job.get("source_digest") or digest != job.get("operations", {}).get("source_digest"):
        raise ValueError("La fuente cambió desde que se solicitó el remix")
    parameters = job.get("effective_parameters") or {}
    if not job.get("engine_task_id") or not parameters:
        raise ValueError("Faltan la tarea o los parámetros reales del motor")
    return {
        "job_id": job["job_id"], "engine_task_id": job["engine_task_id"],
        "project": request.model_dump(), "source_digest": digest,
        "reference_digest": file_digest(reference) if reference else None,
        "source_duration_seconds": duration,
        "timeline": job["operations"]["timeline"],
        "effective_parameters": parameters,
        "processing": asdict(settings.remix),
    }


def file_entry(work: Path, path: Path) -> dict:
    relative = path.resolve().relative_to(work.resolve()).as_posix()
    checked_path(work, relative)
    return {"path": relative, "sha256": file_digest(path)}


def build_receipt(job, source, reference, request, duration, settings, generated, originals) -> dict:
    work = work_directory(settings.outputs_dir, job["job_id"])
    context = batch_context(job, source, reference, request, duration, settings)
    expected = context["effective_parameters"].get("batch_size")
    if not isinstance(expected, int) or isinstance(expected, bool) or expected <= 0 or len(generated) != expected:
        raise ValueError("El lote descargado está incompleto")
    prepared = {}
    for key, path in originals.items():
        if not path.resolve().is_relative_to(work.resolve()):
            digest = file_digest(path)
            target = work / f"prepared-{key}.wav"
            shutil.copyfile(path, target)
            if file_digest(target) != digest or file_digest(path) != digest:
                raise ValueError("El grupo original cambió al guardar el recibo")
            path = target
        prepared[key] = file_entry(work, path)
    return {"version": RECEIPT_VERSION, "context": context,
            "prepared_groups": prepared,
            "tracks": [{**file_entry(work, path), "track": asdict(track)} for path, track in generated]}


async def validate_receipt(receipt, job, source, reference, request, duration, settings, music):
    """Toda la validación precede a modificar el trabajo o a publicar un archivo."""
    require_unpublished(job)
    if receipt_digest(receipt) != job.get("operations", {}).get("downloaded_batch_sha256"):
        raise ValueError("El recibo no coincide con el SHA256 anclado en el historial")
    if request.scope != "groups":
        raise ValueError("La recuperación explícita solo admite remix Por pistas sin otra inferencia")
    work = work_directory(settings.outputs_dir, job["job_id"])
    context = batch_context(job, source, reference, request, duration, settings)
    if receipt.get("version") != RECEIPT_VERSION or receipt.get("context") != context:
        raise ValueError("El recibo no coincide con trabajo, fuente, petición, timeline o parámetros")
    expected = context["effective_parameters"].get("batch_size")
    tracks = receipt.get("tracks")
    if (isinstance(expected, bool) or not isinstance(expected, int) or expected <= 0
            or not isinstance(tracks, list) or len(tracks) != expected):
        raise ValueError("El lote descargado está incompleto")
    natural = context["timeline"]["natural_duration_seconds"]
    tolerance = settings.remix.duration_tolerance_seconds

    async def validate_file(entry):
        path = checked_path(work, entry["path"])
        if file_digest(path) != entry["sha256"]:
            raise ValueError(f"SHA256 distinto en {path.name}")
        seconds = await music.verify_audio(path) / 1000
        if abs(seconds - natural) > tolerance:
            raise ValueError(f"Duración natural incorrecta en {path.name}: {seconds:g}s")
        return path

    generated, seen = [], set()
    for entry in tracks:
        path = await validate_file(entry)
        if path in seen:
            raise ValueError("El lote repite un archivo en lugar de otra variante")
        seen.add(path)
        metadata = entry["track"]
        if not isinstance(metadata, dict) or not metadata.get("file"):
            raise ValueError("Faltan los metadatos reales de una variante")
        generated.append((path, GeneratedTrack(**metadata)))
    groups = receipt.get("prepared_groups") or {}
    if set(groups) != set(request.groups):
        raise ValueError("Faltan los cuatro grupos preparados del original")
    originals = {key: await validate_file(entry) for key, entry in groups.items()}
    return generated, originals
