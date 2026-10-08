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

from pydub import AudioSegment

from audio_analysis import ANALYSIS_RATE, detect_groove

# Objetivo de sonoridad: -14 LUFS es el estándar de streaming (Spotify/Apple).
TARGET_LUFS = -14.0
MP3_BITRATE = "192k"
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


def normalize_track(source: Path, dest: Path) -> dict:
    """Master de una pista al mismo LUFS que la mezcla, en dos datos medidos.

    La primera pasada solo mide. La segunda aplica ese medidor. Así una
    versión o un tramo salen al mismo nivel que una mezcla.
    """
    if shutil.which("ffmpeg") is None:
        raise RuntimeError("ffmpeg no está disponible en el PATH")
    if not source.exists():
        raise FileNotFoundError(f"No existe la pista: {source.name}")
    measured = measure_loudness(source)
    run_ffmpeg(
        ["-i", str(source), "-af", f"loudnorm={_loudnorm_args(measured, True)}",
         "-c:a", "libmp3lame", "-b:a", MP3_BITRATE, "-f", "mp3", str(dest)],
        dest,
    )
    return measure_loudness(dest)


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


def bars_duration_seconds(bpm: float, bars: int, beats_per_bar: int) -> float:
    """Duración de N compases. 4 compases de 4/4 son 16 golpes, no 4."""
    if bpm <= 0:
        raise ValueError("BPM no válido para el loop")
    if bars < 1 or beats_per_bar < 1:
        raise ValueError("El loop necesita al menos un compás")
    return (bars * beats_per_bar * 60.0) / float(bpm)


def first_beat_seconds(groove: dict) -> float:
    """Primer golpe que cae dentro del archivo.

    phase_ms negativo es un golpe anterior al inicio: el siguiente está
    un periodo más adelante.
    """
    phase_ms = float(groove.get("phase_ms") or 0)
    period_ms = float(groove.get("period_ms") or 0)
    if phase_ms < 0 and period_ms > 0:
        phase_ms += period_ms
    return max(0.0, phase_ms / 1000.0)


def _audio_seconds(path: Path) -> float:
    audio = AudioSegment.from_file(path)
    return len(audio) / 1000.0


def _frame_db(samples: list[int], start: int, frame: int) -> float:
    chunk = samples[start:start + frame]
    if not chunk:
        return -120.0
    mean_sq = sum(x * x for x in chunk) / len(chunk)
    if mean_sq <= 0:
        return -120.0
    return 20.0 * math.log10(math.sqrt(mean_sq) / 32768.0)


def _silence_regions(vocal: Path, mixer) -> list[tuple[float, float]]:
    """Tramos con voz. El silencio más corto que el mínimo no parte la frase."""
    audio = AudioSegment.from_file(vocal)
    mono = audio.set_channels(1).set_frame_rate(ANALYSIS_RATE).set_sample_width(2)
    samples = list(mono.get_array_of_samples())
    frame = max(1, int(ANALYSIS_RATE * mixer.vocal_frame_ms / 1000))
    silent_flags: list[bool] = []
    for start in range(0, len(samples) - frame + 1, frame):
        silent_flags.append(_frame_db(samples, start, frame) < mixer.vocal_silence_db)
    regions: list[tuple[float, float]] = []
    open_at: int | None = None
    for index, silent in enumerate(silent_flags):
        if not silent and open_at is None:
            open_at = index
        elif silent and open_at is not None:
            regions.append((open_at * frame / ANALYSIS_RATE, index * frame / ANALYSIS_RATE))
            open_at = None
    if open_at is not None:
        regions.append((open_at * frame / ANALYSIS_RATE, len(silent_flags) * frame / ANALYSIS_RATE))
    merged: list[tuple[float, float]] = []
    for start, end in regions:
        if merged and start - merged[-1][1] < mixer.vocal_min_silence_s:
            merged[-1] = (merged[-1][0], end)
        else:
            merged.append((start, end))
    return [(start, end) for start, end in merged if end - start >= mixer.vocal_min_phrase_s]


def _cut_long_phrases(
    regions: list[tuple[float, float]], piece_s: float, limit: int
) -> list[tuple[float, float]]:
    """Una frase más larga que un compás se parte. No se estira."""
    pieces: list[tuple[float, float]] = []
    step = max(piece_s, 0.4)
    for start, end in regions:
        if end - start <= step * 2:
            pieces.append((start, end))
            continue
        cursor = start
        while cursor < end - 0.2:
            nxt = min(end, cursor + step)
            if nxt - cursor >= 0.2:
                pieces.append((cursor, nxt))
            cursor = nxt
    if len(pieces) <= limit:
        return pieces
    picked = [pieces[round(i * (len(pieces) - 1) / (limit - 1))] for i in range(limit)]
    return picked


def _bar_starts(duration: float, groove: dict | None, mixer) -> list[float]:
    if groove and float(groove.get("confidence") or 0) >= MIN_GROOVE_CONFIDENCE:
        bpm = float(groove["bpm"])
        phase = max(0.0, float(groove.get("phase_ms") or 0) / 1000.0)
        bar = mixer.beats_per_bar * 60.0 / bpm
    else:
        phase = 0.0
        bar = float(mixer.fallback_bar_seconds)
    starts: list[float] = []
    cursor = phase
    while cursor < duration - 0.3:
        starts.append(cursor)
        cursor += bar
    return starts or [0.0]


def plan_vocal_arrangement(base: Path, vocal: Path, mixer, base_bpm: float | None = None) -> dict | None:
    """Reparte la voz en la base cuando la base es claramente más larga.

    Devuelve None si las dos duran parecido: ahí sigue el cuadre de siempre.
    No propone estirar la voz.

    `base_bpm`: si se conoce el BPM al que se generó la base (dato decidido,
    no estimación), manda sobre detect_groove, que lee mal las bases
    generadas. Sin dato, detección como antes.
    """
    base_s = _audio_seconds(base)
    vocal_s = _audio_seconds(vocal)
    if base_s <= 0 or vocal_s <= 0:
        return None
    if vocal_s > base_s * float(mixer.arrange_shorter_than):
        return None
    if base_bpm:
        groove = {"bpm": float(base_bpm), "confidence": 1.0, "phase_ms": 0.0}
    else:
        try:
            groove = detect_groove(base)
        except (ValueError, FileNotFoundError):
            groove = None
    if groove and float(groove.get("confidence") or 0) >= MIN_GROOVE_CONFIDENCE:
        piece_s = mixer.beats_per_bar * 60.0 / float(groove["bpm"])
    else:
        piece_s = float(mixer.fallback_bar_seconds)
    regions = _silence_regions(vocal, mixer)
    if not regions:
        raise ValueError("La voz no tiene frases que colocar")
    phrases = _cut_long_phrases(regions, piece_s, mixer.max_vocal_phrases)
    slots = _bar_starts(base_s, groove, mixer)
    if len(phrases) == 1:
        chosen = [slots[0]]
    else:
        chosen = [
            slots[round(i * (len(slots) - 1) / (len(phrases) - 1))]
            for i in range(len(phrases))
        ]
    placed: list[dict] = []
    cursor = 0.0
    for (src_start, src_end), at in zip(phrases, chosen):
        at = max(float(at), cursor)
        if at >= base_s - 0.2:
            break
        duration = min(src_end - src_start, base_s - at)
        if duration < 0.2:
            continue
        placed.append({
            "source_start": round(src_start, 3),
            "source_end": round(src_start + duration, 3),
            "at": round(at, 3),
            "seconds": round(duration, 3),
        })
        cursor = at + duration
    if not placed:
        raise ValueError("La voz no cabe en la base")
    return {
        "pieces": len(placed),
        "vocal_seconds": round(vocal_s, 2),
        "base_seconds": round(base_s, 2),
        "placements": placed,
        "explanation": (
            f"La base dura {base_s:.0f} s y la voz {vocal_s:.0f} s. "
            f"Se cortan {len(placed)} trozos y se colocan en los golpes, sin estirar. "
            f"El primero entra a {placed[0]['at']:.2f} s y el último a {placed[-1]['at']:.2f} s."
        ),
    }


def make_loop(source: Path, out: Path, seconds: float, start_seconds: float = 0.0) -> dict:
    """Exporta un fragmento como pista nueva, desde el golpe si se pide."""
    if seconds <= 1:
        raise ValueError("El loop debe durar al menos 1 segundo")
    if start_seconds < 0:
        raise ValueError("El loop no puede empezar antes del audio")
    args = ["-i", str(source)]
    # -ss después de -i: el corte cae en el golpe, no en el keyframe de antes.
    if start_seconds > 0:
        args += ["-ss", f"{start_seconds:.3f}"]
    args += [
        "-t", f"{seconds:.3f}", "-c:a", "libmp3lame",
        "-b:a", "192k", "-f", "mp3", str(out),
    ]
    run_ffmpeg(args, out)
    return {
        "file_name": out.name,
        "seconds": round(seconds, 2),
        "start_seconds": round(start_seconds, 3),
    }


def crossfade(tracks: list[Path], out: Path, fade_seconds: float = 4.0) -> dict:
    """Funde varias pistas. El tempo solo se iguala si el ajuste es pequeño.

    Fuera de 0,8–1,25 la pista se deja a su tempo: estirarla más la deforma.
    Si el golpe de la primera no es fiable, no se estira ninguna.
    """
    if len(tracks) < 2:
        raise ValueError("Hacen falta al menos dos pistas para un crossfade")
    if not 0.5 <= fade_seconds <= 15:
        raise ValueError("El fundido debe estar entre 0,5 y 15 segundos")

    base_groove = detect_groove(tracks[0])
    base_ok = float(base_groove.get("confidence") or 0) >= MIN_GROOVE_CONFIDENCE
    matched: list[str] = []
    left: list[str] = []
    args: list[str] = []
    for track in tracks:
        args += ["-i", str(track)]
    filters: list[str] = []
    for index, track in enumerate(tracks):
        chain: list[str] = []
        if index > 0:
            if not base_ok:
                left.append(track.name)
            else:
                try:
                    groove = detect_groove(track)
                    ratio = float(base_groove["bpm"]) / float(groove["bpm"]) if groove.get("bpm") else 1.0
                    reliable = float(groove.get("confidence") or 0) >= MIN_GROOVE_CONFIDENCE
                    if reliable and MIN_TEMPO_RATIO <= ratio <= MAX_TEMPO_RATIO and abs(ratio - 1.0) > 0.005:
                        chain.append(_atempo_chain(ratio))
                        matched.append(track.name)
                    elif not reliable or ratio < MIN_TEMPO_RATIO or ratio > MAX_TEMPO_RATIO:
                        left.append(track.name)
                except ValueError:
                    left.append(track.name)
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
    if left:
        note = "Fundido listo. Estas pistas no se estiran, el ajuste de tempo sería grande: " + ", ".join(left)
    elif matched:
        note = "Fundido listo. El tempo se igualó al de la primera, sin cambiar el tono."
    else:
        note = "Fundido listo. El tempo no se tocó."
    return {
        "file_name": out.name,
        "tracks": len(tracks),
        "fade_seconds": fade_seconds,
        "matched": matched,
        "left": left,
        "note": note,
    }


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

    @staticmethod
    def arrange_vocals(
        base_track_path: str,
        vocal_track_path: str,
        output_path: str,
        plan: dict,
        base_volume: float = 0,
        vocal_volume: float = 0,
        normalize_lufs: bool = True,
        fade_s: float = 0.02,
    ) -> dict:
        """Coloca los trozos del plan sobre la base. No cambia su duración ni su tono."""
        base = Path(base_track_path)
        vocal = Path(vocal_track_path)
        out = Path(output_path)
        pieces = list(plan.get("placements") or [])
        if not pieces:
            raise ValueError("No hay trozos de voz que colocar")
        if shutil.which("ffmpeg") is None:
            raise RuntimeError("ffmpeg no está disponible en el PATH")

        filters: list[str] = [f"[0:a]volume={base_volume}dB[base]"]
        labels = ["[base]"]
        if len(pieces) == 1:
            sources = ["[1:a]"]
        else:
            split = "".join(f"[s{i}]" for i in range(len(pieces)))
            filters.append(f"[1:a]asplit={len(pieces)}{split}")
            sources = [f"[s{i}]" for i in range(len(pieces))]
        for index, piece in enumerate(pieces):
            duration = float(piece["seconds"])
            fade = min(float(fade_s), duration / 4)
            fade_out_at = max(0.0, duration - fade)
            delay_ms = max(0.0, float(piece["at"]) * 1000.0)
            label = f"[p{index}]"
            filters.append(
                f"{sources[index]}atrim=start={float(piece['source_start']):.3f}:end={float(piece['source_end']):.3f},"
                f"asetpts=PTS-STARTPTS,"
                f"afade=t=in:st=0:d={fade:.3f},afade=t=out:st={fade_out_at:.3f}:d={fade:.3f},"
                f"adelay=delays={delay_ms:.1f}:all=1,volume={vocal_volume}dB{label}"
            )
            labels.append(label)
        filters.append(
            f"{''.join(labels)}amix=inputs={len(labels)}:duration=first:dropout_transition=0:normalize=0[mezcla]"
        )

        def render(target: Path, extra_filter: str | None) -> None:
            chain = list(filters)
            master = "[mezcla]"
            if extra_filter:
                chain.append(f"{master}{extra_filter}[out]")
                master = "[out]"
            run_ffmpeg(
                ["-i", str(base), "-i", str(vocal),
                 "-filter_complex", ";".join(chain), "-map", master,
                 "-c:a", "libmp3lame", "-b:a", MP3_BITRATE, "-f", "mp3", str(target)],
                target,
            )

        used = f"arrange:{len(pieces)}"
        if normalize_lufs:
            probe = out.with_name(f"{out.stem}-probe.mp3")
            try:
                render(probe, None)
                measured = measure_loudness(probe)
                render(out, f"loudnorm={_loudnorm_args(measured, measured_flag=True)}")
            finally:
                probe.unlink(missing_ok=True)
        else:
            render(out, None)
        info = measure_loudness(out)
        logger.info(f"Arreglo listo: {out.name} trozos={len(pieces)} {info}")
        return {
            "output_path": str(out),
            "applied": False,
            "arranged": True,
            "pieces": len(pieces),
            "loudness": info,
            "filters": used,
        }
