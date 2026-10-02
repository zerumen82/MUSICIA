/**
 * Datos y helpers de la voz cantada (spec/02 [A3]).
 *
 * Los descriptores van en inglés porque son los que consume el modelo
 * (sus captions son en inglés); las etiquetas de la UI, en español.
 * Todo aquí son DATOS: la lógica solo los combina.
 */

export const VOCAL_GENDER = [
  { id: 'femenina', label: 'FEMENINA', tag: 'female vocal' },
  { id: 'masculina', label: 'MASCULINA', tag: 'male vocal' },
];

export const VOCAL_TIMBRE = [
  { id: 'suave', label: 'SUAVE', tag: 'soft gentle vocal' },
  { id: 'ronca', label: 'RONCA', tag: 'raspy husky vocal' },
  { id: 'potente', label: 'POTENTE', tag: 'powerful strong vocal' },
  { id: 'cálida', label: 'CÁLIDA', tag: 'warm breathy vocal' },
  { id: 'clara', label: 'CLARA', tag: 'clear bright vocal' },
];

export const VOCAL_STYLE = [
  { id: 'pop', label: 'POP', tag: 'pop vocal style' },
  { id: 'rap', label: 'RAP', tag: 'rap vocal delivery' },
  { id: 'susurro', label: 'SUSURRO', tag: 'whispered vocal' },
  { id: 'coral', label: 'CORAL', tag: 'group choir vocals' },
  { id: 'potente-belting', label: 'POTENTE', tag: 'belting powerful vocals' },
  { id: 'hablada', label: 'HABLADA', tag: 'spoken word vocal' },
];

export const VOCAL_EMOTION = [
  { id: 'alegre', label: 'ALEGRE', tag: 'happy uplifting mood' },
  { id: 'melancólica', label: 'MELANCÓLICA', tag: 'melancholic emotional mood' },
  { id: 'íntima', label: 'ÍNTIMA', tag: 'intimate romantic mood' },
  { id: 'enérgica', label: 'ENERGÉTICA', tag: 'energetic driving mood' },
  { id: 'oscura', label: 'OSCURA', tag: 'dark brooding mood' },
];

/** Idiomas que el motor entiende para `vocal_language` (spec A3). */
export const VOCAL_LANGUAGES = [
  { id: 'es', label: 'ESPAÑOL' },
  { id: 'en', label: 'INGLÉS' },
  { id: 'it', label: 'ITALIANO' },
  { id: 'fr', label: 'FRANCÉS' },
  { id: 'pt', label: 'PORTUGUÉS' },
  { id: 'de', label: 'ALEMÁN' },
  { id: 'ja', label: 'JAPONÉS' },
];

const MARKERS = /\[(intro|verse|chorus|bridge|outro|hook|pre-chorus|inst|instrumental|verso|estribillo|puente)\b/i;

/**
 * Une los descriptores elegidos en una frase para el prompt.
 * Devuelve '' si el usuario no eligió nada.
 */
export function buildVocalTags({ gender, timbre, style, emotion }) {
  const pick = (list, id) => list.find((o) => o.id === id)?.tag;
  const tags = [pick(VOCAL_GENDER, gender), pick(VOCAL_TIMBRE, timbre), pick(VOCAL_STYLE, style), pick(VOCAL_EMOTION, emotion)]
    .filter(Boolean);
  if (tags.length === 0) return '';
  return `${tags.join(', ')}, sung vocals`;
}

/**
 * El motor espera la letra con marcas de estructura; un párrafo plano suele
 * salir instrumental. Si el usuario no las escribió, se las ponemos nosotros
 * alternando verso y estribillo (determinista, sin inventar texto).
 */
export function structureLyric(text) {
  const raw = (text || '').trim();
  if (!raw) return '';
  if (MARKERS.test(raw)) return raw; // ya estructurada: no se toca

  const lines = raw.split(/\r?\n/);
  const blocks = [];
  let current = [];
  const flush = (marker) => {
    const body = current.join('\n').trim();
    if (body) blocks.push(`[${marker}]\n${body}`);
    current = [];
  };
  // Un bloque por cada 4 líneas (o por párrafo doble) ya es verso/estribillo.
  for (const line of lines) {
    if (line.trim() === '') { if (current.length) flush(blocks.length % 2 ? 'Chorus' : 'Verse'); continue; }
    current.push(line);
    if (current.length === 4) flush(blocks.length % 2 ? 'Chorus' : 'Verse');
  }
  flush(blocks.length % 2 ? 'Chorus' : 'Verse');

  return ['[Intro]', ...blocks, '[Outro]'].join('\n\n');
}

/** El usuario ya escribió marcas de estructura. */
export function hasLyricStructure(text) {
  return MARKERS.test(text || '');
}
