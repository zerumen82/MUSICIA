/** Dirección de una tecla de cursor. 0 si no es un movimiento. */
export function arrowDirection(key) {
  if (key === 'ArrowRight' || key === 'ArrowUp' || key === 'Right') return 1;
  if (key === 'ArrowLeft' || key === 'ArrowDown' || key === 'Left') return -1;
  return 0;
}

/**
 * Mueve un borde del intervalo `step` segundos.
 * El final null significa «hasta el final de la duración».
 * No cruza el otro borde ni sale de [0, duración].
 */
export function nudgeInterval({ start, end, duration, edge, direction, step }) {
  const span = Number(duration);
  const amount = Number(step);
  if (!(span > 0) || !(amount > 0) || (direction !== 1 && direction !== -1)) return null;
  const currentStart = Number(start);
  const currentEnd = end == null || end === '' ? span : Number(end);
  if (!Number.isFinite(currentStart) || !Number.isFinite(currentEnd)) return null;
  if (edge === 'start') {
    const next = Math.min(Math.max(0, currentStart + direction * amount), currentEnd);
    if (!(next < currentEnd) || next === currentStart) return null;
    return { start: next, end: currentEnd >= span ? null : currentEnd };
  }
  if (edge === 'end') {
    const next = Math.max(Math.min(span, currentEnd + direction * amount), currentStart);
    if (!(next > currentStart) || next === currentEnd) return null;
    return { start: currentStart, end: next >= span ? null : next };
  }
  return null;
}

/** Mueve la posición compartida dentro del intervalo válido, sin salirse. */
export function nudgePosition(time, bounds, direction, step) {
  const amount = Number(step);
  if (!bounds?.valid || !(amount > 0) || (direction !== 1 && direction !== -1)) return null;
  const current = Number(time);
  if (!Number.isFinite(current)) return null;
  const next = current + direction * amount;
  if (next < bounds.start || next >= bounds.end) return null;
  return next;
}
