"""Separación de voces en local con demucs (venv propio: backend/demucs-venv).

El motor ACE-Step no separa stems, así que la separación va en su propio
entorno con torch. Nada sale a la nube: los pesos se descargan una vez a
~/.cache/torch y a partir de ahí es 100 % local.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from loguru import logger

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEMUCS_VENV = PROJECT_ROOT / "backend" / "demucs-venv"
DEMUCS_PYTHON = DEMUCS_VENV / "Scripts" / "python.exe"
# VRAM libre mínima (MB) para usar la GPU: por debajo, se va por CPU.
GPU_MIN_FREE_MB = 2600


def is_available() -> bool:
    """¿Está instalado el motor de separación?"""
    if not DEMUCS_PYTHON.exists():
        return False
    try:
        proc = subprocess.run(
            [str(DEMUCS_PYTHON), "-c", "import demucs, torch; print('ok')"],
            capture_output=True, text=True, timeout=60,
        )
        return proc.returncode == 0 and "ok" in proc.stdout
    except (OSError, subprocess.SubprocessError):
        return False


def _free_vram_mb() -> int:
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
    free = _free_vram_mb()
    return "cuda" if free >= GPU_MIN_FREE_MB else "cpu"


class SeparatorService:
    """Extrae la voz (y la base) de una pista real."""

    @staticmethod
    def separate(source: Path, out_dir: Path, stem_name: str) -> dict:
        """Separa `source` en voz y base usando demucs.

        Escribe `{stem_name}-voces.mp3` y `{stem_name}-base.mp3` en `out_dir`.
        Lanza RuntimeError con el motivo real si algo falla (nunca finge).
        """
        if not is_available():
            raise RuntimeError(
                "El motor de separación no está instalado (backend/demucs-venv). "
                "Instálalo o usa la mezcla con las pistas tal cual."
            )
        if not source.exists():
            raise FileNotFoundError(f"No existe la pista: {source.name}")

        device = pick_device()
        logger.info(f"Separando {source.name} en {device} (VRAM libre: {_free_vram_mb()} MB)")

        work = out_dir / "_separacion"
        work.mkdir(parents=True, exist_ok=True)
        cmd = [
            str(DEMUCS_PYTHON), "-m", "demucs",
            "--two-stems=vocals",
            "-d", device,
            "-n", "htdemucs",
            "-o", str(work),
            str(source),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, errors="replace")
        if proc.returncode != 0:
            tail = (proc.stderr or proc.stdout or "").strip().splitlines()[-4:]
            raise RuntimeError(f"demucs falló en {device}: {' | '.join(tail)}")

        # demucs escribe <model>/<canción>/{vocals,no_vocals}.<ext>
        produced = sorted(work.rglob("*"), key=lambda p: p.stat().st_mtime, reverse=True)
        vocals = next((p for p in produced if p.is_file() and p.stem == "vocals"), None)
        base = next((p for p in produced if p.is_file() and p.stem == "no_vocals"), None)
        if not vocals or not base:
            raise RuntimeError("demucs terminó pero no produjo los stems esperados")

        results = {}
        for label, src in (("voces", vocals), ("base", base)):
            target = out_dir / f"{stem_name}-{label}.mp3"
            subprocess.run(
                ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(src),
                 "-c:a", "libmp3lame", "-b:a", "192k", str(target)],
                capture_output=True, text=True, errors="replace", check=True,
            )
            results[label] = target.name
        shutil.rmtree(work, ignore_errors=True)
        logger.info(f"Separación lista: {results} en {device}")
        return {
            "device": device,
            "vocals": results["voces"],
            "base": results["base"],
        }
