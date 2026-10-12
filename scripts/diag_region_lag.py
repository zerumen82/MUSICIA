"""Diagnóstico: ¿el fallo de preservación fuera de la región es desfase de decodificador o pérdida real?

Compara el PCM del intermedio wav32 (salida del motor) con el original MP3
decodificado por ffmpeg, buscando el desfase (lag) que minimiza el error.
Si el error colapsa con un lag de pocos ms, el splice del motor SÍ reinsertó
la onda original y la diferencia es artefacto de decoders MP3 distintos.
"""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
intermediate = Path(sys.argv[2])
source = Path(sys.argv[3])
SR = 48000


def pcm(path):
    out = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-ac", "2", "-ar", str(SR),
                          "-f", "f32le", "-acodec", "pcm_f32le", "-"],
                         capture_output=True, check=True)
    return np.frombuffer(out.stdout, dtype="<f4").reshape(-1, 2).astype(np.float64)


actual, src = pcm(intermediate), pcm(source)
n = min(len(actual), len(src))
actual, src = actual[:n], src[:n]
# Fuera de la región 6–18 s con 0,1 s de crossfade excluidos: 0–5.9 s y 18.1–fin
mask = np.ones(n, dtype=bool)
mask[int(5.9 * SR):int(18.1 * SR)] = False
best = None
for lag_ms in range(-60, 61, 1):
    lag = int(lag_ms * SR / 1000)
    a = actual[max(lag, 0):n + min(lag, 0)]
    s = src[max(-lag, 0):n - max(lag, 0)]
    m = mask[max(lag, 0):n + min(lag, 0)]
    if m.sum() < SR:
        continue
    err = a[m] - s[m]
    rel = float(np.sqrt(np.mean(err ** 2)) / max(np.sqrt(np.mean(s[m] ** 2)), 1e-12))
    if best is None or rel < best["relative_rms"]:
        best = {"lag_ms": lag_ms, "relative_rms": rel, "max_absolute": float(np.max(np.abs(err)))}
zero_lag_err = actual[mask] - src[mask]
# Hipótesis ganancia: ¿el error colapsa con un escalar constante (normalización del motor)?
a_flat, s_flat = actual[mask].reshape(-1), src[mask].reshape(-1)
alpha = float(np.dot(a_flat, s_flat) / np.dot(s_flat, s_flat))
gain_err = a_flat - alpha * s_flat
gain_rel = float(np.sqrt(np.mean(gain_err ** 2)) / max(np.sqrt(np.mean(s_flat ** 2)), 1e-12))
print(json.dumps({
    "best_shift": best,
    "zero_lag": {"relative_rms": float(np.sqrt(np.mean(zero_lag_err ** 2)) / np.sqrt(np.mean(src[mask] ** 2))),
                 "max_absolute": float(np.max(np.abs(zero_lag_err)))},
    "optimal_gain": {"alpha": alpha, "relative_rms_after_gain": gain_rel},
    "verdict": ("GAIN_ONLY: el splice reinsertó la onda con normalización de ganancia del motor"
                if gain_rel < 0.008 and abs(alpha - 1.0) > 0.01 else
                "WAVEFORM_MATCH: sin ganancia, coincidencia directa"
                if best["relative_rms"] < 0.008 else
                "REAL_LOSS: ni con desfase ni con ganancia se recupera la conservación"),
}, indent=2, ensure_ascii=False))
