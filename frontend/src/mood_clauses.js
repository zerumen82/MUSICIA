/**
 * Ánimo de CREAR → cláusulas que ya están en backend/style_catalog.json.
 * No se inventa prosa. Una cláusula que nombra el tempo no se envía si el
 * BPM ya está en su control. No se manda el párrafo ambient («no drums»)
 * ni «driving drums as the lead of the track».
 */

const CLAUSES = {
  nocturno: ['a dark aggressive energy'],
  oscuro: ['a dark aggressive energy'],
  energico: ['a relentless driving rhythm'],
  melancolico: ['a melancholic, nostalgic emotional mood'],
  cinematico: ['layered, evolving textures', 'an epic, euphoric emotional lift throughout'],
  alegre: ['a bright, upbeat energy'],
  epico: ['an epic, euphoric emotional lift throughout'],
  tranquilo: ['a slow, laid-back tempo'],
  chill: ['a slow, laid-back tempo'],
};

const TEMPO_CLAUSES = new Set([
  'a slow, laid-back tempo',
  'a fast, energetic tempo',
]);

export function allMoodClauses() {
  return [...new Set(Object.values(CLAUSES).flat())];
}

/** Cláusulas que entran en la caption. Vacío si el ánimo no está elegido. */
export function moodClauses(moodId, bpm) {
  const clauses = CLAUSES[moodId] ?? [];
  const hasBpm = bpm != null && bpm !== '';
  if (!hasBpm) return [...clauses];
  return clauses.filter((clause) => !TEMPO_CLAUSES.has(clause));
}

/** Texto del desplegable: lo que se añade, y cuándo el BPM lo impide. */
export function moodTooltip(moodId) {
  const clauses = CLAUSES[moodId] ?? [];
  if (!clauses.length) return '';
  const listed = clauses.map((clause) => `«${clause}»`).join(' · ');
  const tempo = clauses.some((clause) => TEMPO_CLAUSES.has(clause));
  return tempo
    ? `Se añade: ${listed}. Si hay BPM, no se añade: el tempo va en su control.`
    : `Se añade: ${listed}`;
}
