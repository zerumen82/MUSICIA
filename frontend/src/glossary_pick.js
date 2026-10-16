const norm = (value) => String(value ?? '').trim().toLowerCase().replace(/\s+/g, ' ');
const words = (value) => norm(value).split(/[^a-z0-9]+/).filter(Boolean);

/** `needle` aparece como palabras enteras y seguidas dentro de `hay`. */
function mentions(hay, needle) {
  const hayWords = words(hay);
  const needleWords = words(needle);
  if (!needleWords.length || needleWords.length > hayWords.length) return false;
  return hayWords.some((_, index) => needleWords.every((word, offset) => hayWords[index + offset] === word));
}

/** Así empiezan las captions de ejemplo del modelo. Los términos van detrás. */
const FRAME = 'A track with ';
/** Separa términos enteros. La coma no vale: muchas líneas del vocabulario la llevan. */
const JOIN = ' · ';

/**
 * Términos enteros del cuadro. Una línea como «1960s pop, doo-wop» cuenta
 * como uno solo.
 */
export function modelTerms(prompt) {
  const raw = (prompt ?? '').trim();
  if (!raw) return [];
  const body = raw.toLowerCase().startsWith(FRAME.toLowerCase()) ? raw.slice(FRAME.length) : raw;
  return body.split(JOIN).map((part) => part.trim()).filter(Boolean);
}

/** Quita un «N bpm» pegado a la frase. El tempo va en su control. */
export function sinBpmEnFrase(prompt) {
  return (prompt ?? '')
    .replace(/,?\s*\d+(?:[.,]\d+)?\s*bpm\b/gi, '')
    .replace(/\s{2,}/g, ' ')
    .replace(/\s+·\s+·\s+/g, ' · ')
    .trim()
    .replace(/^[·,\s]+|[·,\s]+$/g, '');
}

/**
 * Añade o quita un término que el modelo tiene en su vocabulario.
 * Varios términos quedan en una sola caption: «A track with gabber, medieval».
 * No se pega una segunda frase ni un texto que el modelo no escribe.
 */
export function applyModelTerm(prompt, term) {
  const token = String(term ?? '').trim();
  const raw = (prompt ?? '').trim();
  if (!token) return raw;
  const framed = raw.toLowerCase().startsWith(FRAME.toLowerCase());
  if (!framed) return `${FRAME}${token}`;
  const terms = modelTerms(raw);
  const index = terms.findIndex((item) => norm(item) === norm(token));
  const next = index >= 0 ? terms.filter((_, i) => i !== index) : [...terms, token];
  return next.length ? `${FRAME}${next.join(JOIN)}` : '';
}

/** Claves literales del estilo. Las `re:` son expresiones, no líneas. */
export function styleKeys(style) {
  return [style?.name, style?.genre, ...(style?.keys ?? [])]
    .map((key) => String(key ?? '').trim())
    .filter((key) => key && !key.startsWith('re:'));
}

/** Estilo cuya clave es exactamente esta línea del vocabulario. */
export function findStyle(styles, line) {
  const needle = norm(line);
  if (!needle) return null;
  return (styles ?? []).find((style) => style?.text && styleKeys(style).some((key) => norm(key) === needle)) ?? null;
}

/**
 * Estilos que casan con lo que se busca. Primero la clave exacta.
 * Sin consulta no se lista el catálogo: el glosario sigue siendo el vocabulario.
 */
export function stylesForQuery(styles, query, limit = 3) {
  const needle = norm(query);
  if (needle.length < 3) return [];
  const exact = [];
  const partial = [];
  for (const style of styles ?? []) {
    if (!style?.text) continue;
    const keys = styleKeys(style).map(norm);
    if (keys.some((key) => key === needle)) exact.push(style);
    else if (needle.length >= 4 && keys.some((key) => mentions(needle, key))) partial.push(style);
  }
  return [...exact, ...partial].slice(0, limit);
}

/**
 * Una entrada suelta del vocabulario, sin frase de estilo, sigue siendo
 * solo esa palabra. Volver a pulsarla la quita.
 */
export function applyGlossaryPick(prompt, { genre = '' } = {}) {
  return applyModelTerm(prompt, genre);
}

/**
 * Pie del glosario. Sin respuesta todavía no se dice que el archivo falta:
 * eso solo lo afirma el servidor con available en false. Un fallo escrito
 * no se disfraza de archivo ausente ni de carga.
 */
export function glossaryFoot(data, fail) {
  if (fail) return 'error';
  if (data?.available) return 'ready';
  if (data && data.available === false) return 'missing';
  return 'loading';
}

/**
 * La respuesta solo vale para la consulta que la pidió.
 * Otra consulta, o ninguna respuesta, no enseña ese recuento.
 * El servidor devuelve `q` tal cual se envió (ya recortado).
 */
export function glossaryShown(data, query) {
  if (data == null || String(data.q ?? '') !== query) return null;
  return data;
}

/**
 * Junta el texto de las pistas en transformar en una sola caption.
 * Una pista vacía no aporta términos. No se inventa ninguno.
 * El mismo término en dos pistas queda una vez, en el orden de las pistas.
 */
export function joinTrackPrompts(texts) {
  const terms = [];
  for (const text of texts ?? []) {
    for (const term of modelTerms(text)) {
      if (!terms.some((item) => norm(item) === norm(term))) terms.push(term);
    }
  }
  return terms.length ? `${FRAME}${terms.join(JOIN)}` : '';
}

/**
 * El estilo del prompt se conserva. Los textos de pista se suman.
 * Si el prompt ya es una caption del modelo, todo queda en una sola.
 * Una pista vacía no añade términos.
 */
export function joinStyleAndTracks(style, tracks) {
  const styleText = String(style ?? '').trim();
  const trackPhrase = joinTrackPrompts(tracks);
  if (!trackPhrase) return styleText;
  if (!styleText) return trackPhrase;
  if (styleText.toLowerCase().startsWith(FRAME.toLowerCase())) {
    return joinTrackPrompts([styleText, ...(tracks ?? [])]);
  }
  const extra = modelTerms(trackPhrase).join(JOIN);
  return extra ? `${styleText} · ${extra}` : styleText;
}

/** Añade un término si falta. No lo quita: sirve para la voz, que ya está elegida. */
export function ensureModelTerm(prompt, term) {
  const token = String(term ?? '').trim();
  const raw = (prompt ?? '').trim();
  if (!token) return raw;
  const terms = modelTerms(raw);
  const next = terms.some((item) => norm(item) === norm(token)) ? terms : [...terms, token];
  return next.length ? `${FRAME}${next.join(JOIN)}` : '';
}
