"""Contradicciones explícitas, sin traducir ni reescribir el prompt."""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def rules() -> dict:
    return json.loads(Path(__file__).with_suffix(".json").read_text(encoding="utf-8"))


def validate_explicit_constraints(prompt, *, bpm=None, time_signature=None,
                                  instrumental=None, lyrics=None, marker="[instrumental]",
                                  external_voice=False):
    """Rechaza desacuerdos explícitos; la ausencia de mención no elige controles."""
    catalog = rules()
    # Exclusiones concretas como «no instrumental» no equivalen a pedir una
    # pista instrumental. Solo ocultarlas al detector;
    # el texto original que viaja al motor se conserva byte a byte.
    checked = prompt
    for pattern in catalog["ignored_patterns"]:
        checked = re.sub(pattern, "", checked, flags=re.IGNORECASE)
    tempos = {int(match.group(1)) for pattern in catalog["bpm_patterns"]
              for match in re.finditer(pattern, checked, re.IGNORECASE)}
    if len(tempos) > 1 or (bpm is not None and tempos and tempos != {bpm}):
        raise ValueError("El BPM escrito en el prompt contradice el control de tempo o contiene varios valores. Corrige el texto o el BPM antes de generar.")
    meters = {(match.group(1), match.group(2)) for pattern in catalog["meter_patterns"]
              for match in re.finditer(pattern, checked, re.IGNORECASE)}
    chosen = str(time_signature or "").strip()
    if len(meters) > 1 or (chosen and meters and any(
            numerator != chosen.split("/")[0] or ("/" in chosen and denominator != chosen.split("/")[1])
            for numerator, denominator in meters)):
        raise ValueError("El compás escrito en el prompt contradice el control de compás o contiene varios valores. Corrige el texto o el compás antes de generar.")
    no_voice = any(re.search(pattern, checked, re.IGNORECASE) for pattern in catalog["instrumental_patterns"])
    voice = any(re.search(pattern, checked, re.IGNORECASE) for pattern in catalog["vocal_patterns"])
    has_lyrics = bool((lyrics or "").strip()) and (lyrics or "").strip().lower() != marker.lower()
    if no_voice and (voice or external_voice or instrumental is False or has_lyrics):
        raise ValueError("El prompt pide sin voz pero también hay voz elegida o letra. Corrige el texto o el modo de voz antes de generar.")
    if not external_voice and instrumental is True and (voice or has_lyrics):
        raise ValueError("El modo instrumental contradice la voz o la letra solicitada. Corrige el texto o el modo de voz antes de generar.")
