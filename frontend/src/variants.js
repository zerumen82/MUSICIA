/**
 * Variantes de dirección musical: reescriben el prompt con una dirección
 * clara en vez de dejar que el motor improvisé.
 *
 * Los textos están en inglés, que es el idioma de las captions de
 * entrenamiento, y pasan el mismo control de realismo que los chips
 * (`backend/test_realism.py::test_variantes_del_modelo`): cada palabra sale
 * del corpus del fabricante o del vocabulario de géneros, y cada variante
 * dispara un estilo o un modificador del catálogo. Así lo que ves en el
 * botón y lo que se añade a tu frase es el mismo idioma que viaja al motor.
 */
export const VARIANTS = [
  { id: 'energia', label: 'MORE ENERGY', add: 'high energy driving rhythm, fast and relentless tempo' },
  { id: 'calma', label: 'CALMER', add: 'quiet and spacious, slow tempo, ambient' },
  { id: 'oscura', label: 'DARKER', add: 'dark and tense, melancholic and emotional' },
  { id: 'luminosa', label: 'BRIGHTER', add: 'bright and uplifting, optimistic' },
  { id: 'acustica', label: 'ACOUSTIC', add: 'acoustic folk with guitars, strings and piano' },
  { id: 'electronica', label: 'ELECTRONIC', add: 'electronic with synthesizers, drum machine and four on the floor' },
  { id: 'orquestal', label: 'ORCHESTRAL', add: 'orchestral cinematic, strings and percussion, epic' },
  { id: 'lofi', label: 'LO-FI', add: 'lofi hip hop, soft piano and vinyl, relaxed' },
  { id: 'epica', label: 'EPIC', add: 'epic and grandiose, anthemic, layered arrangement and climax' },
  { id: 'minimal', label: 'MINIMAL', add: 'minimal arrangement with layered evolving elements' },
];

export const escapeRe = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

/** Quita una frase (y la coma que la precede) del prompt, con tolerancia a
    mayúsculas: es lo que hace «ELEGIDO» al volver a pulsarlo. */
export const removeTexto = (prompt, text) => {
  const p = prompt ?? '';
  const re = new RegExp(`(,\\s*)?${escapeRe(text)}`, 'i');
  return p.replace(re, '').replace(/,\s*,/g, ',').replace(/^[\s,]+|[\s,]+$/g, '');
};

/** Conmutador: si la variante ya está en el prompt, la quita; si no, la añade. */
export const toggleVariantText = (prompt, add) => {
  const p = (prompt ?? '').trim();
  if (p.toLowerCase().includes(add.toLowerCase())) return removeTexto(p, add);
  return p ? `${p}, ${add}` : add;
};
