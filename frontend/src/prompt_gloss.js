/**
 * Caption literal compartido por las vistas y los envíos.
 *
 * La antigua glosa de palabras añadía términos sin conservar las relaciones
 * («contrabajo» acababa reforzando doble bombo; «potente» se asignaba a voz).
 * Conservamos el nombre exportado para los consumidores existentes, pero
 * no presentamos un catálogo/regex como traductor semántico. Las entradas
 * del glosario y los chips solo se añaden por selección explícita.
 */
export function glossPrompt(prompt) {
  return (prompt || '').trim();
}
