/**
 * Glosa inglés-español para el caption que recibe el motor.
 *
 * Las captions de entrenamiento son inglesas: un prompt solo en español
 * se obedece peor. `glossPrompt` NO reescribe tu frase: le añade entre
 * paréntesis los equivalentes ingleses de las palabras de estilo que
 * reconoce, sin duplicar lo que ya está. Si no reconoce nada, devuelve
 * el texto intacto. La glosa se ve en VER LO QUE SE ENVÍA porque se
 * aplica antes de mostrar el prompt final.
 */

const GLOSSARY = [
  // Batería y ritmo
  [/bater[ií]as?/i, 'drums'],
  [/bombo/i, 'kick drum'],
  [/caja/i, 'snare'],
  [/platillos?|hi[\s-]?hats?/i, 'hi-hats'],
  [/percusi[oó]n/i, 'percussion'],
  [/\b4x4\b|cuatro por cuatro/i, 'four-on-the-floor'],
  [/ritmo/i, 'groove'],
  // Bajo y armonía
  [/contrabajo/i, 'double bass'],
  [/bajo/i, 'bassline'],
  [/acordes?/i, 'chords'],
  [/arpegios?/i, 'arpeggios'],
  // Instrumentos
  [/guitarras?/i, 'guitars'],
  [/ac[uú]stic[oa]/i, 'acoustic'],
  [/el[eé]ctric[oa]/i, 'electric'],
  [/piano/i, 'piano'],
  [/sintetizadores?|\bsintes?\b/i, 'synthesizers'],
  [/cuerdas/i, 'strings'],
  [/saxof[oó]n/i, 'saxophone'],
  [/trompeta/i, 'trumpet'],
  [/viol[ií]n/i, 'violin'],
  // Voz
  [/\bcoro\b/i, 'choir'],
  [/cantad[oa]/i, 'sung vocals'],
  // Géneros
  [/techno/i, 'techno'],
  [/hardcore|hard house|hardbounce|hard bounce/i, 'hardcore'],
  [/house/i, 'house'],
  [/drum and bass|drum[' ]?n[' ]?bass/i, 'drum and bass'],
  [/lo[\s-]?fi/i, 'lo-fi'],
  [/ambient/i, 'ambient'],
  [/jazz/i, 'jazz'],
  [/orquestal/i, 'orchestral'],
  [/cinematogr[aá]fic[oa]/i, 'cinematic'],
  [/\b[eé]pic[oa]/i, 'epic'],
  // Carácter
  [/oscur[oa]/i, 'dark'],
  [/luminos[oa]/i, 'bright'],
  [/en[eé]rgic[oa]/i, 'energetic'],
  [/melanc[oó]lic[oa]/i, 'melancholic'],
  [/tranquil[oa]/i, 'calm'],
  [/agresiv[oa]/i, 'aggressive'],
  [/pesad[oa]/i, 'heavy'],
  [/contundente/i, 'hard-hitting'],
  [/r[aá]pid[oa]/i, 'fast'],
  [/lent[oa]/i, 'slow'],
  [/melod[ií]as?/i, 'melody'],
  [/sin melod[ií]a|no melody/i, 'without melody'],
];

/** Quita acentos para comparar sin falsos negativos. */
const plain = (s) => (s ?? '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();

/**
 * Añade la glosa inglesa: `texto (english terms)`.
 * No toca la frase del usuario; si no hay coincidencias nuevas, la deja igual.
 */
export function glossPrompt(text) {
  const original = (text ?? '').trim();
  if (!original) return original;
  const haystack = plain(original);
  const terms = [];
  for (const [re, en] of GLOSSARY) {
    if (re.test(original) && !haystack.includes(en.toLowerCase()) && !terms.includes(en)) {
      terms.push(en);
    }
  }
  if (terms.length === 0) return original;
  return `${original} (${terms.join(', ')})`;
}
