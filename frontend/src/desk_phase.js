/** Frases que escribe Musicia. El motor manda su último log en progress_text y no se pinta. */

export const REMIX_FALLBACK = 'Rehaciendo el audio';
export const ANALYSIS_FALLBACK = 'Analizando el audio original…';

/** El motor escribe 0,8 al empezar estas fases y no lo vuelve a mover. */
export const CONVERT_PHASES = ['Convirtiendo a audio', 'Convirtiendo a audio final'];

/** La mesa enseña job.error, no la palabra suelta. */
export const ERROR_PHASES = ['Error', 'Error de análisis'];

const KNOWN = new Set([
  REMIX_FALLBACK,
  ANALYSIS_FALLBACK,
  'En cola',
  'Preparando',
  'Descargando el audio',
  ...CONVERT_PHASES,
  'Cargando el modelo',
  'Listo',
  ...ERROR_PHASES,
  'Cancelado',
  'Grupos listos',
  'Separando los cuatro grupos del original',
  'Separando los grupos del original',
  'Descargando y verificando el audio',
  'En cola del motor (esperando turno en la GPU)',
  'Sintetizando el audio (difusión por pasos)',
  'Cargando el modelo en la GPU (la primera vez tarda varios minutos)',
  'Preparando la estructura musical',
  'Trabajando en el motor (esto tarda 1-3 min con la GPU)',
  'Analizando audio',
  'Esperando análisis',
  'Preparando un fragmento del audio original',
  'El modelo local analiza el audio',
  'Análisis disponible',
]);

const NUMBERED = [
  /^Transformando el audio original con (cover|repaint)$/,
  /^Separando grupos transformados de la variante \d+$/,
  /^Montando la pista transformada de la variante \d+$/,
  /^Recombinando la variante \d+ sobre la timeline original$/,
  /^Exportando la variante \d+$/,
];

export function deskPhase(text, fallback) {
  const line = String(text ?? '').replace(/\s+/g, ' ').trim();
  if (KNOWN.has(line) || NUMBERED.some((pattern) => pattern.test(line))) return line;
  return fallback;
}

const FROZEN_PERCENT = new Set([...CONVERT_PHASES, ...ERROR_PHASES]);

export function movingPercent(phase, ratio) {
  const line = deskPhase(phase, '');
  if (!line || FROZEN_PERCENT.has(line)) return null;
  const value = Number(ratio);
  if (!Number.isFinite(value) || value <= 0 || value >= 1) return null;
  return Math.round(value * 100);
}
