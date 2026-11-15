/** Lo que se enseña tras IDENTIFY. El modelo describe la canción y, si el
 *  género se confirmó en el glosario, se muestra también. */
export function identifyReading(result) {
  const description = String(result?.description ?? '').trim();
  const genre = String(result?.glossary_genre ?? '').trim();
  const raw = String(result?.genres ?? '').trim();
  const parts = [];
  if (description) parts.push(description);
  if (genre) parts.push(`Género: ${genre}`);
  else if (raw) parts.push(`No está en el glosario: ${raw}`);
  if (!parts.length) return 'El modelo no devolvió un género del glosario';
  return parts.join(' · ');
}
