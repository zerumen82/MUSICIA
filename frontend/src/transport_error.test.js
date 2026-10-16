import { test } from 'node:test'
import assert from 'node:assert/strict'
import { actionError, isEnginePollBlip, isTransportBlip, staleTransportError } from './transport_error.js'

test('un corte del cliente no se guarda como fallo de la acción', () => {
  assert.equal(isTransportBlip('La API no contesta.'), true)
  assert.equal(isTransportBlip('La API tardó demasiado en contestar.'), true)
  assert.equal(isTransportBlip('timeout of 30000ms exceeded'), true)
  assert.equal(isTransportBlip('timeout exceeded'), true)
  assert.equal(isTransportBlip('Network Error'), true)
  assert.equal(isTransportBlip('ECONNABORTED'), true)
  assert.equal(isTransportBlip('ECONNREFUSED'), true)
  assert.equal(isTransportBlip('El motor citó Network Error en el detalle'), false)
  assert.equal(actionError('La API no contesta.'), null)
  assert.equal(actionError('Elige un género o escribe una descripción'), 'Elige un género o escribe una descripción')
})

test('el corte se quita cuando la API vuelve a contestar', () => {
  assert.equal(staleTransportError('La API no contesta.', true), true)
  assert.equal(staleTransportError('La API no contesta.', false), false)
  assert.equal(staleTransportError('El remix no tiene pulso', true), false)
})

test('un fallo real del remix no se trata como corte de red', () => {
  const kept = [
    'El traductor local tardó demasiado. No se envía el estilo sin pasarlo al inglés.',
    'El motor ACE-Step no responde (/health): ReadError',
    'Respuesta ilegible del motor (/health): bad',
  ]
  for (const message of kept) {
    assert.equal(isTransportBlip(message), false)
    assert.equal(actionError(message), message)
    assert.equal(staleTransportError(message, true), false)
    assert.equal(isEnginePollBlip(message), true)
  }
})
