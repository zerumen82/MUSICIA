"""Secuencia de pasos del remix: reparto en la línea de tiempo y contrato de cada paso.

Una secuencia divide la canción en tramos y vuelve a hacer **uno por paso**, en
orden. El orden lo pone la línea de tiempo, no el prompt: el motor se salta el
LM en `cover` y `repaint`, así que un texto con ocho instrucciones no es un
programa (ver [R20] en spec/02).
"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

# Focos posibles de un paso. `todo` rehace el tramo entero; el resto son para
# la fase siguiente (separar la pista concreta del tramo antes de rehacerla).
STEP_FOCUSES = ("todo", "vocals", "drums", "bass", "other")

# Focos que el backend ejecuta hoy. Los demás se rechazan: un selector que no
# hace nada sería un autoengaño.
IMPLEMENTED_FOCUSES = ("todo",)

# De dónde sale el material de un trabajo. Sin stems del usuario, el audio se
# separa de una canción terminada: eso es un bootleg, no un remix oficial.
MATERIAL_ORIGIN_MIX = "separado_de_mezcla"
MATERIAL_ORIGIN_STEMS = "stems_del_usuario"


def step_seed(requested: int | None, position: int, seed_max: int) -> int | None:
    """Semilla de cada paso: la pedida para el primero y derivadas para el resto.

    Nunca se sale del máximo configurado; sin semilla pedida, cada paso se
    sortea por su cuenta (el motor no repite muestra).
    """
    if (isinstance(requested, bool) or not isinstance(requested, int) or requested < 0
            or isinstance(seed_max, bool) or not isinstance(seed_max, int) or seed_max < 0):
        return None
    return (requested + position) % (seed_max + 1)


def material_origin(request) -> str:
    """Origen declarado del material: stems del usuario o mezcla separada."""
    stems = getattr(request, "stems", None)
    return MATERIAL_ORIGIN_STEMS if stems else MATERIAL_ORIGIN_MIX


class SequenceStep(BaseModel):
    """Un paso de la secuencia: qué tramo se rehace y con qué texto."""

    index: int = Field(ge=0)
    enabled: bool = True
    focus: str = "todo"
    prompt: str = ""

    model_config = ConfigDict(extra="forbid")


def active_steps(steps: list[SequenceStep]) -> list[SequenceStep]:
    """Pasos encendidos, en orden."""
    return [step for step in sorted(steps, key=lambda item: item.index) if step.enabled]


def validate_steps(steps: list[SequenceStep] | None, config) -> list[SequenceStep]:
    """Valida la lista de pasos y devuelve los encendidos."""
    if not steps:
        raise ValueError("La secuencia necesita al menos un paso")
    if len(steps) > config.sequence_max_steps:
        raise ValueError(f"La secuencia admite hasta {config.sequence_max_steps} pasos")
    indexes = sorted(step.index for step in steps)
    if indexes != list(range(len(steps))):
        raise ValueError("Los pasos deben ir numerados desde 0, sin repetir ni saltar números")
    active = active_steps(steps)
    if not active:
        raise ValueError("Enciende al menos un paso de la secuencia")
    for step in active:
        if not (step.prompt or "").strip():
            raise ValueError(f"El paso {step.index + 1} necesita su texto: sin él no hay nada que rehacer")
        if step.focus not in STEP_FOCUSES:
            raise ValueError(f"El paso {step.index + 1} tiene un foco desconocido: {step.focus}")
        if step.focus not in IMPLEMENTED_FOCUSES:
            raise ValueError(
                f"El foco «{step.focus}» del paso {step.index + 1} todavía no está implementado: "
                "ahora cada paso rehace el tramo entero.")
    return active


def bars_per_step(duration: float, bpm: float, count: int, beats_per_bar: int,
                  config) -> int:
    """Compases por paso. Sin tempo fiable o sin compases suficientes, no hay reparto."""
    if not bpm or bpm <= 0:
        raise ValueError("No hay un BPM fiable para repartir la secuencia en compases: "
                         "indica el BPM original revisado")
    bar_seconds = beats_per_bar * 60.0 / bpm
    bars = int(duration // bar_seconds)
    if bars < count:
        raise ValueError(f"La canción no tiene compases suficientes para {count} pasos: "
                         "usa menos pasos o una canción más larga")
    per_step = bars // count
    if per_step < config.sequence_min_bars_per_step:
        raise ValueError("Los pasos saldrían más cortos que un compás: usa menos pasos")
    return per_step


def plan_segments(duration: float, bpm: float, steps: list[SequenceStep],
                  config, beats_per_bar: int) -> list[dict]:
    """Reparte la canción en un tramo por paso, en compases completos.

    Sin tempo fiable no se reparte: cortar a mitad de golpe destrozaría el
    groove, así que el llamante avisa y el usuario da el BPM revisado.
    """
    count = len(steps)
    per_step = bars_per_step(duration, bpm, count, beats_per_bar, config)
    bar_seconds = beats_per_bar * 60.0 / bpm
    segments: list[dict] = []
    for position, step in enumerate(steps):
        start = round(position * per_step * bar_seconds, 3)
        end = (round(duration, 3) if position == count - 1
               else round((position + 1) * per_step * bar_seconds, 3))
        segments.append({
            "index": step.index,
            "enabled": step.enabled,
            "focus": step.focus,
            "prompt": step.prompt,
            "start": start,
            "end": end,
            "bars": per_step,
            "bar_aligned": True,
        })
    return segments


def sequence_timeline(duration: float, bpm: float, steps: list[SequenceStep],
                      config, beats_per_bar: int, bpm_origin: str = "measurement") -> dict:
    """La línea de tiempo de una secuencia: los tramos y cómo se reparten."""
    segments = plan_segments(duration, bpm, steps, config, beats_per_bar)
    return {
        "source_duration_seconds": duration,
        "natural_duration_seconds": duration,
        "target_duration_seconds": duration,
        "tempo_ratio": 1.0,
        "source_bpm": bpm,
        "source_bpm_origin": bpm_origin,
        "bpm_measured": bpm,
        "bpm_confidence": None,
        "target_bpm": None,
        "repeat_start": None,
        "repeat_end": None,
        "mapped_repeat_start": None,
        "mapped_repeat_end": None,
        "transition_seconds": 0.0,
        "method": "sequence_steps",
        "tempo_method": "original",
        "beat_clock_bpm": None,
        "beat_clock_origin": "not_required",
        "steps": segments,
        "step_count": len(segments),
        "bar_aligned": True,
    }
