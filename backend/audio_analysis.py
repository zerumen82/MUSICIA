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

import numpy as np
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

# Cobertura de bombo (B8c, 2026-10-20): mide si hay un golpe de la banda
# 40-120 Hz en cada tiempo del compás pedido. El oído del usuario detectó
# trozos «sin batería» aunque el detector de pulso los diera por buenos:
# ese detector mira el pulso global, no el bombo a negras.
KICK_BAND_LOW_HZ = 40.0       # extremo grave de la banda del bombo
KICK_BAND_HIGH_HZ = 120.0     # extremo agudo de la banda del bombo
KICK_ANALYSIS_RATE = 48000    # Hz, para resolver la banda del bombo
KICK_FRAME_SAMPLES = 1024     # ~21,3 ms por trama espectral
KICK_HOP_SAMPLES = 512        # avance entre tramas (solape 50 %)
KICK_SMOOTH_FRAMES = 5        # media local ~100 ms para el flanco
KICK_ONSET_STD = 2.0          # flanco de subida sobre media + 2 desviaciones
KICK_MIN_GAP_MS = 120.0       # dos bombos seguidos más cerca no son dos
KICK_TOLERANCE_MS = 80.0      # ventana alrededor de cada tiempo del compás
KICK_PHASE_STEP_MS = 10       # paso del barrido de fase del compás


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

def _validate_octave_settings(settings) -> None:
    if (not math.isfinite(settings.groove_octave_score_ratio)
            or not 0 < settings.groove_octave_score_ratio <= 1
            or not math.isfinite(settings.groove_octave_lag_tolerance_frames)
            or settings.groove_octave_lag_tolerance_frames < 0):
        raise ValueError("Configuración de octava de groove inválida")


def _select_groove_peak(scores: list[tuple[int, float]], settings) -> tuple[int, float]:
    """Máximo local, con preferencia solo por sus octavas bien sustentadas.

    La resolución es una trama: un pico próximo al periodo/2 puede representar
    el pulso del compás. Un pico fuerte a cualquier otro periodo no es una
    octava. Todos los candidatos se comparan con el máximo inicial para no
    acumular pérdidas de evidencia al pasar por varias octavas.
    """
    if not scores:
        raise ValueError("Sin periodicidad suficiente para detectar el groove")
    _validate_octave_settings(settings)
    # El primer y el último lag son el borde de la ventana de búsqueda.
    # Una pendiente que se sale por ahí no es un pulso sustentado.
    peaks = [(lag, score) for index, (lag, score) in enumerate(scores)
             if 0 < index < len(scores) - 1
             and score >= scores[index - 1][1]
             and score > scores[index + 1][1]]
    if not peaks:
        raise ValueError("El groove es incierto: no hay un pico de período interior "
                         "en la ventana de búsqueda")
    anchor = max(peaks, key=lambda item: item[1])
    chosen = anchor
    octave_lag = anchor[0] / 2
    while octave_lag >= scores[0][0]:
        candidates = [peak for peak in peaks
                      if abs(peak[0] - octave_lag) <= settings.groove_octave_lag_tolerance_frames
                      and peak[1] >= anchor[1] * settings.groove_octave_score_ratio]
        if candidates:
            chosen = max(candidates, key=lambda item: item[1])
        octave_lag /= 2
    return chosen


def _score_supported_grooves(supported: list[tuple[float, float, float]], settings) -> float:
    """Elige el período cuyo golpe es más nítido entre los de evidencia cercana.

    Una textura un poco más periódica, con el golpe borroso, no sustituye al
    pulso. Un acento mucho menos periódico tampoco gana por tener el golpe
    más marcado. La regla de octava desempata y no usa el BPM pedido.
    """
    if not supported:
        raise ValueError("El groove es incierto: ningún período sostenido dentro del rango")
    _validate_octave_settings(settings)
    ratio = settings.groove_hit_preference_ratio
    if isinstance(ratio, bool) or not isinstance(ratio, (int, float)) or not math.isfinite(ratio) or ratio <= 1:
        raise ValueError("Configuración de preferencia de golpe inválida")
    reliable = [item for item in supported if item[2] >= settings.timeline_min_groove_confidence]
    pool = reliable or supported
    # El golpe solo cambia la elección entre períodos de evidencia cercana,
    # y solo si es claramente más nítido. Un acento con el pliegue un poco
    # mayor no tapa al pulso que ya concentra la evidencia.
    strongest = max(item[1] for item in pool)
    close = [item for item in pool if item[1] >= strongest * settings.groove_octave_score_ratio]
    ranked = [(period, evidence) for period, evidence, _confidence in close]
    chosen = _prefer_supported_octave(ranked, settings)
    chosen_fold = max(confidence for period, _evidence, confidence in close if period == chosen)
    clearer = [item for item in close if item[2] >= chosen_fold * ratio]
    if not clearer:
        return chosen
    return _prefer_supported_octave(
        [(period, evidence) for period, evidence, _confidence in clearer], settings)


def _prefer_supported_octave(periods: list[tuple[float, float]], settings) -> float:
    """Elige el período sostenido y, si su octava rápida también lo está, esa.

    `periods` son pares (tramas, peso) que ya sobrevivieron al refinado
    interior. El peso es la evidencia sostenida, ponderada por el golpe en
    la medición. No es el diente de una sola repetición, y cada octava se
    compara con el máximo inicial.
    """
    if not periods:
        raise ValueError("El groove es incierto: ningún período sostenido dentro del rango")
    _validate_octave_settings(settings)
    anchor = max(periods, key=lambda item: item[1])
    chosen = anchor
    # Mitades del ancla original. No se corta en la primera que falle
    # ni se recentra: si no, un /2 débil tapa un /4 que sí cumple.
    octave = anchor[0] / 2
    while octave >= 1:
        candidates = [item for item in periods
                      if abs(item[0] - octave) <= settings.groove_octave_lag_tolerance_frames
                      and item[1] >= anchor[1] * settings.groove_octave_score_ratio]
        if candidates:
            chosen = max(candidates, key=lambda item: item[1])
        octave /= 2
    return chosen[0]


def _reject_unprominent_period(best: float, floor: float, settings) -> None:
    """Rechaza un período interior que solo arruga la caída de la autocorrelación.

    El lag legal más rápido concentra evidencia cuando la envolvente es suave
    y no hay golpe. Un máximo local ahí debajo no es un tempo medible.
    """
    ratio = settings.groove_peak_evidence_ratio
    if (isinstance(ratio, bool) or not isinstance(ratio, (int, float))
            or not math.isfinite(ratio) or not 0 < ratio <= 1):
        raise ValueError("Configuración de evidencia de pico de groove inválida")
    if floor > 0 and best < floor * ratio:
        raise ValueError("El groove es incierto: el período interior no destaca "
                         "sobre la caída de la autocorrelación")


def _onset_flux(rms: list[float]) -> list[float]:
    """Subida de energía de una trama a la siguiente. El compás no es un ataque."""
    flux = [0.0]
    for previous, current in zip(rms, rms[1:]):
        flux.append(max(0.0, current - previous))
    return flux


def _onset_spectrum_power(series: list[float], fps: float, bpm: float) -> float:
    """Potencia de un solo período en el flujo. No elige tempo por sí sola."""
    if not series or not math.isfinite(bpm) or bpm <= 0 or not math.isfinite(fps) or fps <= 0:
        return 0.0
    omega = 2.0 * math.pi * (bpm / 60.0) / fps
    sine = cosine = 0.0
    for index, value in enumerate(series):
        sine += value * math.sin(omega * index)
        cosine += value * math.cos(omega * index)
    return sine * sine + cosine * cosine


def _prefer_onset_beat(rms: list[float], fps: float, period_frames: float,
                       supported: list[tuple[float, float, float]], settings) -> float:
    """Si el ancla es el compás, el golpe es el armónico cuyo ataque manda.

    Solo entran las mitades /2 y /4 que ya son períodos sostenidos, dentro de
    la tolerancia de trama de la octava. No consulta el BPM pedido. Si el
    flujo no destaca sobre el ancla, el ancla se queda.
    """
    ratio = settings.groove_onset_spectrum_ratio
    tolerance = settings.groove_octave_lag_tolerance_frames
    if (isinstance(ratio, bool) or not isinstance(ratio, (int, float)) or not math.isfinite(ratio) or ratio <= 1
            or isinstance(tolerance, bool) or not isinstance(tolerance, (int, float))
            or not math.isfinite(tolerance) or tolerance < 0
            or not math.isfinite(period_frames) or period_frames <= 0):
        raise ValueError("Configuración de octava de groove inválida")
    flux = _onset_flux(rms)
    anchor_bpm = 60.0 * fps / period_frames
    anchor_power = _onset_spectrum_power(flux, fps, anchor_bpm)
    best_period = period_frames
    best_power = anchor_power
    floor = anchor_power * ratio
    for period, _evidence, _confidence in supported:
        if not math.isfinite(period) or period <= 0 or period >= period_frames:
            continue
        subdivision = period_frames / period
        nearest = min((2, 4), key=lambda factor: abs(subdivision - factor))
        if abs(period - period_frames / nearest) > tolerance:
            continue
        power = _onset_spectrum_power(flux, fps, 60.0 * fps / period)
        if power > floor and power > best_power:
            best_power = power
            best_period = period
    return best_period


def _reject_flat_shoulder(best: float, shoulder: float, settings) -> None:
    """Rechaza un máximo que no destaca sobre el tempo de al lado.

    Una meseta tiene algún lag un poco más alto que sus vecinos. Estirar ese
    lag no lleva el audio al tempo pedido. Un hombro no positivo sí deja pasar
    el periodo: el pico está por encima de esa zona.
    """
    ratio = settings.groove_shoulder_ratio
    fraction = settings.groove_shoulder_period_fraction
    minimum = settings.groove_shoulder_min_frames
    if (isinstance(ratio, bool) or not isinstance(ratio, (int, float)) or not math.isfinite(ratio) or ratio <= 1
            or isinstance(fraction, bool) or not isinstance(fraction, (int, float))
            or not math.isfinite(fraction) or not 0 < fraction < 0.5
            or isinstance(minimum, bool) or not isinstance(minimum, (int, float))
            or not math.isfinite(minimum) or minimum <= 0):
        raise ValueError("Configuración de hombro de groove inválida")
    if shoulder > 0 and best < shoulder * ratio:
        raise ValueError("El groove es incierto: el período elegido no destaca "
                         "sobre los tempos vecinos")


def _multi_period_evidence(rms: list[float], period: float, periods: int, width: int) -> float:
    """Misma evidencia de varios períodos que el refinado, en un solo lag."""
    if periods < 1 or width <= 0 or width % 2 == 0:
        raise ValueError("Configuración de refinado de groove inválida")
    n = len(rms)
    half = width // 2
    cumulative = [0.0]
    for value in rms:
        cumulative.append(cumulative[-1] + value)
    smooth = [(cumulative[min(n, i + half + 1)] - cumulative[max(0, i - half)])
              / (min(n, i + half + 1) - max(0, i - half)) for i in range(n)]
    mean = sum(smooth) / n
    centered = [value - mean for value in smooth]
    denominator = sum(value * value for value in centered)
    if denominator <= 0:
        raise ValueError("No se ha detectado un tempo claro (sin periodicidad)")
    max_lag = math.ceil(period * periods) + 1
    correlations = [sum(centered[i] * centered[i + lag] for i in range(n - lag)) / denominator
                    for lag in range(max_lag + 1)]
    score = 0.0
    for multiple in range(1, periods + 1):
        lag = period * multiple
        index = int(lag)
        fraction = lag - index
        score += (correlations[index] * (1 - fraction)
                  + correlations[index + 1] * fraction) / multiple
    return score


def _refine_groove_period(rms: list[float], chosen_lag: int, settings) -> float:
    """Periodo refinado. Los tests y la medición pública solo necesitan las tramas."""
    return _refine_groove_detail(rms, chosen_lag, settings)[0]


def _refine_groove_detail(rms: list[float], chosen_lag: int, settings) -> tuple[float, float]:
    """Refina el pulso por su repetición a varios períodos, sin elegir otra octava.

    La energía tonal introduce dientes cercanos en la autocorrelación de una
    sola repetición. Suavizar y contrastar varios golpes permite estimar el
    período sostenido en vez del diente más fuerte de esa textura.
    """
    width, periods = settings.groove_smooth_frames, settings.groove_refine_periods
    radius, step = settings.groove_refine_radius_frames, settings.groove_refine_step_frames
    if (isinstance(width, bool) or not isinstance(width, int) or width <= 0 or width % 2 == 0
            or isinstance(periods, bool) or not isinstance(periods, int)
            or isinstance(settings.groove_refine_max_periods, bool)
            or not isinstance(settings.groove_refine_max_periods, int)
            or isinstance(settings.groove_refine_max_candidates, bool)
            or not isinstance(settings.groove_refine_max_candidates, int)
            or settings.groove_refine_max_candidates <= 0
            or not 2 <= periods <= settings.groove_refine_max_periods
            or isinstance(radius, bool) or not isinstance(radius, (int, float))
            or not math.isfinite(radius) or radius <= 0
            or isinstance(step, bool) or not isinstance(step, (int, float))
            or not math.isfinite(step) or step <= 0):
        raise ValueError("Configuración de refinado de groove inválida")
    # La vecindad nunca llega a otra octava, incluso con un override amplio.
    radius = min(radius, chosen_lag / 4)
    lo, hi = max(1.0, chosen_lag - radius), chosen_lag + radius
    candidates = math.ceil((hi - lo) / step) + 1
    if candidates > settings.groove_refine_max_candidates:
        raise ValueError("La resolución de groove excede el límite configurado de candidatos")
    n = len(rms)
    periods = min(periods, int((n - 2) / hi))
    if periods < 2:
        raise ValueError("Audio insuficiente para contrastar varios períodos del groove")
    cumulative = [0.0]
    for value in rms:
        cumulative.append(cumulative[-1] + value)
    half = width // 2
    smooth = [(cumulative[min(n, i + half + 1)] - cumulative[max(0, i - half)])
              / (min(n, i + half + 1) - max(0, i - half)) for i in range(n)]
    mean = sum(smooth) / n
    centered = [value - mean for value in smooth]
    denominator = sum(value * value for value in centered)
    if denominator <= 0:
        raise ValueError("No se ha detectado un tempo claro (sin periodicidad)")
    max_lag = math.ceil(hi * periods) + 1
    correlations = [sum(centered[i] * centered[i + lag] for i in range(n - lag)) / denominator
                    for lag in range(max_lag + 1)]

    def evidence(period):
        score = 0.0
        for multiple in range(1, periods + 1):
            lag = period * multiple
            index = int(lag)
            fraction = lag - index
            score += (correlations[index] * (1 - fraction)
                      + correlations[index + 1] * fraction) / multiple
        return score

    grid = [min(hi, lo + index * step) for index in range(candidates)]
    peak_index = max(range(len(grid)), key=lambda index: evidence(grid[index]))
    if peak_index == 0 or peak_index == len(grid) - 1:
        raise ValueError("El groove es incierto: el máximo del refinado está en el borde de la vecindad, "
                         "sin un pico de período sustentado")
    period = grid[peak_index]
    return period, evidence(period)


def _fold_groove(onset: list[float], period_frames: float, fps: float) -> tuple[float, float]:
    """Fase y fuerza sobre el período fraccional realmente estimado."""
    count = max(1, round(period_frames))
    bins, visits = [0.0] * count, [0.0] * count
    for i, value in enumerate(onset):
        position = (i % period_frames) / period_frames * count
        floor = math.floor(position)
        left = floor % count
        fraction = position - floor
        right = (left + 1) % count
        bins[left] += value * (1 - fraction)
        bins[right] += value * fraction
        visits[left] += 1 - fraction
        visits[right] += fraction
    bins = [value / visits[index] if visits[index] else 0.0 for index, value in enumerate(bins)]
    peak = max(range(count), key=lambda index: bins[index])
    phase = peak / count * period_frames
    if phase > period_frames / 2:
        phase -= period_frames
    strength = (max(bins) - sum(bins) / count) / (max(bins) or 1)
    return phase / fps * 1000, max(0.0, min(1.0, strength))


def detect_groove(path: Path, *, include_periods: bool = False) -> dict:
    """Tempo + fase del golpe: lo que hace que dos pistas encajen.

    Devuelve {bpm, period_ms, phase_ms, confidence}. `phase_ms` es el instante
    del primer golpe respecto al inicio del fichero: es lo que hay que
    desplazar una pista para que su bateria caiga donde cae la otra.
    """
    if not path.exists():
        raise FileNotFoundError(f"No existe el audio: {path}")
    with path.open("rb") as stream:
        audio = AudioSegment.from_file(stream, format=path.suffix.lstrip("."))
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

    mean = sum(rms) / len(rms)
    onset = [max(0.0, x - mean) for x in rms]

    from config import get_settings

    # Cada pico interior se contrasta en varios períodos. Un diente rápido
    # cuyo refinado cae en el borde no tapa un pulso sostenido más lento.
    # El estimado grueso solo sirve para saber que hay periodicidad: su
    # ventana alrededor de un subarmónico (66 cuando el pulso es 199) no
    # puede dejar fuera un BPM legal.
    config = get_settings().remix
    limits = config.parameters["bpm"]
    scores = _autocorr_scores(onset, fps, limits["min"], limits["max"])
    peaks = [(lag, score) for index, (lag, score) in enumerate(scores)
             if 0 < index < len(scores) - 1
             and score >= scores[index - 1][1]
             and score > scores[index + 1][1]]
    if not peaks:
        raise ValueError("El groove es incierto: no hay un pico de período interior "
                         "en la ventana de búsqueda")
    supported: list[tuple[float, float]] = []
    rejected: list[ValueError] = []
    for lag, _score in peaks:
        try:
            period, evidence = _refine_groove_detail(rms, lag, config)
        except ValueError as exc:
            text = str(exc)
            if text.startswith("Configuración") or "excede el límite" in text:
                raise
            rejected.append(exc)
            continue
        measured = 60.0 * fps / period
        if limits["min"] <= measured <= limits["max"]:
            _phase, confidence = _fold_groove(onset, period, fps)
            supported.append((period, evidence, confidence))
    if not supported:
        if rejected:
            raise rejected[-1]
        raise ValueError("El groove es incierto: ningún período sostenido dentro del rango")
    # El lag legal más rápido no es un candidato: en una envolvente suave
    # su evidencia es la caída, y un pliegue lento no debe heredarla.
    fastest = max(1, math.floor(fps * 60.0 / limits["max"]))
    best_period = max(supported, key=lambda item: item[1])[0]
    multiples = min(config.groove_refine_periods,
                    int((len(rms) - 2) / max(fastest, best_period)))
    if multiples >= 2:
        floor = _multi_period_evidence(rms, fastest, multiples, config.groove_smooth_frames)
        best = _multi_period_evidence(rms, best_period, multiples, config.groove_smooth_frames)
        _reject_unprominent_period(best, floor, config)
    # Una octava rápida con el golpe ya por debajo del mínimo no sustituye
    # al pulso que sí se puede usar. Si ninguna llega, se conserva la medición
    # débil para que el rechazo diga el BPM y la confianza reales.
    period_frames = _score_supported_grooves(supported, config)
    period_frames = _prefer_onset_beat(rms, fps, period_frames, supported, config)
    shoulder_offset = max(config.groove_shoulder_min_frames,
                          period_frames * config.groove_shoulder_period_fraction)
    shoulder_room = period_frames + shoulder_offset
    shoulder_multiples = min(config.groove_refine_periods, int((len(rms) - 2) / shoulder_room))
    if shoulder_multiples >= 2 and shoulder_offset < period_frames:
        chosen_evidence = _multi_period_evidence(
            rms, period_frames, shoulder_multiples, config.groove_smooth_frames)
        neighbors = (
            _multi_period_evidence(rms, period_frames - shoulder_offset, shoulder_multiples,
                                   config.groove_smooth_frames),
            _multi_period_evidence(rms, period_frames + shoulder_offset, shoulder_multiples,
                                   config.groove_smooth_frames),
        )
        _reject_flat_shoulder(chosen_evidence, max(neighbors), config)
    bpm = 60.0 * fps / period_frames
    phase_ms, strength = _fold_groove(onset, period_frames, fps)
    if strength < config.timeline_min_groove_confidence:
        raise ValueError(
            f"El groove es incierto: confianza {strength:.3f} por debajo del mínimo "
            f"{config.timeline_min_groove_confidence} (BPM medido: {bpm:.2f})")
    result = {
        "bpm": round(float(bpm), 2),
        "period_ms": round(60000.0 / float(bpm), 1),
        "phase_ms": round(phase_ms, 1),
        "confidence": round(strength, 3),
        "duration_seconds": round(len(audio) / 1000.0, 2),
    }
    if include_periods:
        result["periods"] = [{"bpm": round(60.0 * fps / period, 2),
                              "evidence": round(float(evidence), 4),
                              "confidence": round(float(confidence), 3)}
                             for period, evidence, confidence in supported]
    return result


def _autocorr_scores(onset: list[float], fps: float, bpm_min: float, bpm_max: float) -> list[tuple[int, float]]:
    """Autocorrelación normalizada en el rango de BPM configurado (lag, score)."""
    if (not math.isfinite(bpm_min) or not math.isfinite(bpm_max)
            or bpm_min <= 0 or bpm_max < bpm_min):
        raise ValueError("El rango de BPM del groove no es válido")
    fastest = math.floor(fps * 60.0 / bpm_max)
    slowest = math.ceil(fps * 60.0 / bpm_min)
    # Un lag de margen deja que el BPM justo en el límite sea un pico interior.
    # El límite medido se aplica después; el margen no amplía el rango legal.
    # range() no incluye hi. El +2 deja dentro el lag de margen lento.
    lo, hi = max(1, fastest - 1), slowest + 2
    n = len(onset)
    denom = sum(x * x for x in onset) or 1.0
    scores: list[tuple[int, float]] = []
    for lag in range(lo, min(hi, n - 1)):
        acc = 0.0
        for i in range(n - lag):
            acc += onset[i] * onset[i + lag]
        scores.append((lag, acc / denom))
    return scores


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


def _kick_envelope(samples: np.ndarray, rate: int) -> tuple[list[float], float]:
    """Energía de la banda del bombo (40-120 Hz) por trama, FFT con hamming."""
    n = KICK_FRAME_SAMPLES
    if len(samples) < n:
        return [], float(rate) / KICK_HOP_SAMPLES
    window = np.hamming(n)
    freqs = np.fft.rfftfreq(n, 1.0 / rate)
    band = (freqs >= KICK_BAND_LOW_HZ) & (freqs < KICK_BAND_HIGH_HZ)
    values = []
    for start in range(0, len(samples) - n + 1, KICK_HOP_SAMPLES):
        spectrum = np.abs(np.fft.rfft(samples[start:start + n] * window)) ** 2
        values.append(float(spectrum[band].sum()))
    return values, float(rate) / KICK_HOP_SAMPLES


def _kick_onsets(envelope: list[float], fps: float, min_gap_ms: float) -> np.ndarray:
    """Flancos de subida claros de la envolvente del bombo (índices de trama)."""
    if len(envelope) < KICK_SMOOTH_FRAMES + 3:
        return np.array([])
    flux = np.maximum(np.diff(envelope, prepend=envelope[0]), 0.0)
    threshold = float(np.mean(flux) + KICK_ONSET_STD * np.std(flux))
    peaks: list[int] = []
    for index in range(2, len(flux) - 2):
        if flux[index] > threshold and flux[index] >= flux[index - 1] and flux[index] > flux[index + 1]:
            if not peaks or (index - peaks[-1]) * 1000.0 / fps >= min_gap_ms:
                peaks.append(index)
    return np.array(peaks)


def _kick_coverage_phase(onsets_s: np.ndarray, bpm: float, duration: float,
                         tolerance_ms: float) -> tuple[float, float, np.ndarray]:
    """Fracción de tiempos del compás pedido con un golpe cerca (±tolerancia).

    La fase del compás se barre para no penalizar un bombo que cae en el
    tiempo pero desplazado unos milisegundos.
    """
    period = 60.0 / bpm
    best = (0.0, 0.0, np.array([]))
    for phase_ms in range(0, int(period * 1000), KICK_PHASE_STEP_MS):
        beats = np.arange(phase_ms / 1000.0, duration, period)
        if len(beats) == 0:
            continue
        hits = 0
        used: set[int] = set()
        for beat in beats:
            candidates = np.where(np.abs(onsets_s - beat) * 1000.0 <= tolerance_ms)[0]
            free = [int(candidate) for candidate in candidates if int(candidate) not in used]
            if free:
                hits += 1
                used.add(free[0])
        coverage = hits / len(beats)
        if coverage > best[0]:
            best = (coverage, phase_ms / 1000.0, beats)
    return best


def kick_coverage(path: Path, *, bpm: float, tolerance_ms: float = KICK_TOLERANCE_MS,
                  min_gap_ms: float = KICK_MIN_GAP_MS) -> dict:
    """Cobertura de bombo: ¿hay un golpe en cada tiempo del compás pedido?

    Devuelve {coverage (0-1), kicks, beats, phase_s, bpm, duration_seconds,
    tolerance_ms}. `coverage` es la fracción de tiempos del compás que tiene
    un golpe de la banda 40-120 Hz dentro de `tolerance_ms`. Un trozo sin
    batería queda cerca de 0 aunque el detector de pulso lo dé por bueno.
    """
    if not path.exists():
        raise FileNotFoundError(f"No existe el audio: {path}")
    if bpm is None or not math.isfinite(bpm) or bpm <= 0:
        raise ValueError("El BPM pedido debe ser un número finito y positivo")
    with path.open("rb") as stream:
        audio = AudioSegment.from_file(stream, format=path.suffix.lstrip("."))
    if len(audio) < 1000:
        raise ValueError("Audio demasiado corto para medir la cobertura de bombo")
    mono = audio.set_channels(1).set_frame_rate(KICK_ANALYSIS_RATE).set_sample_width(2)
    samples = np.array(mono.get_array_of_samples(), dtype=np.float64) / float(1 << 15)
    duration = len(samples) / KICK_ANALYSIS_RATE
    envelope, fps = _kick_envelope(samples, KICK_ANALYSIS_RATE)
    onsets = _kick_onsets(envelope, fps, min_gap_ms)
    onsets_s = onsets / fps
    coverage, phase_s, beats = _kick_coverage_phase(onsets_s, bpm, duration, tolerance_ms)
    return {
        "coverage": round(float(coverage), 3),
        "kicks": int(len(onsets_s)),
        "beats": int(len(beats)),
        "phase_s": round(float(phase_s), 3),
        "bpm": round(float(bpm), 2),
        "duration_seconds": round(float(duration), 2),
        "tolerance_ms": round(float(tolerance_ms), 1),
    }
