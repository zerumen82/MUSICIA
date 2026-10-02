"""Análisis DSP ligero de audio (Python puro + pydub, sin numpy).

Calcula features reales de un fichero de audio y propone una hipótesis
de contenido (música / voz / música+voz) con heurísticas explícitas.
La UI debe mostrar la hipótesis y preguntar al usuario: nunca se asume.

Features:
- duración (s)
- loudness medio (dBFS) y dinámica (desviación típica del RMS por trama)
- ZCR: tasa de cruces por cero (voz con sibilancias vs música densa)
- bass_ratio: energía relativa de graves (<250 Hz) frente al total
- bpm: estimado por autocorrelación de la envolvente de energía (60-180)

Heurística de hipótesis (explicada en la respuesta para que el usuario juzgue):
- voz: ZCR alto + graves suaves + dinámica de habla (pausas frecuentes)
- música: graves marcados + BPM estable + dinámica continua
- mixta: entre medias
"""

from __future__ import annotations

import math
from pathlib import Path

from pydub import AudioSegment

# Parámetros de análisis (constantes explícitas, nada mágico oculto)
ANALYSIS_RATE = 8000          # Hz, suficiente para features rítmicas/espectrales
FRAME_MS = 40                 # trama de análisis
BASS_CUTOFF_HZ = 250.0        # frontera grave/agudos
SILENCE_THRESHOLD_DB = -45.0  # umbral de trama "en silencio"
BPM_MIN, BPM_MAX = 60, 180
ZCR_VOICE = 0.12              # ZCR medio por muestra por encima de esto sugiere voz
BASS_MUSIC = 0.55             # ratio de graves por encima de esto sugiere música
FLATNESS_MUSIC = 0.35         # variabilidad de RMS baja => pista continua (música)


def _bass_ratio(samples: list[int], sample_rate: int) -> float:
    """Energía de graves < BASS_CUTOFF_HZ vía diferencia (low-pass por recurrencia simple)."""
    # Filtro pasa-bajos IIR de un polo, suficiente para separar graves de agudos.
    rc = 1.0 / (2.0 * math.pi * BASS_CUTOFF_HZ)
    dt = 1.0 / sample_rate
    alpha = dt / (rc + dt)
    prev = 0.0
    bass_energy = 0.0
    total_energy = 0.0
    for s in samples:
        prev += alpha * (s - prev)
        bass_energy += prev * prev
        total_energy += s * s
    if total_energy <= 0:
        return 0.0
    return bass_energy / total_energy


def _estimate_bpm(envelope_rms: list[float], frames_per_second: float) -> int | None:
    """BPM por autocorrelación de la envolvente de energía (60-180 BPM)."""
    n = len(envelope_rms)
    if n < frames_per_second * 8:  # al menos 8 s de audio para estimar con sentido
        return None
    mean = sum(envelope_rms) / n
    if mean <= 0:
        return None
    # Quitar la media (componente DC) para autocorrelación limpia
    centered = [x - mean for x in envelope_rms]
    denom = sum(x * x for x in centered)
    if denom <= 0:
        return None

    best_lag, best_score = None, 0.0
    min_lag = int(frames_per_second * 60 / BPM_MAX)
    max_lag = int(frames_per_second * 60 / BPM_MIN)
    for lag in range(min_lag, max_lag + 1):
        acc = 0.0
        for i in range(n - lag):
            acc += centered[i] * centered[i + lag]
        score = acc / denom
        if score > best_score:
            best_score = score
            best_lag = lag
    if best_lag is None or best_score < 0.05:  # sin periodicidad clara
        return None
    return int(round(60.0 * frames_per_second / best_lag))


# Trama fina solo para el groove: a 40 ms el tempo se cuantiza demasiado
# (~4 % de error) y la alineación arrastra ese error a la mezcla.
GROOVE_FRAME_MS = 10


def detect_groove(path: Path) -> dict:
    """Tempo + fase del golpe: lo que hace que dos pistas encajen.

    Devuelve {bpm, period_ms, phase_ms, confidence}. `phase_ms` es el instante
    del primer golpe respecto al inicio del fichero: es lo que hay que
    desplazar una pista para que su bateria caiga donde cae la otra.
    """
    if not path.exists():
        raise FileNotFoundError(f"No existe el audio: {path}")
    audio = AudioSegment.from_file(path)
    if len(audio) < GROOVE_FRAME_MS * 8 * 20:  # menos de ~1.6 s no sirve
        raise ValueError("Audio demasiado corto para detectar el groove")

    mono = audio.set_channels(1).set_frame_rate(ANALYSIS_RATE).set_sample_width(2)
    samples = list(mono.get_array_of_samples())
    frame_len = int(ANALYSIS_RATE * GROOVE_FRAME_MS / 1000)
    fps = 1000.0 / GROOVE_FRAME_MS

    rms: list[float] = []
    for start in range(0, len(samples) - frame_len + 1, frame_len):
        frame = samples[start:start + frame_len]
        rms.append(math.sqrt(sum(x * x for x in frame) / frame_len))
    if len(rms) < fps * 8:
        raise ValueError("Audio demasiado corto para detectar el groove")

    bpm = _estimate_bpm(rms, fps)
    if not bpm:
        raise ValueError("No se ha detectado un tempo claro (sin periodicidad)")
    period_frames = fps * 60.0 / bpm

    # Fase: se pliega la envolvente de energía sobre el periodo del tempo y se
    # busca el máximo -> ese frame es el golpe.
    mean = sum(rms) / len(rms)
    onset = [max(0.0, x - mean) for x in rms]
    period_int = max(1, int(round(period_frames)))
    bins: list[float] = [0.0] * period_int
    for i, value in enumerate(onset):
        bins[i % period_int] += value
    peak = max(range(len(bins)), key=lambda i: bins[i])
    phase_frames = peak
    if phase_frames > period_int / 2:  # cerca de 0: mejor al inicio
        phase_frames -= period_int

    # Refinado del tempo: interpolación parabólica sobre el máximo de la
    # autocorrelación da un BPM decimal mucho más fiel que el lag entero.
    bpm = _refine_bpm(onset, fps, bpm) or bpm

    strength = (max(bins) - sum(bins) / len(bins)) / (max(bins) or 1)
    return {
        "bpm": round(float(bpm), 2),
        "period_ms": round(60000.0 / float(bpm), 1),
        "phase_ms": round(phase_frames / fps * 1000.0, 1),
        "confidence": round(max(0.0, min(1.0, strength)), 3),
    }


def _refine_bpm(onset: list[float], fps: float, bpm_guess: int) -> float | None:
    """BPM decimal por interpolación parabólica del pico de autocorrelación."""
    period = fps * 60.0 / bpm_guess
    lo, hi = max(1, int(period * 0.85)), int(period * 1.18) + 1
    scores: list[tuple[int, float]] = []
    n = len(onset)
    denom = sum(x * x for x in onset) or 1.0
    for lag in range(lo, min(hi, n - 1)):
        acc = 0.0
        for i in range(n - lag):
            acc += onset[i] * onset[i + lag]
        scores.append((lag, acc / denom))
    if not scores:
        return None
    peak_index = max(range(len(scores)), key=lambda i: scores[i][1])
    y0 = scores[peak_index - 1][1] if peak_index > 0 else scores[peak_index][1]
    y1 = scores[peak_index][1]
    y2 = scores[peak_index + 1][1] if peak_index + 1 < len(scores) else y1
    denominator = y0 - 2 * y1 + y2
    delta = 0.5 * (y0 - y2) / denominator if denominator != 0 else 0.0
    delta = max(-1.0, min(1.0, delta))
    refined_lag = scores[peak_index][0] + delta
    return 60.0 * fps / refined_lag


def analyze_audio(path: Path) -> dict:
    """Analiza un audio real y devuelve features + hipótesis explicada.

    Lanza FileNotFoundError si no existe y ValueError si está vacío/corrupto.
    """
    if not path.exists():
        raise FileNotFoundError(f"No existe el audio: {path}")

    audio = AudioSegment.from_file(path)
    if len(audio) < 1000:  # < 1 s
        raise ValueError("El audio es demasiado corto para analizarlo (mínimo 1 segundo)")

    mono = audio.set_channels(1).set_frame_rate(ANALYSIS_RATE).set_sample_width(2)
    samples = list(mono.get_array_of_samples())
    sr = ANALYSIS_RATE
    frame_len = int(sr * FRAME_MS / 1000)
    fps = 1000.0 / FRAME_MS

    # RMS por trama + ZCR global
    rms_frames: list[float] = []
    zcr_total, zcr_count = 0, 0
    for start in range(0, len(samples) - frame_len + 1, frame_len):
        frame = samples[start:start + frame_len]
        rms = math.sqrt(sum(x * x for x in frame) / frame_len)
        rms_frames.append(rms)
        crossings = sum(
            1 for i in range(1, frame_len) if (frame[i - 1] < 0) != (frame[i] < 0)
        )
        zcr_total += crossings
        zcr_count += 1
    zcr = zcr_total / max(zcr_count, 1) / frame_len  # por muestra

    # Loudness en dBFS y dinámica (variabilidad del RMS en dB)
    full_scale = (1 << 15)
    rms_db_frames = [
        20 * math.log10(r / full_scale) if r > 0 else SILENCE_THRESHOLD_DB - 10
        for r in rms_frames
    ]
    mean_db = sum(rms_db_frames) / len(rms_db_frames)
    var_db = sum((d - mean_db) ** 2 for d in rms_db_frames) / len(rms_db_frames)
    std_db = math.sqrt(var_db)

    # Fracción de tramas en silencio (pausas => habla)
    silence_ratio = sum(
        1 for d in rms_db_frames if d < SILENCE_THRESHOLD_DB
    ) / len(rms_db_frames)

    bass = _bass_ratio(samples, sr)
    bpm = _estimate_bpm(rms_frames, fps)

    # ---- Hipótesis con heurística explícita ----
    signals = []
    if zcr >= ZCR_VOICE:
        signals.append("voz")
    if bass >= BASS_MUSIC:
        signals.append("música")
    if std_db >= 9.0:
        signals.append("dinámica amplia (habla)")
    if silence_ratio >= 0.15:
        signals.append("pausas frecuentes (habla)")
    if bpm is not None:
        signals.append(f"pulso rítmico ~{bpm} BPM")

    score_voice = (zcr >= ZCR_VOICE) + (silence_ratio >= 0.15) + (std_db >= 9.0)
    score_music = (bass >= BASS_MUSIC) + (bpm is not None) + (std_db < 9.0)

    if score_music >= 2 and score_voice == 0:
        kind, confidence = "música", "alta"
    elif score_voice >= 2 and score_music <= 1:
        kind, confidence = "voz", "media-alta"
    elif score_music >= 1 and score_voice >= 1:
        kind, confidence = "música + voz", "media"
    elif bpm is not None and bass >= 0.35:
        kind, confidence = "música", "media"
    else:
        kind, confidence = "sin clasificar clara", "baja"

    return {
        "duration_seconds": round(len(audio) / 1000.0, 2),
        "channels": audio.channels,
        "sample_rate": audio.frame_rate,
        "mean_loudness_dbfs": round(mean_db, 1),
        "dynamics_std_db": round(std_db, 1),
        "silence_ratio": round(silence_ratio, 3),
        "zcr": round(zcr, 4),
        "bass_ratio": round(bass, 3),
        "bpm": bpm,
        "hypothesis": {
            "kind": kind,
            "confidence": confidence,
            "signals": signals,
            "note": (
                "Hipótesis automática basada en espectro y dinámica. "
                "Confírmala o corrígela tú: decides qué hacer con este audio."
            ),
        },
    }
