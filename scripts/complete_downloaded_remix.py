"""Termina un lote Por pistas descargado. Solo inspecciona salvo --execute.

Ejecutar con backend/venv/Scripts/python.exe; no arranca API ni motor.
"""
from __future__ import annotations

import argparse
import asyncio
import copy
import ctypes
import gc
import hashlib
import json
import os
import socket
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from fastapi import FastAPI
import main
from music_service import GeneratedTrack, MusicService
from remix_project import RemixProjectRequest, RemixProjectRuntime, project_generation, timeline_plan, validate_project
from remix_recovery import (RECEIPT_NAME, atomic_json, build_receipt, checked_path,
                            file_digest, receipt_digest, require_unpublished, validate_receipt, work_directory)


def windows_arguments(command_line: str) -> list[str]:
    """Usa el parser de Windows para comparar el argv completo del launcher."""
    count = ctypes.c_int()
    parse = ctypes.windll.shell32.CommandLineToArgvW
    parse.argtypes = [ctypes.c_wchar_p, ctypes.POINTER(ctypes.c_int)]
    parse.restype = ctypes.POINTER(ctypes.c_wchar_p)
    arguments = parse(command_line, ctypes.byref(count))
    if not arguments:
        raise ctypes.WinError()
    try:
        return [arguments[index] for index in range(count.value)]
    finally:
        free = ctypes.windll.kernel32.LocalFree
        free.argtypes = [ctypes.c_void_p]
        free.restype = ctypes.c_void_p
        free(arguments)


def require_offline(settings) -> dict:
    """Rechaza listeners y procesos del stack, incluso si no llegaron a escuchar."""
    engine = urlsplit(settings.acestep.base_url)
    endpoints = [("127.0.0.1", settings.port), (engine.hostname, engine.port)]
    for host, port in endpoints:
        with socket.socket() as probe:
            probe.settimeout(settings.acestep.health_timeout)
            if probe.connect_ex((host, port)) == 0:
                raise ValueError(f"Detén API y motor antes de recuperar: hay un listener en {host}:{port}")
    if os.name != "nt":
        raise ValueError("La comprobación de procesos de esta reparación requiere Windows")
    command = ("Get-CimInstance Win32_Process | Where-Object { $_.Name -match '^(python|pythonw|uv|uvicorn).*' } "
               "| Select-Object ProcessId,ParentProcessId,CommandLine,ExecutablePath | ConvertTo-Json -Compress")
    result = subprocess.run(["powershell.exe", "-NoProfile", "-Command", command],
                            capture_output=True, text=True, check=True, timeout=settings.acestep.request_timeout)
    processes = json.loads(result.stdout or "[]")
    if isinstance(processes, dict):
        processes = [processes]
    current = next((item for item in processes if item["ProcessId"] == os.getpid()), None)
    for process in processes:
        command_line = (process.get("CommandLine") or "").lower().replace("/", "\\")
        executable = (process.get("ExecutablePath") or "").lower().replace("/", "\\")
        workspace = str(ROOT).lower()
        backend_python = str(ROOT / "backend" / "venv" / "Scripts" / "python.exe").lower()
        engine_python = str(ROOT / "vendor" / "ACE-Step-1.5" / ".venv" / "Scripts" / "python.exe").lower()
        own_api = (str(ROOT / "backend" / "main.py").lower() in command_line
                   or (executable == backend_python and ("main.py" in command_line or "main:app" in command_line))
                   or ("main:app" in command_line and workspace in command_line))
        own_engine = any(token in command_line for token in ("acestep-api", "acestep\\api_server", "acestep.api_server"))
        own_engine = own_engine and (workspace in command_line or executable == engine_python)
        own_repair = "complete_downloaded_remix.py" in command_line and (workspace in command_line or executable == backend_python)
        # python.exe del venv es un launcher que espera a su hijo Python real.
        # Solo ese padre inmediato, con idéntico argv y la identidad del venv,
        # forma parte de esta recuperación. Otra reparación sigue bloqueada.
        own_launcher = (own_repair and process["ProcessId"] == os.getppid()
                        and executable == backend_python and current is not None
                        and current.get("ParentProcessId") == process["ProcessId"]
                        and windows_arguments(process["CommandLine"])[1:]
                        == windows_arguments(current["CommandLine"])[1:])
        if own_launcher:
            continue
        if process["ProcessId"] != os.getpid() and (own_api or own_engine or own_repair):
            raise ValueError(f"Hay otro proceso de API/motor/recuperación activo: PID {process['ProcessId']}")
    return {"listeners": [], "conflicting_processes": [], "checked_at": datetime.now(timezone.utc).isoformat()}


def validate_historical_plan(job, request, source, reference, settings):
    duration = job["duration_seconds"]
    validate_project(request, duration, settings)
    timeline = job["operations"]["timeline"]
    measured = {"bpm_measured": timeline.get("bpm_measured"), "bpm_confidence": timeline.get("bpm_confidence")}
    if timeline_plan(request, duration, settings, measured) != timeline:
        raise ValueError("La timeline histórica no corresponde a la petición y configuración actuales")
    config = settings.remix
    expected_export = {"format": "mp3", "bitrate": config.export_bitrate,
                       "sample_rate": config.sample_rate, "peak_limit_dbfs": config.peak_limit_dbfs}
    if job["operations"].get("export") != expected_export:
        raise ValueError("La configuración de exportación difiere de la histórica")
    parameters = job["effective_parameters"]
    engine_source = Path(parameters["src_audio_path"])
    work = work_directory(settings.outputs_dir, job["job_id"])
    checked_path(work, engine_source.resolve().relative_to(work).as_posix())
    effective = main.music.build_payload(project_generation(request, engine_source, reference, settings))
    if effective != parameters:
        raise ValueError("Los parámetros actuales no coinciden con los usados por el motor")
    return duration


def legacy_receipt(cache, job, source, reference, request, duration, settings):
    """Lee el valor JSON de diskcache sin importar/picklear el motor."""
    cache = cache.resolve(strict=True)
    with sqlite3.connect(str(cache)) as database:
        rows = database.execute("SELECT mode, filename, value FROM Cache WHERE key = ?",
                                ("ace_step_v1.5_" + job["engine_task_id"],)).fetchall()
    if len(rows) != 1 or rows[0][0] != 1 or rows[0][1] is not None:
        raise ValueError("No hay un resultado JSON directo y único para la tarea en la caché")
    raw = rows[0][2]
    entries = json.loads(raw)
    expected = job["effective_parameters"]["batch_size"]
    if (not isinstance(entries, list) or len(entries) != expected
            or any(not isinstance(item, dict) or item.get("status") != 1 for item in entries)):
        raise ValueError("El resultado real de la caché no es un lote terminado completo")
    tracks = MusicService._parse_tracks(raw)
    work = work_directory(settings.outputs_dir, job["job_id"])
    authorized_audio = (cache.parent.parent / "tmp" / "api_audio").resolve(strict=True)
    generated = []
    for index, (entry, metadata) in enumerate(zip(entries, tracks)):
        parameters = job["effective_parameters"]
        if (metadata["seed"] is None or metadata["prompt"] != parameters["prompt"]
                or metadata["lyrics"] != parameters["lyrics"]
                or entry.get("dit_model") != parameters["model"]
                or entry.get("lm_model") != parameters.get("lm_model_path")):
            raise ValueError("Los metadatos reales no coinciden con la petición histórica")
        url = urlsplit(metadata["file"])
        query = parse_qs(url.query, strict_parsing=True)
        if (url.scheme or url.netloc or url.path != settings.acestep.audio_path
                or set(query) != {"path"} or len(query["path"]) != 1):
            raise ValueError("La referencia de audio del motor no es una ruta local autorizada")
        remote = Path(query["path"][0]).resolve(strict=True)
        if not remote.is_relative_to(authorized_audio):
            raise ValueError("El WAV del motor está fuera de la caché autorizada")
        local = checked_path(work, f"variante-{index + 1}.wav")
        if file_digest(remote) != file_digest(local):
            raise ValueError("El WAV local no coincide byte por byte con el resultado del motor")
        track = GeneratedTrack(**{key: value for key, value in metadata.items()
                                 if key in GeneratedTrack.__dataclass_fields__})
        generated.append((local, track))
    originals = {key: checked_path(work, Path(value).resolve().relative_to(work).as_posix())
                 for key, value in job["operations"]["prepared_groups"].items()}
    result = build_receipt(job, source, reference, request, duration, settings, generated, originals), entries
    gc.collect()
    return result


async def recover(args):
    report = {"job_id": args.job_id, "execute": args.execute, "status": "validating"}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    lock = None
    lock_path = main.HISTORY_FILE.with_suffix(".recovery.lock")
    try:
        report["offline"] = require_offline(main.settings)
        if args.execute:
            lock = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(lock, str(os.getpid()).encode("ascii"))
        history_bytes = main.HISTORY_FILE.read_bytes()
        history_hash = hashlib.sha256(history_bytes).hexdigest()
        history = json.loads(history_bytes)
        matches = [item for item in history.get("remix", []) if item.get("job_id") == args.job_id]
        if len(matches) != 1:
            raise ValueError("El historial no contiene un único trabajo con ese identificador")
        original_job = matches[0]
        job = copy.deepcopy(original_job)
        require_unpublished(job)
        request = RemixProjectRequest(**job["project"])
        if request.scope != "groups":
            raise ValueError("Esta recuperación solo admite Por pistas")
        source = main._find_audio(request.source_name, request.source_kind)
        reference = main._find_audio(request.reference_name, request.reference_kind) if request.reference_name else None
        duration = validate_historical_plan(job, request, source, reference, main.settings)
        work = work_directory(main.settings.outputs_dir, job["job_id"])
        receipt_path = work / RECEIPT_NAME
        engine_entries = None
        if receipt_path.is_file():
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            if not job["operations"].get("downloaded_batch_sha256"):
                if not args.engine_cache:
                    raise ValueError("El recibo carece de ancla histórica; indica --engine-cache para contrastarlo")
                checked, engine_entries = legacy_receipt(args.engine_cache, job, source, reference,
                                                         request, duration, main.settings)
                if receipt_digest(receipt) != receipt_digest(checked):
                    raise ValueError("El recibo sin ancla no coincide con el resultado real del motor")
                job["operations"]["downloaded_batch_sha256"] = receipt_digest(checked)
        elif args.engine_cache:
            receipt, engine_entries = legacy_receipt(args.engine_cache, job, source, reference,
                                                     request, duration, main.settings)
            job["operations"]["downloaded_batch_sha256"] = receipt_digest(receipt)
        else:
            raise ValueError("No hay recibo; para un trabajo antiguo indica --engine-cache")
        generated, _originals = await validate_receipt(receipt, job, source, reference, request,
                                                     duration, main.settings, main.music)
        report.update(status="validated", receipt=receipt,
                      history_sha256_before=history_hash,
                      source=str(source), seeds=[track.seed for _path, track in generated],
                      target_duration_seconds=request.duration_seconds)
        if not args.execute:
            return report
        report["offline_before_execute"] = require_offline(main.settings)
        if file_digest(main.HISTORY_FILE) != history_hash:
            raise ValueError("El historial cambió durante la validación")
        snapshot = args.report.parent / (args.report.stem + "-snapshot")
        snapshot.mkdir(exist_ok=False)
        (snapshot / "job_history-before.json").write_bytes(history_bytes)
        atomic_json(snapshot / "original-job.json", original_job)
        atomic_json(snapshot / "downloaded-batch.json", receipt)
        if engine_entries is not None:
            atomic_json(snapshot / "engine-result.json", engine_entries)
        if not receipt_path.exists():
            atomic_json(receipt_path, receipt)
        report["snapshot"] = str(snapshot)
        atomic_json(args.report, report)

        expected_history_hash = history_hash

        def guard_publish():
            require_offline(main.settings)
            if file_digest(main.HISTORY_FILE) != expected_history_hash:
                raise ValueError("El historial cambió; no se publican resultados ni sobrescriben trabajos ajenos")

        def save_selected():
            nonlocal expected_history_hash
            guard_publish()
            updated = copy.deepcopy(history)
            for index, item in enumerate(updated["remix"]):
                if item.get("job_id") == args.job_id:
                    updated["remix"][index] = main._snapshot_job(main._REMIX_KEPT, job)
                    break
            atomic_json(main.HISTORY_FILE, updated)
            expected_history_hash = file_digest(main.HISTORY_FILE)

        runtime = RemixProjectRuntime(
            FastAPI(), main.music, main.settings, {args.job_id: job}, {}, main._find_audio,
            main._gpu_busy, main._remember, main._public_side_job, main._push_event, save_selected,
            main._unique_output_path, main._safe_name, main._carry_ficha, main._measure_bpm,
            main._now, main._throw_if_cancelled)
        job["started"] = time.monotonic() - float(job.get("elapsed_seconds") or 0)
        save_selected()
        await runtime.finish_downloaded(job, source, reference, request, duration, receipt,
                                        before_publish=guard_publish)
        if job.get("status") != "succeeded":
            raise ValueError(job.get("error") or "El lote no terminó")
        result = job.get("result") or {}
        files = result.get("variants") or []
        if len(files) != len(generated) or len(result.get("metadata") or []) != len(generated):
            raise ValueError("La publicación final está incompleta")
        outputs = []
        target = job["operations"]["timeline"]["target_duration_seconds"]
        for name in files:
            path = main.settings.outputs_dir / name
            seconds = await main.music.verify_audio(path) / 1000
            if abs(seconds - target) > main.settings.remix.duration_tolerance_seconds:
                raise ValueError("La duración publicada no cumple el objetivo")
            outputs.append({"path": str(path), "sha256": file_digest(path),
                            "bytes": path.stat().st_size, "duration_seconds": seconds})
        after = json.loads(main.HISTORY_FILE.read_bytes())
        for family, rows in history.items():
            expected = [row for row in rows if family != "remix" or row.get("job_id") != args.job_id]
            actual = [row for row in after[family] if family != "remix" or row.get("job_id") != args.job_id]
            if actual != expected:
                raise ValueError("Se modificó un trabajo ajeno al lote recuperado")
        report.update(status="succeeded", result=result, outputs=outputs,
                      history_sha256_after=file_digest(main.HISTORY_FILE), other_jobs_unchanged=True)
        return report
    except Exception as exc:
        report.update(status="failed", error=str(exc))
        return report
    finally:
        try:
            atomic_json(args.report, report)
        finally:
            if lock is not None:
                os.close(lock)
                lock_path.unlink()


def cli():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--job-id", required=True)
    parser.add_argument("--engine-cache", type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    result = asyncio.run(recover(args))
    print(json.dumps({key: result.get(key) for key in ("job_id", "status", "error", "outputs")},
                     ensure_ascii=False, indent=2))
    return 1 if result["status"] == "failed" else 0


if __name__ == "__main__":
    raise SystemExit(cli())
