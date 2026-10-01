"""Post-proceso de audio real sobre ficheros MP3 con pydub.

Nada simulado: se abre el fichero real, se aplica la transformación y se
exporta un MP3 nuevo. Un parámetro fuera de rango lanza ValueError.
"""

from __future__ import annotations

from pathlib import Path

from pydub import AudioSegment

MIN_GAIN_DB = -24.0
MAX_GAIN_DB = 24.0
MIN_FADE_MS = 0
MAX_FADE_MS = 10000
MIN_DURATION_S = 1.0


def process_audio(
    source: Path,
    output: Path,
    gain_db: float = 0.0,
    fade_in_ms: int = 0,
    fade_out_ms: int = 0,
    trim_start_s: float = 0.0,
    trim_end_s: float | None = None,
) -> float:
    """Aplica ganancia, fades y recorte; devuelve la duración final en ms.

    - ``gain_db``: -24 a +24 dB.
    - ``fade_in_ms`` / ``fade_out_ms``: 0 a 10000 ms.
    - ``trim_start_s``: segundo de inicio (>= 0).
    - ``trim_end_s``: segundo de fin (None = hasta el final).
    """
    if not MIN_GAIN_DB <= gain_db <= MAX_GAIN_DB:
        raise ValueError(f"gain_db debe estar entre {MIN_GAIN_DB} y {MAX_GAIN_DB}")
    if not MIN_FADE_MS <= fade_in_ms <= MAX_FADE_MS:
        raise ValueError(f"fade_in_ms debe estar entre 0 y {MAX_FADE_MS}")
    if not MIN_FADE_MS <= fade_out_ms <= MAX_FADE_MS:
        raise ValueError(f"fade_out_ms debe estar entre 0 y {MAX_FADE_MS}")

    if not source.exists():
        raise FileNotFoundError(f"No existe el audio de origen: {source}")

    audio = AudioSegment.from_file(source)

    start_ms = max(0, int(trim_start_s * 1000))
    if start_ms >= len(audio):
        raise ValueError(
            f"trim_start_s ({trim_start_s}) supera la duración del audio ({len(audio) / 1000:.1f}s)"
        )
    end_ms = len(audio) if trim_end_s is None else int(trim_end_s * 1000)
    if end_ms <= start_ms:
        recorte = f"{trim_start_s}s a {trim_end_s}s"
        raise ValueError(f"Recorte vacío ({recorte}): el fin debe ser posterior al inicio")
    end_ms = min(end_ms, len(audio))

    audio = audio[start_ms:end_ms]

    if fade_in_ms > 0:
        audio = audio.fade_in(int(fade_in_ms))
    if fade_out_ms > 0:
        audio = audio.fade_out(int(fade_out_ms))
    if gain_db != 0.0:
        audio = audio + gain_db

    output.parent.mkdir(parents=True, exist_ok=True)
    audio.export(output, format="mp3")
    return len(audio)
