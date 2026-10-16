/** Para qué sirve cada parte de la mesa. Los títulos coinciden con las sondas. */
import { CONVERT_PHASES, ERROR_PHASES, REMIX_FALLBACK } from './desk_phase.js';

export const ACTIONS = [
  { id: 'full', label: 'Rehacer la canción' },
  { id: 'region', label: 'Cambiar un trozo' },
  { id: 'groups', label: 'Cambiar por pistas' },
  { id: 'voice', label: 'Dejar la voz y crear música nueva' },
  { id: 'adjust', label: 'Ajustar tempo, tono, recorte o loop' },
];

export const SCOPE_WHY = {
  full: 'Rehace toda la canción a partir de esta. El texto dice qué cambia.',
  region: 'Cambia solo el trozo que marques. El resto se queda.',
  groups: 'Elige en cada pista si se queda, se rehace o se quita.',
};

export const SCOPE_BUSY = {
  full: 'Rehaciendo la canción entera',
  region: 'Rehaciendo el trozo marcado',
  groups: 'Rehaciendo las pistas elegidas',
  voice: 'Creando la música nueva',
  adjust: 'Ajustando el audio',
};

export const CONVERTING = 'Convirtiendo el audio a archivo';

export const SECTIONS = {
  advanced: { title: 'REFERENCIA Y AVANZADOS', why: 'Opcional. Timbre de otra pista, voz y semilla.' },
  compare: { title: 'COMPARAR CON EL ORIGINAL', why: 'Escucha el resultado al lado del archivo de partida.' },
  detected: { title: 'AUDIO DETECTADO', why: 'Lo que se oyó en el archivo. Corregirlo no cambia el remix.' },
  engine: { title: 'PARÁMETROS DEL MOTOR', why: 'Lo que se enviará al pulsar REMIX.' },
  executed: { title: 'PARÁMETROS Y SEMILLAS EJECUTADOS', why: 'Lo que salió en este trabajo.' },
  voice: { title: 'VOZ ORIGINAL + BASE NUEVA', why: 'Deja la voz grabada y crea música nueva debajo. No usa el botón REMIX.' },
  adjust: { title: 'AJUSTES DE AUDIO · TEMPO, TONO, RECORTE Y LOOP', why: 'Tempo, tono, recorte o loop, sin regenerar la canción.' },
  limit: { title: 'LÍMITE DEL TRAMO', why: 'Al repintar, el volumen de toda la pista puede cambiar.' },
};

export const REPAINT = {
  conservative: { label: 'Conservador', why: 'Fuera del trozo se queda la grabación.' },
  balanced: { label: 'Equilibrado', why: 'Cambia el trozo y funde los bordes.' },
  aggressive: { label: 'Agresivo', why: 'Puede cambiar también lo de fuera del trozo.' },
};

export function actionWhy(id) {
  if (SCOPE_WHY[id]) return SCOPE_WHY[id];
  if (id === 'voice') return 'Se queda la voz grabada. La música de debajo es nueva.';
  if (id === 'adjust') return 'Cambia el archivo que ya existe, sin generar otra canción.';
  return '';
}

const CONVERT_PHASE = new Set(CONVERT_PHASES);
const ERROR_PHASE = new Set(ERROR_PHASES);

/** La frase genérica del motor se sustituye por el ámbito. La conversión no lleva porcentaje. */
export function remixBusyLine(shown, scope, ratio) {
  if (CONVERT_PHASE.has(shown)) return CONVERTING;
  if (ERROR_PHASE.has(shown)) return '';
  if (shown && shown !== REMIX_FALLBACK) return shown;
  if (typeof ratio === 'number' && ratio >= 1) return CONVERTING;
  return SCOPE_BUSY[scope] || REMIX_FALLBACK;
}
