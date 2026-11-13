/**
 * De dónde sale el material de un remix (spec/02 [R20.C]).
 *
 * Sin stems del usuario el audio se separa de una canción terminada: eso es
 * un bootleg, no un remix con material propio. La app no autoriza ni
 * publica nada: la diferencia es de derechos sobre el material y sobre la
 * publicación, no de herramienta.
 */

export const MATERIAL_ORIGIN_MIX = 'separado_de_mezcla';
/** Material propio del usuario: stems que subió (spec/02 [R20.B]). */
export const MATERIAL_ORIGIN_STEMS = 'stems_del_usuario';

/** La línea de la entrada de REMIX: qué pasa con el material, sin jerga. */
export const MATERIAL_ENTRY_NOTE = 'Sin stems propios el material sale de separar una canción terminada: eso es un bootleg, no un remix con material real. El patrón de batería marca la intención rítmica y el modelo crea a partir de ella.';

/** La frase legible del origen que registró la ficha de la salida. */
export function materialOriginLabel(origin) {
  if (origin === MATERIAL_ORIGIN_STEMS) {
    return 'Material tuyo: stems que subiste. Es un remix con material real.';
  }
  if (origin === MATERIAL_ORIGIN_MIX) {
    return 'Material separado de una canción terminada: es un bootleg.';
  }
  return null;
}
