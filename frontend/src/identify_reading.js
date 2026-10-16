/** Lo que se enseña tras IDENTIFY. El género solo si el backend lo confirmó en el glosario. */
export function identifyReading(result) {
  const genre = String(result?.glossary_genre ?? '').trim();
  if (genre) return genre;
  const raw = String(result?.genres ?? '').trim();
  if (raw) return `No está en el glosario: ${raw}`;
  return 'El modelo no devolvió un género del glosario';
}
