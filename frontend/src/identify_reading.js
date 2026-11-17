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

/** Texto que COPIAR lleva al portapapeles: solo la descripción del modelo. */
export function identifyCopyText(result) {
  const description = String(result?.description ?? '').trim();
  if (description) return description;
  const raw = String(result?.genres ?? '').trim();
  if (raw) return raw;
  return 'El modelo no devolvió un género del glosario';
}

/** Etiqueta de contexto del análisis (análisis_range del backend): declara
 *  ANTES de la descripción qué parte se escuchó y quién lo decidió. Con tramo
 *  elegido en la onda la descripción es DE ESE TROZO; sin tramo, la elección
 *  automática (tema entero o su centro). El rango es el real del backend,
 *  nunca el pedido: si el tope lo cortó, `truncated` lo declara. */
export function identifyScopeReading(result, chosenRegion = null) {
  const range = result?.analysis_range;
  const start = Number(range?.start);
  const end = Number(range?.end);
  if (!Number.isFinite(end)) return '';
  const clock = (seconds) => {
    const total = Math.max(0, Math.round(Number(seconds) || 0));
    return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, '0')}`;
  };
  const tail = range.truncated ? ' · recortado al máximo' : '';
  const heard = `${clock(start)}–${clock(end)}`;
  if (chosenRegion) {
    return `TRAMO ELEGIDO ${heard} · DESCRIPCIÓN DE ESE TROZO${tail}`;
  }
  const total = Number(range?.source_duration);
  const whole = Number.isFinite(total) ? ` de ${clock(total)}` : '';
  return `TEMA COMPLETO · OÍDO ${heard}${whole}${tail}`;
}
