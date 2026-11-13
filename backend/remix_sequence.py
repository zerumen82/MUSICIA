"""Secuencia de pasos del remix: reparto en la línea de tiempo y contrato de cada paso.

Una secuencia divide la canción en tramos y vuelve a hacer **uno por paso**, en
orden. El orden lo pone la línea de tiempo, no el prompt: el motor se salta el
LM en `cover` y `repaint`, así que un texto con ocho instrucciones no es un
programa (ver [R20] en spec/02).
"""
from __future__ import annotations

import math

from pydantic import BaseModel, ConfigDict, Field

from config import get_settings

# Focos posibles de un paso. `todo` rehace el tramo entero; el resto son para
# la fase siguiente (separar la pista concreta del tramo antes de rehacerla).
STEP_FOCUSES = ("todo", "vocals", "drums", "bass", "other")

# Focos que el backend ejecuta hoy. Los demás se rechazan: un selector que no
# hace nada sería un autoengaño. `drums` separa el tramo, rehace solo la
# batería y lo remezcla con el resto original (spec/02 [R20.D]).
IMPLEMENTED_FOCUSES = ("todo", "drums")

class SequencePattern(BaseModel):
    """Un patrón de ritmo de una sección: qué instrumento suena en cada paso.

    La longitud se contrasta con la configuración efectiva al validar el
    proyecto, no con otra copia fija en Pydantic. Filas omitidas están vacías.
    Cymbal significa platillo; clap conserva el significado histórico palmas.
    """

    kick: list[bool] = Field(default_factory=list)
    snare: list[bool] = Field(default_factory=list)
    hihat: list[bool] = Field(default_factory=list)
    cymbal: list[bool] = Field(default_factory=list)
    clap: list[bool] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")

    def hits(self) -> dict[str, list[int]]:
        """Celdas marcadas (numeradas desde 1), sin inferir otros instrumentos."""
        return {instrument: [index + 1 for index, on in enumerate(getattr(self, instrument)) if on]
                for instrument in type(self).model_fields}

    def is_empty(self) -> bool:
        return not any(self.hits().values())


def as_pattern(value) -> SequencePattern | None:
    """El patrón puede venir como modelo o como diccionario.

    El plan de la secuencia se guarda en el historial (JSON), así que el
    patrón viaja como diccionario y se reconstruye aquí.
    """
    if value is None:
        return None
    if isinstance(value, SequencePattern):
        return value
    if isinstance(value, dict):
        return SequencePattern(**value)
    raise ValueError("El patrón no tiene un formato válido")


def _pattern_settings(config=None):
    return config if config is not None else get_settings().remix


def _pattern_meter(beats_per_bar=None):
    return beats_per_bar if beats_per_bar is not None else get_settings().mixer.beats_per_bar


def pattern_step_seconds(bpm: float, beats_per_bar: int, config=None) -> float:
    """Resolución de una subdivisión; BPM cuenta los tiempos del compás."""
    config = _pattern_settings(config)
    if (not bpm or not math.isfinite(bpm) or bpm <= 0
            or not isinstance(config.pattern_steps, int) or isinstance(config.pattern_steps, bool)
            or config.pattern_steps <= 0 or not beats_per_bar
            or not math.isfinite(beats_per_bar) or beats_per_bar <= 0):
        raise ValueError("La resolución del patrón necesita tempo, compás y pasos positivos y finitos")
    return 60.0 / bpm * beats_per_bar / config.pattern_steps


def pattern_onset_gap_ms(bpm: float, beats_per_bar: int, config=None) -> float:
    config = _pattern_settings(config)
    fraction = config.pattern_onset_gap_step_fraction
    if not math.isfinite(fraction) or not 0 < fraction < 1:
        raise ValueError("La distancia mínima entre ataques debe ser menor que una subdivisión")
    return pattern_step_seconds(bpm, beats_per_bar, config) * fraction * 1000


def pattern_capabilities(config, beats_per_bar: int) -> dict:
    """Contrato que comparte UI con compilación y medición."""
    return {"steps": config.pattern_steps, "instruments": list(config.pattern_instruments),
            "legacy_instruments": list(config.pattern_legacy_instruments),
            "labels": dict(config.pattern_labels), "beats_per_bar": beats_per_bar,
            "beat_unit": config.pattern_beat_unit, "tolerance_ms": config.pattern_tolerance_ms,
            "tolerance_step_fraction": config.pattern_tolerance_step_fraction,
            "onset_gap_step_fraction": config.pattern_onset_gap_step_fraction,
            "measured_instruments": ["kick"]}


def compile_pattern_text(pattern: SequencePattern | None, *, config=None, beats_per_bar=None) -> str:
    """Traduce el patrón a una frase en inglés para el caption del motor.

    Expresa intención, unidad y prioridad, sin garantizar obediencia del motor.
    """
    pattern = as_pattern(pattern)
    if pattern is None or pattern.is_empty():
        return ""
    config = _pattern_settings(config)
    beats_per_bar = _pattern_meter(beats_per_bar)
    validate_pattern(pattern, 1, config)
    parts = []
    for instrument in dict.fromkeys([*config.pattern_instruments, *config.pattern_legacy_instruments]):
        steps = pattern.hits()[instrument]
        if not steps:
            continue
        values = {"instrument": config.pattern_caption_labels[instrument]}
        if len(steps) == config.pattern_steps:
            parts.append(config.pattern_all_template.format(**values))
        elif steps == list(range(1, config.pattern_steps + 1, 2)):
            parts.append(config.pattern_alternate_template.format(**values))
        else:
            numbers = config.pattern_position_separator.join(str(step) for step in steps)
            parts.append(config.pattern_positions_template.format(**values, positions=numbers))
    if not parts:
        return ""
    return config.pattern_header_template.format(
        steps=config.pattern_steps, beats_per_bar=beats_per_bar, beat_unit=config.pattern_beat_unit,
        rows=config.pattern_row_separator.join(parts))


def step_caption(prompt: str, pattern: SequencePattern | None, *, config=None, beats_per_bar=None) -> str:
    """El caption de un paso: su texto (ya en inglés) más el ritmo del patrón.

    El patrón manda en el ritmo; el texto del usuario, en el estilo y el papel
    de la sección.
    """
    config = _pattern_settings(config)
    rhythm = compile_pattern_text(pattern, config=config, beats_per_bar=beats_per_bar)
    if not rhythm:
        return (prompt or "").strip()
    text = (prompt or "").strip()
    return config.pattern_detail_separator.join(part for part in (rhythm, text) if part)


def check_kick_pattern(pattern: SequencePattern | None, onsets_s: list[float],
                       bpm: float, duration_seconds: float | None = None, *,
                       beats_per_bar=None, config=None) -> dict:
    """Qué pasos marcados del bombo han tenido golpe en el audio producido.

    Solo mide la fila del bombo: es el único detector de percusión que hay.
    Devuelve los pasos acertados, los fallados y los golpes que no se habían
    marcado (información, no un error).
    """
    pattern = as_pattern(pattern)
    if pattern is None:
        return {"measured": False, "reason": "La sección no tiene patrón marcado."}
    marked = pattern.hits()["kick"]
    if not marked:
        return {"measured": False, "reason": "El patrón no marca ningún bombo."}
    if not bpm or bpm <= 0:
        return {"measured": False, "reason": "Sin tempo fiable no se pueden situar los golpes."}
    if not duration_seconds or not math.isfinite(duration_seconds) or duration_seconds <= 0:
        return {"measured": False, "reason": "Sin duración real de la sección no se pueden contar sus compases."}
    config = _pattern_settings(config)
    minimum = config.pattern_min_measurement_seconds
    if (isinstance(minimum, (int, float)) and not isinstance(minimum, bool)
            and minimum > 0 and duration_seconds < minimum):
        return {"measured": False,
                "reason": f"La sección dura menos de {minimum:g} s: no hay material para medir sus compases."}
    beats_per_bar = _pattern_meter(beats_per_bar)
    try:
        validate_pattern(pattern, 1, config)
        step_seconds = pattern_step_seconds(bpm, beats_per_bar, config)
        fraction = config.pattern_tolerance_step_fraction
        if (not math.isfinite(fraction) or not 0 < fraction < .5
                or not math.isfinite(config.pattern_tolerance_ms) or config.pattern_tolerance_ms <= 0):
            raise ValueError("La tolerancia debe ser positiva y menor que media subdivisión")
    except ValueError as exc:
        return {"measured": False, "reason": str(exc)}
    tolerance = min(config.pattern_tolerance_ms / 1000, step_seconds * fraction)
    bar_seconds = step_seconds * config.pattern_steps
    expected = [{"bar": bar + 1, "step": step, "time_seconds": bar * bar_seconds + (step - 1) * step_seconds}
                for bar in range(math.ceil(duration_seconds / bar_seconds)) for step in marked
                if bar * bar_seconds + (step - 1) * step_seconds < duration_seconds]
    onsets = sorted(float(onset) for onset in onsets_s if math.isfinite(onset) and 0 <= onset < duration_seconds)
    used = set()
    hit_events, missed_events = [], []
    for event in expected:
        available = [(abs(onset - event["time_seconds"]), index) for index, onset in enumerate(onsets)
                     if index not in used and abs(onset - event["time_seconds"]) <= tolerance]
        rounded = {**event, "time_seconds": round(event["time_seconds"], 6)}
        if available:
            _distance, index = min(available)
            used.add(index)
            hit_events.append({**rounded, "onset_seconds": round(onsets[index], 6),
                               "error_ms": round((onsets[index] - event["time_seconds"]) * 1000, 3)})
        else:
            missed_events.append(rounded)
    extra = [round(onset, 6) for index, onset in enumerate(onsets) if index not in used]
    return {
        "measured": True,
        "marked": len(expected), "expected_count": len(expected),
        "hit_count": len(hit_events), "missed_count": len(missed_events),
        "hit": [event["step"] for event in hit_events],
        "missed": [event["step"] for event in missed_events],
        "hit_events": hit_events, "missed_events": missed_events,
        "extra_onsets_s": extra,
        "coverage": round(len(hit_events) / len(expected), 3) if expected else None,
        "bpm": round(float(bpm), 2),
        "duration_seconds": duration_seconds, "beats_per_bar": beats_per_bar,
        "pattern_steps": config.pattern_steps, "bar_count": math.ceil(duration_seconds / bar_seconds),
        "step_seconds": round(step_seconds, 6), "tolerance_ms": round(tolerance * 1000, 3),
        "measured_instruments": ["kick"],
    }

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
    pattern: SequencePattern | None = None

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
                "hoy cada paso rehace el tramo entero o solo la batería.")
        if step.pattern is not None:
            validate_pattern(step.pattern, step.index + 1, config)
    return active


def validate_pattern(pattern: SequencePattern, position: int, config) -> None:
    """El patrón tiene que encajar con los límites declarados en la configuración."""
    allowed = [*config.pattern_instruments, *config.pattern_legacy_instruments]
    if (not isinstance(config.pattern_steps, int) or isinstance(config.pattern_steps, bool)
            or config.pattern_steps <= 0 or len(allowed) != len(set(allowed))
            or any(name not in type(pattern).model_fields for name in allowed)):
        raise ValueError("La configuración de pasos o instrumentos del patrón es inválida")
    for instrument in type(pattern).model_fields:
        row = getattr(pattern, instrument)
        if any(row) and instrument not in allowed:
            raise ValueError(f"El instrumento «{instrument}» no está en la configuración del patrón")
        if row and len(row) != config.pattern_steps:
            raise ValueError(f"El patrón del paso {position} tiene filas de {len(getattr(pattern, instrument))} "
                             f"pasos: el patrón son {config.pattern_steps}")


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
            # El patrón viaja como diccionario: el plan se guarda en el historial.
            "pattern": step.pattern.model_dump(mode="json") if step.pattern else None,
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
