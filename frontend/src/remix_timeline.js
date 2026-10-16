const SECONDS_PER_MINUTE = 60;

const hasValue = (value) => value !== '' && value != null;
const within = (value, bounds) => Number.isFinite(value)
  && (bounds?.min == null || value >= bounds.min)
  && (bounds?.max == null || value <= bounds.max);

/** Only a bounded, confident measurement can populate the editable source tempo. */
export function measuredRemixBpm(groove, capabilities) {
  const bpm = Number(groove?.bpm);
  const confidence = Number(groove?.confidence);
  const limits = capabilities?.parameters?.source_bpm ?? capabilities?.parameters?.bpm;
  const threshold = capabilities?.timeline?.min_groove_confidence;
  return bpm > 0 && within(bpm, limits) && Number.isFinite(confidence)
    && threshold != null && confidence >= threshold ? bpm : null;
}

/** Full covers with a target tempo cannot know their DSP ratio before generation. */
export function remixNaturalDuration({ scope, sourceDuration, targetBpm, sourceBpm }) {
  const duration = Number(sourceDuration);
  if (!(duration > 0) || !Number.isFinite(duration) || scope === 'region') return null;
  if (!hasValue(targetBpm)) return duration;
  if (scope !== 'groups') return null;
  const original = Number(sourceBpm);
  const target = Number(targetBpm);
  return original > 0 && target > 0 && Number.isFinite(original) && Number.isFinite(target)
    ? duration * original / target : null;
}

export function remixMinimumDurationLabel(duration) {
  if (!(duration > 0) || !Number.isFinite(duration)) return null;
  const seconds = Math.ceil(duration);
  return `${Math.floor(seconds / SECONDS_PER_MINUTE)}:${String(seconds % SECONDS_PER_MINUTE).padStart(2, '0')} (${seconds} s)`;
}

/** Segundos marcados en la onda para la parte que se repite. Vacío es el extremo del tema. */
export function repeatBoundsFromWave(selection) {
  const start = Number(selection?.trim_start_s);
  const end = selection?.trim_end_s;
  const text = (value) => String(Math.round(Number(value) * 100) / 100);
  return {
    start: Number.isFinite(start) && start > 0 ? text(start) : '',
    end: end == null || end === '' || !Number.isFinite(Number(end)) ? '' : text(end),
  };
}

/** Produce the same optional timeline fields for preview and execution. */
export function remixTimelineFields({ scope, targetBpm, sourceBpm, sourceBpmOrigin = 'manual', minutes, seconds,
  repeatStart, repeatEnd, transition, sourceDuration, capabilities }) {
  const fields = {};
  const parameters = capabilities?.parameters ?? {};
  const timeline = capabilities?.timeline ?? {};
  if (scope === 'groups' && hasValue(targetBpm) && hasValue(sourceBpm)) {
    const measured = Number(sourceBpm);
    if (measured <= 0 || !within(measured, parameters.source_bpm ?? parameters.bpm)) {
      return { fields, error: 'Escribe un BPM original válido para las pistas.' };
    }
    if (sourceBpmOrigin === 'manual') fields.source_bpm = measured;
  }
  if (!['full', 'groups'].includes(scope) || (!hasValue(minutes) && !hasValue(seconds))) return { fields, error: null };
  const mins = hasValue(minutes) ? Number(minutes) : 0;
  const secs = hasValue(seconds) ? Number(seconds) : 0;
  if (!Number.isInteger(mins) || mins < 0 || !Number.isFinite(secs) || secs < 0 || secs >= SECONDS_PER_MINUTE) {
    return { fields, error: 'Escribe minutos enteros y segundos entre 0 y 59 para la duración.' };
  }
  const duration = mins * SECONDS_PER_MINUTE + secs;
  const limits = parameters.duration_seconds ?? { min: timeline.min_duration_seconds, max: timeline.max_duration_seconds };
  if (duration <= 0 || !within(duration, limits)) {
    return { fields, error: `La duración debe estar entre ${limits.min ?? 0} y ${limits.max ?? 'el máximo configurado'} segundos.` };
  }
  fields.duration_seconds = duration;
  const natural = remixNaturalDuration({ scope, sourceDuration, targetBpm, sourceBpm });
  if (natural != null && duration < natural) {
    return { fields, error: `La duración mínima al tempo elegido es ${remixMinimumDurationLabel(natural)}.` };
  }
  const start = hasValue(repeatStart) ? Number(repeatStart) : 0;
  const end = hasValue(repeatEnd) ? Number(repeatEnd) : sourceDuration;
  if (hasValue(repeatStart) || hasValue(repeatEnd)) {
    fields.repeat_start = start;
    fields.repeat_end = end;
    if (!Number.isFinite(start) || !Number.isFinite(end) || start < 0 || end <= start || (sourceDuration != null && end > sourceDuration)) {
      return { fields, error: 'La parte a repetir debe estar dentro del original y terminar después de su inicio.' };
    }
    const ratio = scope === 'groups' && hasValue(targetBpm)
      ? (hasValue(sourceBpm) ? Number(targetBpm) / Number(sourceBpm) : null)
      : scope === 'full' && hasValue(targetBpm) ? null : 1;
    if (ratio > 0 && timeline.min_repeat_seconds != null && (end - start) / ratio < timeline.min_repeat_seconds) {
      return { fields, error: `La parte a repetir debe durar al menos ${timeline.min_repeat_seconds} segundos.` };
    }
  }
  if (hasValue(transition)) {
    const fade = Number(transition);
    if (fade <= 0 || !within(fade, parameters.transition_seconds ?? { min: 0, max: timeline.max_transition_seconds })) {
      return { fields, error: 'Escribe un fundido dentro de los límites indicados.' };
    }
    fields.transition_seconds = fade;
  }
  return { fields, error: null };
}
