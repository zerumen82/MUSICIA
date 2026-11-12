/**
 * De dónde sale el material de un remix (spec/02 [R20.C]).
 *
 * Sin stems del usuario el audio se separa de una canción terminada: eso es
 * un bootleg, no un remix con material propio. La app no autoriza ni
 * publica nada: la diferencia es de derechos sobre el material y sobre la
 * publicación, no de herramienta.
 */

export const MATERIAL_ORIGIN_MIX = 'separado_de_mezcla';
export const MATERIAL_ORIGIN_STEMS = 'stems_del_usuario';

/** La línea de la entrada de REMIX: qué pasa con el material, sin jerga. */
export const MATERIAL_ENTRY_NOTE = 'El material sale de separar la mezcla que subes: es un bootleg. Con stems propios sería un remix con material real.';

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
