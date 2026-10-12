"""Separación de voces en local con demucs (venv propio: backend/demucs-venv).

El motor ACE-Step no separa stems, así que la separación va en su propio
entorno con torch. Las operaciones solo leen pesos ya instalados; descargar
modelos requiere autorización explícita fuera de este servicio.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import threading
import time
import tempfile
from pathlib import Path
from typing import Callable

from loguru import logger

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEMUCS_VENV = PROJECT_ROOT / "backend" / "demucs-venv"
DEMUCS_PYTHON = DEMUCS_VENV / "Scripts" / "python.exe"
# VRAM libre mínima (MB) para usar la GPU: por debajo, se va por CPU.
GPU_MIN_FREE_MB = 2600
# El import de demucs+torch tarda ~11 s en frío y más con el motor ACE-Step
# cargando; con 60 s y SIN LOG, el chequeo falló una vez en frío y el falso
# negativo se cacheó para toda la sesión (bug 2026-10-10, remix 0540d437).
CHEQUEO_TIMEOUT_S = 120
# Un negativo cacheado PARA TODA LA PROCESIÓN es lo que mató el remix del
# 2026-10-10: el negativo caduca y se vuelve a comprobar; el positivo no.
NEGATIVO_TTL_S = 60.0
_CHEQUEO = threading.Lock()


def _instalado() -> bool:
    """Comprobación real: importa demucs+torch en un subproceso (segundos).

    Registra duración y motivo de cada fallo: sin eso, un falso negativo es
    indistinguible de «no instalado» (se vio el 2026-10-09 y 2026-10-10).
    """
    if not DEMUCS_PYTHON.exists():
        logger.warning(f"Motor de separación ausente: no existe {DEMUCS_PYTHON}")
        return False
    inicio = time.monotonic()
    try:
        proc = subprocess.run(
            [str(DEMUCS_PYTHON), "-c", "import demucs, torch; print('ok')"],
            capture_output=True, text=True, errors="replace",
            timeout=CHEQUEO_TIMEOUT_S,
        )
    except subprocess.TimeoutExpired:
        logger.error(
            f"Chequeo de demucs sin responder en {CHEQUEO_TIMEOUT_S} s "
            "(máquina cargada): se repetirá en {NEGATIVO_TTL_S:.0f} s"
        )
        return False
    except (OSError, subprocess.SubprocessError) as exc:
        logger.error(f"Chequeo de demucs imposible ({exc!r}): se repetirá en "
                     f"{NEGATIVO_TTL_S:.0f} s")
        return False
    duracion = round(time.monotonic() - inicio, 1)
    ok = proc.returncode == 0 and "ok" in (proc.stdout or "")
    if ok:
        logger.info(f"Motor de separación verificado (demucs+torch en {duracion} s)")
    else:
        cola = (proc.stderr or proc.stdout or "").strip().splitlines()[-4:]
        logger.error(
            f"Chequeo de demucs falló (rc={proc.returncode}, {duracion} s): "
            f"{' | '.join(cola)} — se repetirá en {NEGATIVO_TTL_S:.0f} s"
        )
    return ok


# ¿Instalado o no? El positivo se contesta UNA vez por proceso (la
# instalación no cambia mientras la app corre). El NEGATIVO caduca cada
# NEGATIVO_TTL_S: un chequeo que falló por frío/carga no puede dejar la
# separación muerta toda la sesión (bug 2026-10-10). La comprobación importa
# torch, así que NUNCA corre en el hilo del evento (bug 2026-10-08: en cada
# llamada congelaba la API ~5 s y en CREAR el AÑADIR salía «SIN DATOS DEL
# MOTOR»); siempre se pide desde `asyncio.to_thread` o un hilo.
_DISPONIBLE: bool | None = None
_DISPONIBLE_TS: float = 0.0


def is_available() -> bool:
    """¿Está instalado el motor de separación? (positivo cacheado, negativo
    con caducidad NEGATIVO_TTL_S)"""
    global _DISPONIBLE, _DISPONIBLE_TS
    if _disponible_cacheado():
        return _DISPONIBLE is True
    with _CHEQUEO:
        if _disponible_cacheado():
            return _DISPONIBLE is True
        _DISPONIBLE = _instalado()
        _DISPONIBLE_TS = time.monotonic()
        return _DISPONIBLE


def _disponible_cacheado() -> bool:
    """¿Hay un resultado en vigor (positivo para siempre, negativo TTL)?"""
    if _DISPONIBLE is True:
        return True
    if _DISPONIBLE is False:
        return (time.monotonic() - _DISPONIBLE_TS) < NEGATIVO_TTL_S
    return False


def free_vram_mb() -> int:
    """VRAM libre en MB (0 si no hay GPU o nvidia-smi no está)."""
    if shutil.which("nvidia-smi") is None:
        return 0
    try:
        proc = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.free", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=20,
        )
        return int(proc.stdout.strip().splitlines()[0])
    except (OSError, ValueError, IndexError, subprocess.SubprocessError):
        return 0


def pick_device() -> str:
    """GPU si hay VRAM de sobra (el motor ACE-Step también la usa); si no, CPU."""
    free = free_vram_mb()
    return "cuda" if free >= GPU_MIN_FREE_MB else "cpu"


def run_cancellable_process(cmd, settings, cancelled=None):
    """No libera el trabajo hasta que el proceso local ha terminado de verdad."""
    if cancelled and cancelled():
        raise RuntimeError("Cancelado por el usuario")
    started = time.monotonic()
    with subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          text=True, errors="replace") as proc:
        try:
            while True:
                if cancelled and cancelled():
                    raise RuntimeError("Cancelado por el usuario")
                if time.monotonic() - started > settings.subprocess_timeout_seconds:
                    raise RuntimeError("El proceso de separación agotó el tiempo máximo configurado")
                try:
                    stdout, stderr = proc.communicate(timeout=settings.subprocess_poll_seconds)
                    return subprocess.CompletedProcess(cmd, proc.returncode, stdout, stderr)
                except subprocess.TimeoutExpired:
                    continue
        finally:
            if proc.poll() is None:
                if os.name == "nt":
                    # El python.exe del venv puede ser un launcher con otro
                    # Python hijo. Matar el PID padre dejaría Demucs/GPU vivo.
                    # /T se limita al árbol del proceso que acabamos de crear.
                    stopped = subprocess.run(
                        ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                        capture_output=True, text=True, errors="replace",
                        timeout=settings.subprocess_termination_seconds,
                    )
                    if stopped.returncode and proc.poll() is None:
                        raise RuntimeError(f"No se pudo terminar el árbol del separador {proc.pid}: {stopped.stderr or stopped.stdout}")
                else:
                    proc.terminate()
                try:
                    proc.communicate(timeout=settings.subprocess_termination_seconds)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.communicate()


class SeparatorService:
    """Extrae la voz (y la base) de una pista real."""

    @staticmethod
    def separate_groups(
        source: Path, out_dir: Path, stem_name: str, settings,
        cancelled: Callable[[], bool] | None = None,
    ) -> dict:
        """Cuatro grupos reales, float WAV; sin descargas ni resultados ajenos."""
        if not DEMUCS_PYTHON.is_file():
            raise RuntimeError("No está instalado el separador local Demucs")
        if not source.is_file():
            raise FileNotFoundError(source)
        from pydub import AudioSegment

        device = pick_device() if settings.demucs_device == "auto" else settings.demucs_device
        if device not in {"cpu", "cuda"}:
            raise ValueError("remix.demucs_device debe ser auto, cpu o cuda")
        out_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="musicia-groups-", dir=out_dir) as work:
            cmd = [
                str(DEMUCS_PYTHON), str(Path(__file__).with_name("demucs_local.py")),
                "-n", settings.demucs_model, "-d", device, "--float32",
                "--clip-mode", "none", "--shifts", str(settings.demucs_shifts),
                "--overlap", str(settings.demucs_overlap), "-o", work, str(source),
            ]
            proc = run_cancellable_process(cmd, settings, cancelled)
            if proc.returncode:
                tail = (proc.stderr or proc.stdout or "").strip().splitlines()[-8:]
                raise RuntimeError(f"Demucs falló en {device}: {' | '.join(tail)}")
            produced = Path(work) / settings.demucs_model / source.stem
            groups = []
            for group in settings.groups:
                src = produced / f"{group['id']}.wav"
                if not src.is_file():
                    raise RuntimeError(f"Demucs no produjo el grupo {group['id']}")
                target = out_dir / f"{stem_name}-{group['id']}.wav"
                shutil.copyfile(src, target)
                audio = AudioSegment.from_file(target)
                if len(audio) <= 0:
                    raise RuntimeError(f"El grupo {group['id']} está vacío o corrupto")
                groups.append({
                    **group, "file_name": target.name,
                    "duration_seconds": len(audio) / 1000,
                    "rms_dbfs": round(audio.dBFS, 2) if audio.rms else None,
                    "url": f"/music/audio/{target.name}",
                })
        return {"device": device, "groups": groups}

    @staticmethod
    def separate(source: Path, out_dir: Path, stem_name: str,
                 cancelled: Callable[[], bool] | None = None, settings=None) -> dict:
        """Separa `source` en voz y base usando demucs.

        Escribe `{stem_name}-voces.mp3` y `{stem_name}-base.mp3` en `out_dir`.
        Lanza RuntimeError con el motivo real si algo falla (nunca finge).
        """
        # Guard barato y sin cache: un negativo cacheado (bug 2026-10-10) no
        # puede aquí bloquear un remix. Si el venv existe, demucs se lanza y
        # su error real viaja; el chequeo pesado solo lo pide la UI de estado.
        if not DEMUCS_PYTHON.exists():
            raise RuntimeError(
                "El motor de separación no está instalado (backend/demucs-venv). "
                "Instálalo o usa la mezcla con las pistas tal cual."
            )
        if not source.exists():
            raise FileNotFoundError(f"No existe la pista: {source.name}")

        if settings is None:
            from config import get_settings
            settings = get_settings().remix
        if cancelled and cancelled():
            raise RuntimeError("Cancelado por el usuario")
        device = pick_device() if settings.demucs_device == "auto" else settings.demucs_device
        logger.info(f"Separando {source.name} en {device} (VRAM libre: {free_vram_mb()} MB)")

        out_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="musicia-voice-", dir=out_dir) as work:
            cmd = [
                str(DEMUCS_PYTHON), str(Path(__file__).with_name("demucs_local.py")),
                "--two-stems=vocals", "-d", device, "-n", settings.demucs_model,
                "--shifts", str(settings.demucs_shifts), "--overlap", str(settings.demucs_overlap),
                "-o", work, str(source),
            ]
            proc = run_cancellable_process(cmd, settings, cancelled)
            if proc.returncode != 0:
                tail = (proc.stderr or proc.stdout or "").strip().splitlines()[-4:]
                raise RuntimeError(f"demucs falló en {device}: {' | '.join(tail)}")

            # Ruta propia exacta: no reutilizar stems de otro trabajo.
            produced = Path(work) / settings.demucs_model / source.stem
            vocals, base = produced / "vocals.wav", produced / "no_vocals.wav"
            if not vocals.is_file() or not base.is_file():
                raise RuntimeError("demucs terminó pero no produjo los stems esperados")

            results = {}
            for label, src in (("voces", vocals), ("base", base)):
                target = out_dir / f"{stem_name}-{label}.mp3"
                proc = run_cancellable_process(
                    ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(src),
                     "-c:a", "libmp3lame", "-b:a", settings.export_bitrate, str(target)],
                    settings, cancelled,
                )
                if proc.returncode:
                    raise RuntimeError(f"ffmpeg falló al exportar {label}: {proc.stderr or proc.stdout}")
                results[label] = target.name
        logger.info(f"Separación lista: {results} en {device}")
        return {
            "device": device,
            "vocals": results["voces"],
            "base": results["base"],
        }
