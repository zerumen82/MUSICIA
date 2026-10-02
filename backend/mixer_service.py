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

from audio_analysis import detect_groove

# Objetivo de sonoridad: -14 LUFS es el estándar de streaming (Spotify/Apple).
TARGET_LUFS = -14.0
# True peak máximo para que nada sature al exportar.
TARGET_TP = -1.0
# Desfasos por debajo de esto son ruido de medición: no se tocan.
MIN_PHASE_SHIFT_MS = 5.0
# Confianza mínima del groove para fiarse y alinear. Por debajo, el tempo es
# basura (p. ej. una voz sola sin bateria) y alinear DESTRUYE la pista.
MIN_GROOVE_CONFIDENCE = 0.12
# Rango de tempo en el que tiene sentido cuadrar: fuera de él ya no es
# "cuadrar la bateria", es destrozar el audio.
MIN_TEMPO_RATIO = 0.8
MAX_TEMPO_RATIO = 1.25


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


def plan_alignment(base_groove: dict, vocal_groove: dict) -> dict | None:
    """Propone cómo cuadrar la pista de voz con la base (no la mezcla).

    Devuelve None (y explica por qué) cuando no es seguro cuadrar: si el
    groove no es fiable o si el ajuste sería tan grande que rompería el audio.
    Mejor no cuadrar que destrozar la pista.
    """
    base_bpm = float(base_groove["bpm"])
    vocal_bpm = float(vocal_groove["bpm"])
    base_conf = float(base_groove.get("confidence") or 0)
    vocal_conf = float(vocal_groove.get("confidence") or 0)

    if base_conf < MIN_GROOVE_CONFIDENCE or vocal_conf < MIN_GROOVE_CONFIDENCE:
        return None
    ratio = base_bpm / vocal_bpm if vocal_bpm else 1.0
    if not MIN_TEMPO_RATIO <= ratio <= MAX_TEMPO_RATIO:
        return None

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


def _loudnorm_args(measured: dict, measured_flag: bool) -> str:
    """Argumentos de loudnorm; con `measured` se usan los datos de la 1ª pasada."""
    if measured_flag and measured.get("input_i") not in (None, "nan"):
        return (
            f"I={TARGET_LUFS:g}:TP={TARGET_TP:g}:LRA=11:"
            f"measured_I={measured['input_i']}:"
            f"measured_TP={measured.get('input_tp')}:"
            f"measured_LRA={measured.get('input_lra')}:"
            f"measured_thresh={measured.get('input_thresh', -24)}:"
            "offset=0:linear=true:print_format=summary"
        )
    return f"I={TARGET_LUFS:g}:TP={TARGET_TP:g}:LRA=11:print_format=summary"


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
                        "input_thresh": float(data.get("input_thresh", -24.0)),
                    }
                except (json.JSONDecodeError, ValueError, TypeError):
                    pass
                collecting = False
    return {}


def run_ffmpeg(args: list[str], output: Path) -> None:
    """Ejecuta ffmpeg y falla con el motivo REAL si algo va mal."""
    proc = subprocess.run(
        ["ffmpeg", "-hide_banner", "-nostats", "-y", *args],
        capture_output=True, text=True, errors="replace",
    )
    if proc.returncode != 0 or not output.exists():
        tail = (proc.stderr or "").strip().splitlines()[-3:]
        raise RuntimeError(f"ffmpeg falló: {' | '.join(tail)}")


def force_tempo(source: Path, out: Path, factor: float) -> dict:
    """Fuerza un tempo (factor >1 acelera) SIN cambiar el tono."""
    if factor <= 0.05 or factor > 8:
        raise ValueError("El factor de tempo debe estar entre 0,05 y 8")
    run_ffmpeg(
        ["-i", str(source), "-af", _atempo_chain(factor), "-c:a", "libmp3lame",
         "-b:a", "192k", "-f", "mp3", str(out)],
        out,
    )
    return {"file_name": out.name, "tempo_factor": round(factor, 4)}


def make_loop(source: Path, out: Path, seconds: float) -> dict:
    """Exporta un fragmento (loop) como pista nueva, sin recomprimir el resto."""
    if seconds <= 1:
        raise ValueError("El loop debe durar al menos 1 segundo")
    run_ffmpeg(
        ["-i", str(source), "-t", f"{seconds:.3f}", "-c:a", "libmp3lame",
         "-b:a", "192k", "-f", "mp3", str(out)],
        out,
    )
    return {"file_name": out.name, "seconds": round(seconds, 2)}


def crossfade(tracks: list[Path], out: Path, fade_seconds: float = 4.0) -> dict:
    """Funde varias pistas en cadena igualando su tempo (como un DJ).

    Cada pista se estira al tempo de la primera (sin tocar el tono) y se
    mezclan con fundidos solapados; el resultado se normaliza a -14 LUFS.
    """
    if len(tracks) < 2:
        raise ValueError("Hacen falta al menos dos pistas para un crossfade")
    if not 0.5 <= fade_seconds <= 15:
        raise ValueError("El fundido debe estar entre 0,5 y 15 segundos")

    base_groove = detect_groove(tracks[0])
    args: list[str] = []
    for track in tracks:
        args += ["-i", str(track)]
    filters: list[str] = []
    for index, track in enumerate(tracks):
        chain: list[str] = []
        if index > 0:
            try:
                groove = detect_groove(track)
                ratio = float(base_groove["bpm"]) / float(groove["bpm"])
                if abs(ratio - 1.0) > 0.005:
                    chain.append(_atempo_chain(ratio))
            except ValueError:
                pass  # sin tempo claro: se deja a su aire
        chain.append("aresample=48000")
        filters.append(
            f"[{index}:a]" + ",".join(chain) + f",aformat=sample_fmts=fltp:channel_layouts=stereo[pre{index}]"
        )
    # crossfade encadenado: el fundido solapa con la pista anterior
    last = "[pre0]"
    for index in range(1, len(tracks)):
        label = f"[cf{index}]"
        filters.append(
            f"{last}[pre{index}]acrossfade=d={fade_seconds:g}:c1=tri:c2=tri{label}"
        )
        last = label
    filters.append(f"{last}loudnorm=I={TARGET_LUFS:g}:TP={TARGET_TP:g}:LRA=11[out]")

    run_ffmpeg(
        [*args, "-filter_complex", ";".join(filters), "-map", "[out]",
         "-c:a", "libmp3lame", "-b:a", "192k", "-f", "mp3", str(out)],
        out,
    )
    return {"file_name": out.name, "tracks": len(tracks), "fade_seconds": fade_seconds}


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

        def render(target: Path, extra_filter: str | None) -> None:
            chain = list(filters)
            master = "[mezcla]"
            if extra_filter:
                chain.append(f"{master}{extra_filter}[out]")
                master = "[out]"
            run_ffmpeg(
                ["-i", str(base), "-i", str(vocal),
                 "-filter_complex", ";".join(chain), "-map", master,
                 "-c:a", "libmp3lame", "-b:a", "192k", "-f", "mp3", str(target)],
                target,
            )

        used_filters = ";".join(filters)
        if normalize_lufs:
            # Dos pasadas, como un master de estudio: 1ª render sin normalizar
            # para MEDIR, 2ª con esos datos (si no, el resultado se queda
            # corto del objetivo en material dinámico).
            probe = out.with_name(f"{out.stem}-probe.mp3")
            try:
                render(probe, None)
                measured = measure_loudness(probe)
                render(out, f"loudnorm={_loudnorm_args(measured, measured_flag=True)}")
                used_filters = f"{used_filters};loudnorm(2 pasadas {measured})"
            finally:
                probe.unlink(missing_ok=True)
        else:
            render(out, None)

        info = measure_loudness(out)
        logger.info(f"Mezcla lista: {out.name} {info}")
        return {
            "output_path": str(out),
            "applied": bool(alignment),
            "loudness": info,
            "filters": used_filters,
        }
