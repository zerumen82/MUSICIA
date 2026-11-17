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

/** Prompt en formato del modelo para pegar y generar: primero el género en el
 *  vocabulario del glosario del motor (lo que el motor entiende de estilo) y
 *  después la descripción, que es el formato caption nativo del propio motor.
 *  No se inventa nada: ambos textos salen del análisis. */
export function identifyModelPrompt(result) {
  const genre = String(result?.glossary_genre ?? '').trim();
  const raw = String(result?.genres ?? '').trim();
  const description = String(result?.description ?? '').trim();
  const head = genre || raw;
  if (head && description) return `${head}. ${description}`;
  return description || head;
}

/** Reloj m:ss para etiquetas de tramo. */
export function formatClock(seconds) {
  const total = Math.max(0, Math.round(Number(seconds) || 0));
  return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, '0')}`;
}

/** Marca visible bajo la onda: declara que hay un tramo elegido y que
 *  IDENTIFY describirá ESE trozo. Sin tramo devuelve null (automático). */
export function markedRegionReading(region) {
  if (!region) return null;
  const start = formatClock(region.start);
  const end = region.end == null ? 'FINAL' : formatClock(region.end);
  return `TRAMO MARCADO ${start}–${end} · IDENTIFY describirá ese trozo`;
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
  const tail = range.truncated ? ' · recortado al máximo' : '';
  const heard = `${formatClock(start)}–${formatClock(end)}`;
  if (chosenRegion) {
    return `TRAMO ELEGIDO ${heard} · DESCRIPCIÓN DE ESE TROZO${tail}`;
  }
  const total = Number(range?.source_duration);
  const whole = Number.isFinite(total) ? ` de ${formatClock(total)}` : '';
  return `TEMA COMPLETO · OÍDO ${heard}${whole}${tail}`;
}
