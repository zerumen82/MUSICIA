"""Mezclador profesional en local (ffmpeg): alinea tempo y fase, iguala niveles.

Por qué ffmpeg y no pydub: `atempo` estira el tempo SIN cambiar el tono y
`loudnorm` normaliza a LUFS con límite de pico real, que es como se mezcla en
estudio. pydub solo suma dB y solapa (dejaba las baterías descuadradas).
"""
from __future__ import annotations

import json
import math
import shutil
import subprocess
from pathlib import Path

from loguru import logger

# Objetivo de sonoridad: -14 LUFS es el estándar de streaming (Spotify/Apple).
TARGET_LUFS = -14.0
# True peak máximo para que nada sature al exportar.
TARGET_TP = -1.0
# Desfasos por debajo de esto son ruido de medición: no se tocan.
MIN_PHASE_SHIFT_MS = 5.0


def _atempo_chain(ratio: float) -> str:
    """Cadena de atempo para relaciones fuera del rango útil de una sola vez."""
    filters = []
    remaining = ratio
    # atempo acepta 0.5-2.0 con buena calidad: se encadena.
    while remaining < 0.5:
        filters.append("atempo=0.5")
        remaining /= 0.5
    while remaining > 2.0:
        filters.append("atempo=2.0")
        remaining /= 2.0
    filters.append(f"atempo={remaining:.6f}")
    return ",".join(filters)


def plan_alignment(base_groove: dict, vocal_groove: dict) -> dict:
    """Propone cómo cuadrar la pista de voz con la base (no la mezcla).

    - `tempo_ratio`: >1 acelera la voz para igualar el tempo de la base.
    - `delay_ms`: cuánto se adelanta (negativo) o retrasa (positivo) la voz
      para que su golpe caiga exactamente en el de la base.
    """
    base_bpm = float(base_groove["bpm"])
    vocal_bpm = float(vocal_groove["bpm"])
    ratio = base_bpm / vocal_bpm if vocal_bpm else 1.0

    period_ms = float(base_groove.get("period_ms") or (60_000 / base_bpm))
    delta_ms = float(base_groove.get("phase_ms") or 0) - float(vocal_groove.get("phase_ms") or 0)
    # Normalizar el desfase al intervalo de un golpe (lo que importa es el compás).
    delay_ms = delta_ms % period_ms
    if delay_ms > period_ms / 2:
        delay_ms -= period_ms

    return {
        "base_bpm": base_bpm,
        "vocal_bpm": vocal_bpm,
        "tempo_ratio": round(ratio, 4),
        "delay_ms": round(delay_ms, 1),
        "period_ms": round(period_ms, 1),
        "base_confidence": base_groove.get("confidence"),
        "vocal_confidence": vocal_groove.get("confidence"),
    }


def measure_loudness(path: Path) -> dict:
    """Mide LUFS y true peak reales del fichero (ffmpeg, sin estimar).

    `loudnorm` imprime un bloque JSON multilínea al final del log: se recoge
    desde la primera llave hasta la última.
    """
    proc = subprocess.run(
        ["ffmpeg", "-hide_banner", "-nostats", "-i", str(path),
         "-af", "loudnorm=I=-14:TP=-1.0:LRA=11:print_format=json", "-f", "null", "-"],
        capture_output=True, text=True, errors="replace",
    )
    block: list[str] = []
    collecting = False
    for line in proc.stderr.splitlines():
        stripped = line.strip()
        if stripped.startswith("{"):
            collecting, block = True, [stripped]
            continue
        if collecting:
            block.append(stripped)
            if stripped.startswith("}"):
                try:
                    data = json.loads("\n".join(block))
                    return {
                        "input_i": float(data.get("input_i", "nan")),
                        "input_tp": float(data.get("input_tp", "nan")),
                        "input_lra": float(data.get("input_lra", "nan")),
                    }
                except (json.JSONDecodeError, ValueError, TypeError):
                    pass
                collecting = False
    return {}


class MixerService:
    """Mezclas dos pistas alineando el groove y normalizando el volumen."""

    @staticmethod
    def mix_tracks(
        base_track_path: str,
        vocal_track_path: str,
        output_path: str,
        base_volume: float = 0,
        vocal_volume: float = 0,
        alignment: dict | None = None,
        normalize_lufs: bool = True,
    ) -> dict:
        """Mezcla base + voz con ffmpeg.

        `alignment` es el plan de `plan_alignment`; si llega, aplica atempo
        (tempo) y adelay (fase) a la voz. Con `normalize_lufs` cierra con
        loudnorm a -14 LUFS y pico máximo -1 dBTP.
        """
        base = Path(base_track_path)
        vocal = Path(vocal_track_path)
        out = Path(output_path)
        for path in (base, vocal):
            if not path.exists():
                raise FileNotFoundError(f"No existe la pista: {path.name}")

        if shutil.which("ffmpeg") is None:
            raise RuntimeError("ffmpeg no está disponible en el PATH")

        base_chain: list[str] = []
        vocal_chain: list[str] = []
        if alignment:
            ratio = float(alignment.get("tempo_ratio") or 1.0)
            if abs(ratio - 1.0) > 0.005:
                vocal_chain.append(_atempo_chain(ratio))
            delay_ms = float(alignment.get("delay_ms") or 0)
            if abs(delay_ms) >= MIN_PHASE_SHIFT_MS:
                # `adelay` no admite valores negativos (rompe el grafo): si la
                # voz debe empezar antes, retrasamos la base lo mismo, que es
                # matemáticamente idéntico y no pierde audio.
                if delay_ms > 0:
                    vocal_chain.append(f"adelay=delays={delay_ms:.1f}:all=1")
                else:
                    base_chain.append(f"adelay=delays={abs(delay_ms):.1f}:all=1")
        vocal_chain.append(f"volume={vocal_volume}dB")

        filters = [
            "[0:a]" + ",".join([f"volume={base_volume}dB"] + base_chain) + "[base]",
            "[1:a]" + ",".join(vocal_chain) + "[voz]",
            "[base][voz]amix=inputs=2:duration=longest:normalize=0[mezcla]",
        ]
        master = "[mezcla]"
        if normalize_lufs:
            filters.append(
                f"{master}loudnorm=I={TARGET_LUFS:g}:TP={TARGET_TP:g}:LRA=11[out]"
            )
            master = "[out]"

        cmd = [
            "ffmpeg", "-hide_banner", "-nostats", "-y",
            "-i", str(base), "-i", str(vocal),
            "-filter_complex", ";".join(filters),
            "-map", master,
            "-c:a", "libmp3lame", "-b:a", "192k",
            "-f", "mp3",
            str(out),
        ]
        logger.info(f"Mezcla: base={base.name} voz={vocal.name} filtros={';'.join(filters)}")
        proc = subprocess.run(cmd, capture_output=True, text=True, errors="replace")
        if proc.returncode != 0 or not out.exists():
            tail = (proc.stderr or "").strip().splitlines()[-3:]
            raise RuntimeError(f"ffmpeg falló: {' | '.join(tail)}")

        info = measure_loudness(out)
        logger.info(f"Mezcla lista: {out.name} {info}")
        return {
            "output_path": str(out),
            "applied": bool(alignment),
            "loudness": info,
            "filters": ";".join(filters),
        }
