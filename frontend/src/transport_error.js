/**
 * Corte del cliente: la petición no obtuvo respuesta HTTP.
 * No incluye un 422 del traductor ni un fallo que el motor sí escribió.
 */
const CLIENT_CUT = /^(?:La API no contesta\.|La API tardó demasiado en contestar\.|timeout of \d+ms exceeded|timeout exceeded|Network Error|ECONNABORTED|ECONNREFUSED)$/i

export const isTransportBlip = (message) => CLIENT_CUT.test(message ?? '')

/**
 * Solo para seguir sondeando un trabajo ya lanzado.
 * No sirve para borrar el resultado de pulsar REMIX.
 */
export const isEnginePollBlip = (message) =>
  /no responde|no contesta|respuesta ilegible|timeout of \d+ms exceeded|timeout exceeded|tardó demasiado|Network Error|ECONNABORTED|ECONNREFUSED/i.test(message ?? '')

/** Null si el texto es un corte del cliente. Un fallo real se conserva. */
export const actionError = (message) => (isTransportBlip(message) ? null : (message || null))

/** Un corte de cliente que sigue en pantalla cuando la API ya contesta tiene que quitarse. */
export const staleTransportError = (message, apiOk) =>
  Boolean(message) && isTransportBlip(message) && apiOk === true
