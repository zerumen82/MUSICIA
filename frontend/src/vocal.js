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
  { id: 'ronca', label: 'RONCA', tag: 'raw vocal' },
  { id: 'potente', label: 'POTENTE', tag: 'powerful lead vocal' },
  { id: 'cálida', label: 'CÁLIDA', tag: 'warm vocal' },
  { id: 'clara', label: 'CLARA', tag: 'clear bright vocal' },
];

export const VOCAL_STYLE = [
  { id: 'pop', label: 'POP', tag: 'pop vocals' },
  { id: 'rap', label: 'RAP', tag: 'rapped verses' },
  { id: 'susurro', label: 'SUSURRO', tag: 'whispered vocal' },
  { id: 'coral', label: 'CORAL', tag: 'choir vocals with harmonies and ad-libs' },
  { id: 'potente-belting', label: 'POTENTE', tag: 'powerful commanding vocal' },
  { id: 'hablada', label: 'HABLADA', tag: 'spoken passages' },
];

export const VOCAL_EMOTION = [
  { id: 'alegre', label: 'ALEGRE', tag: 'uplifting euphoric mood' },
  { id: 'melancólica', label: 'MELANCÓLICA', tag: 'melancholic emotional mood' },
  { id: 'íntima', label: 'ÍNTIMA', tag: 'intimate mood' },
  { id: 'enérgica', label: 'ENERGÉTICA', tag: 'energetic driving mood' },
  { id: 'oscura', label: 'OSCURA', tag: 'dark aggressive mood' },
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
 * Sin coletilla inventada: cada tag ya es vocabulario del fabricante
 * (minado en 200 captions: female/male vocal, whispered, rapped…).
 */
export function buildVocalTags({ gender, timbre, style, emotion }) {
  const pick = (list, id) => list.find((o) => o.id === id)?.tag;
  const tags = [pick(VOCAL_GENDER, gender), pick(VOCAL_TIMBRE, timbre), pick(VOCAL_STYLE, style), pick(VOCAL_EMOTION, emotion)]
    .filter(Boolean);
  if (tags.length === 0) return '';
  return tags.join(', ');
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

/**
 * Convierte un par de frases sueltas en una letra completa usando SOLO sus
 * palabras (nada inventado): las frases van como verso y se repiten como
 * estribillo, que es lo que hace una canción con dos frases.
 * Es el respaldo cuando el motor no sabe expandir la letra.
 */
export function expandLyric(text) {
  const raw = (text || '').trim();
  if (!raw) return '';
  if (hasLyricStructure(raw)) return raw;

  const lines = raw.split(/\r?\n/).map((l) => l.trim()).filter(Boolean);
  const chunks = [];
  for (let i = 0; i < lines.length; i += 2) {
    const body = lines.slice(i, i + 2).join('\n');
    chunks.push(body);
  }
  const [first, second] = chunks;
  const extra = chunks.slice(2);

  const parts = ['[Intro]'];
  if (chunks.length === 1) {
    // Solo un bloque de frases: verso, estribillo y puente con lo mismo.
    parts.push(`[Verse]\n${first}`);
    parts.push(`[Chorus]\n${first}`);
    parts.push(`[Bridge]\n${first}`);
  } else {
    parts.push(`[Verse]\n${first}`);
    parts.push(`[Chorus]\n${second}`);
    for (const [i, chunk] of extra.entries()) {
      parts.push(`${i % 2 === 0 ? 'Verse' : 'Chorus'}\n${chunk}`);
    }
  }
  parts.push('[Outro]');
  return parts.join('\n\n');
}
