/**
 * Glosa inglés-español para el caption que recibe el motor.
 *
 * Las captions de entrenamiento son inglesas: un prompt solo en español
 * se obedece peor. `glossPrompt` NO reescribe tu frase: le añade entre
 * paréntesis los equivalentes ingleses de las palabras de estilo que
 * reconoce, sin duplicar lo que ya está. Si no reconoce nada, devuelve
 * el texto intacto. La glosa se ve en VER LO QUE SE ENVÍA porque se
 * aplica antes de mostrar el prompt final.
 *
 * Cada entrada puede llevar `without`: la forma inglesa cuando la palabra
 * está negada («sin melodías» → without melody). Si una palabra negada no
 * tiene forma `without`, no se añade nada. El bug del 2026-10-05 era
 * exactamente ese: «sin melodías» glosaba `melody, without melody` y el
 * motor recibía la orden de meter melodía y de quitarla a la vez.
 */

const GLOSSARY = [
  // Batería y ritmo
  { re: /bater[ií]as?/i, en: 'drums', without: 'without drums' },
  { re: /bombo/i, en: 'kick drum', without: 'without kick drum' },
  { re: /caja/i, en: 'snare' },
  { re: /platillos?|hi[\s-]?hats?/i, en: 'hi-hats' },
  { re: /percusi[oó]n/i, en: 'percussion', without: 'without percussion' },
  { re: /\b4x4\b|cuatro por cuatro/i, en: 'four-on-the-floor' },
  { re: /\britmo\b/i, en: 'groove' },
  // Bajo y armonía
  { re: /contrabajo/i, en: 'double bass' },
  { re: /\bbajo\b/i, en: 'bassline', without: 'without bassline' },
  { re: /acordes?/i, en: 'chords', without: 'without chords' },
  { re: /arpegios?/i, en: 'arpeggios' },
  // Instrumentos
  { re: /guitarras?/i, en: 'guitars', without: 'without guitars' },
  { re: /ac[uú]stic[oa]/i, en: 'acoustic' },
  { re: /el[eé]ctric[oa]/i, en: 'electric' },
  { re: /piano/i, en: 'piano', without: 'without piano' },
  { re: /sintetizador(?:es)?|\bsintes?\b/i, en: 'synthesizers', without: 'without synthesizers' },
  { re: /cuerdas/i, en: 'strings', without: 'without strings' },
  { re: /saxof[oó]n/i, en: 'saxophone' },
  { re: /trompeta/i, en: 'trumpet' },
  { re: /viol[ií]n/i, en: 'violin' },
  // Voz (estilo vocal de la guía oficial: whispered, powerful, falsetto, rap)
  { re: /susurrad[oa]s?/i, en: 'whispered' },
  { re: /potentes?/i, en: 'powerful' },
  { re: /falsete/i, en: 'falsetto' },
  { re: /gritad[oa]s?|gritando/i, en: 'shouted' },
  { re: /rapead[oa]s?/i, en: 'rapped' },
  { re: /hablad[oa]s?/i, en: 'spoken' },
  { re: /armon[ií]as?/i, en: 'harmonies' },
  // Tempo feel de la guía oficial (fast, slow, moderate, driving)
  { re: /lent[oa]s?/i, en: 'slow' },
  { re: /moderad[oa]s?/i, en: 'mid tempo' },
  { re: /constantes?/i, en: 'steady' },
  { re: /imparable/i, en: 'driving' },
  // Épica e instrumentos frecuentes en sus 400 textos
  { re: /himnos?/i, en: 'anthemic' },
  { re: /explosiv[oa]s?/i, en: 'explosive' },
  { re: /capas/i, en: 'layered' },
  { re: /pegadiz[oa]s?/i, en: 'catchy' },
  { re: /riffs?/i, en: 'riffs' },
  { re: /\bcoro\b/i, en: 'choir' },
  { re: /cantad[oa]/i, en: 'sung vocals' },
  { re: /\bvoz(es)?\b/i, en: 'vocals', without: 'without vocals' },
  // Géneros
  { re: /\btechno\b|\btecno\b/i, en: 'techno' },
  { re: /hardcore|hard house|hardbounce|hard bounce/i, en: 'hardcore' },
  { re: /\bgabber\b/i, en: 'gabber' },
  { re: /\bhardstyle\b/i, en: 'hardstyle' },
  { re: /frenchcore|rawstyle|uptempo|\bmakina\b/i, en: 'hard dance' },
  { re: /\bhouse\b/i, en: 'house' },
  { re: /electro/i, en: 'electro' },
  { re: /\btrance\b/i, en: 'trance' },
  { re: /\brave\b/i, en: 'rave' },
  { re: /industrial/i, en: 'industrial' },
  { re: /drum and bass|drum[' ]?n[' ]?bass|\bdnb\b/i, en: 'drum and bass' },
  { re: /breakbeat|jungle/i, en: 'breakbeat' },
  { re: /dubstep/i, en: 'dubstep' },
  { re: /\breggae\b|\bdub\b/i, en: 'reggae' },
  { re: /funk/i, en: 'funk' },
  { re: /\bdisco\b/i, en: 'disco' },
  { re: /hip[ -]?hop|\brap\b/i, en: 'hip-hop' },
  { re: /\btrap\b/i, en: 'trap' },
  { re: /reggaet[oó]n/i, en: 'reggaeton' },
  { re: /\bsalsa\b/i, en: 'salsa' },
  { re: /flamenco/i, en: 'flamenco' },
  { re: /\bmetal\b/i, en: 'metal' },
  { re: /\brock\b/i, en: 'rock' },
  { re: /\bpop\b/i, en: 'pop' },
  { re: /synthwave|retrowave/i, en: 'synthwave' },
  { re: /lo[\s-]?fi/i, en: 'lo-fi' },
  { re: /\bambient\b|ambiental/i, en: 'ambient' },
  { re: /\bjazz\b/i, en: 'jazz' },
  { re: /orquestal/i, en: 'orchestral' },
  { re: /cinematogr[aá]fic[oa]/i, en: 'cinematic' },
  { re: /\b[eé]pic[oa]/i, en: 'epic' },
  { re: /progresiv[oa]/i, en: 'progressive' },
  // Carácter
  { re: /oscur[oa]/i, en: 'dark' },
  { re: /luminos[oa]/i, en: 'bright' },
  { re: /brillante/i, en: 'bright' },
  { re: /en[eé]rgic[oa]/i, en: 'energetic' },
  { re: /melanc[oó]lic[oa]/i, en: 'melancholic' },
  { re: /tranquil[oa]/i, en: 'gentle' },
  { re: /agresiv[oa]/i, en: 'aggressive' },
  { re: /pesad[oa]/i, en: 'heavy' },
  { re: /contundente/i, en: 'hard-hitting' },
  { re: /potente/i, en: 'powerful' },
  { re: /distorsionad[oa]/i, en: 'distorted' },
  { re: /saturad[oa]/i, en: 'distorted' },
  { re: /suci[oa]/i, en: 'gritty' },
  { re: /limpi[oa]/i, en: 'clean' },
  { re: /profund[oa]/i, en: 'deep' },
  { re: /pegajos[oa]/i, en: 'catchy' },
  { re: /mel[oó]dic[oa]/i, en: 'melodic', without: 'without melody' },
  { re: /melod[ií]as?/i, en: 'melody', without: 'without melody' },
  { re: /r[aá]pid[oa]/i, en: 'fast' },
  { re: /lent[oa]/i, en: 'slow' },
  { re: /tranquil[oa]s?/i, en: 'gentle' },
  { re: /espacios[oa]/i, en: 'spacious' },
  { re: /minimalista/i, en: 'minimalist' },
  { re: /nost[áa]lgic[oa]s?/i, en: 'nostalgic' },
  { re: /tens[oa]/i, en: 'tense' },
  { re: /optimista/i, en: 'bright' },
  { re: /evolucion/i, en: 'evolving' },
  // «clímax» contiene a «climax» y viceversa: como nostálgico y minimalista,
  // la glosa no lo repite (ver tests). No necesita entrada propia.
  { re: /vinilo/i, en: 'vinyl' },
];

// Palabras de negación que dejan un término en su forma contraria.
const NEGATION_BEFORE =
  /(?:^|[^a-záéíóúüñ])(sin|no|without)(?:\s+(?:el|la|los|las|un|una|unos|unas|any))?\s+$/i;

/** Quita acentos para comparar sin falsos negativos. */
const plain = (s) => (s ?? '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();

/** ¿La coincidencia en `index` está justo tras una negación («sin …»)? */
const isNegated = (original, index) =>
  NEGATION_BEFORE.test(original.slice(Math.max(0, index - 16), index));

/**
 * Añade la glosa inglesa: `texto (english terms)`.
 * No toca la frase del usuario; si no hay coincidencias nuevas, la deja igual.
 */
export function glossPrompt(text) {
  const original = (text ?? '').trim();
  if (!original) return original;
  const haystack = plain(original);
  const terms = [];
  const seen = new Set();
  const add = (term) => {
    const key = term.toLowerCase();
    if (!term || seen.has(key) || haystack.includes(key)) return;
    seen.add(key);
    terms.push(term);
  };
  for (const { re, en, without } of GLOSSARY) {
    const match = re.exec(original);
    if (!match) continue;
    if (isNegated(original, match.index)) {
      // Negada: solo la forma contraria; si no la tiene, no se añade nada.
      add(without ?? '');
    } else {
      add(en);
    }
  }
  if (terms.length === 0) return original;
  return `${original} (${terms.join(', ')})`;
}
