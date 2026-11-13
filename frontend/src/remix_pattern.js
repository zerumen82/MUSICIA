/**
 * Rejilla de patrón por sección (spec/02 [R20.F]).
 *
 * La resolución y los instrumentos proceden del servidor. La rejilla expresa
 * intención mediante texto; no garantiza que el modelo reproduzca los golpes.
 *
 * Lógica pura, sin React: la rejilla y las pruebas usan las mismas reglas.
 */

/** Nombres legibles de los instrumentos de la rejilla. */
export const PATTERN_LABELS = {
  kick: 'BOMBO',
  snare: 'CAJA',
  hihat: 'CHARLES',
  cymbal: 'PLATILLO',
  clap: 'PALMAS',
};

/** Un patrón vacío con las filas que declara el servidor. */
export function emptyPattern(instruments = [], steps = 0) {
  const size = Number.isInteger(Number(steps)) && Number(steps) > 0 ? Number(steps) : 0;
  const pattern = {};
  for (const instrument of instruments) {
    pattern[instrument] = Array.from({ length: size }, () => false);
  }
  return pattern;
}

/** Un patrón con una celda cambiada. No muta el que recibe. */
export function togglePatternCell(pattern, instrument, index) {
  if (!pattern || !Array.isArray(pattern[instrument])) return pattern;
  const row = pattern[instrument].slice();
  if (index < 0 || index >= row.length) return pattern;
  row[index] = !row[index];
  return { ...pattern, [instrument]: row };
}

/** Cuántos golpes hay marcados en total. */
export function patternHits(pattern) {
  if (!pattern) return 0;
  return Object.values(pattern).reduce(
    (total, row) => total + (Array.isArray(row) ? row.filter(Boolean).length : 0), 0);
}

/** Si el patrón no tiene nada marcado, no viaja (no añade texto al caption). */
export function patternPayload(pattern) {
  if (!pattern || patternHits(pattern) === 0) return null;
  return Object.fromEntries(Object.entries(pattern).map(([instrument, row]) => [instrument, row.slice()]));
}

/** Resumen corto para la cabecera de la rejilla. */
export function patternSummary(pattern) {
  const hits = patternHits(pattern);
  if (!hits) return 'vacío';
  return `${hits} golpe${hits === 1 ? '' : 's'}`;
}

/** La frase que se lee después de generar: qué golpes han caído donde marcaste. */
export function patternCheckLabel(check) {
  if (!check) return null;
  if (check.measured === false) return check.reason || 'No se midió el patrón.';
  if (Number.isFinite(check.expected_count) && Number.isFinite(check.hit_count)) {
    const missing = Number(check.missed_count) || 0;
    return `${check.hit_count} de ${check.expected_count} golpes de bombo donde marcaste${missing ? `; faltaron ${missing}` : ''}.`;
  }
  const hit = (check.hit ?? []).length;
  const missed = (check.missed ?? []).length;
  if (!missed) return `${hit} de ${check.marked} golpes donde marcaste.`;
  return `${hit} de ${check.marked} golpes donde marcaste; fallaron ${missed === 1 ? 'el paso' : 'los pasos'} ${(check.missed ?? []).join(', ')}.`;
}

/** Las flechas recorren la rejilla sin cambiar golpes ni salir de sus límites. */
export function patternCellTarget(key, row, column, rows, columns, control = false) {
  if (!(rows > 0 && columns > 0)) return null;
  if (key === 'ArrowLeft') return { row, column: Math.max(0, column - 1) };
  if (key === 'ArrowRight') return { row, column: Math.min(columns - 1, column + 1) };
  if (key === 'ArrowUp') return { row: Math.max(0, row - 1), column };
  if (key === 'ArrowDown') return { row: Math.min(rows - 1, row + 1), column };
  if (key === 'Home') return { row: control ? 0 : row, column: 0 };
  if (key === 'End') return { row: control ? rows - 1 : row, column: columns - 1 };
  return null;
}
