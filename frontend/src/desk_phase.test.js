import test from 'node:test';
import assert from 'node:assert/strict';
import { ANALYSIS_FALLBACK, REMIX_FALLBACK, deskPhase, movingPercent } from './desk_phase.js';

test('el último log del motor no entra en la mesa', () => {
  const logs = [
    'Extracting Audio Codes...',
    'Starting Deep Analysis...',
    'Waiting',
    '12:04:01 | INFO | Sampling 12/50',
    'Sampling:  23%|██▎       | 12/50 [00:04<00:15,  2.41it/s]',
    '12:04:01 | INFO | Extracting Audio Codes...\nStarting Deep Analysis...',
    'Traceback (most recent call last):\n  File "handler.py", line 3',
  ];
  for (const log of logs) {
    assert.equal(deskPhase(log, REMIX_FALLBACK), REMIX_FALLBACK);
    assert.equal(deskPhase(log, ANALYSIS_FALLBACK), ANALYSIS_FALLBACK);
  }
});

test('las frases propias sí se enseñan', () => {
  assert.equal(deskPhase('En cola', REMIX_FALLBACK), 'En cola');
  assert.equal(deskPhase('Transformando el audio original con repaint', REMIX_FALLBACK), 'Transformando el audio original con repaint');
  assert.equal(deskPhase('Exportando la variante 2', REMIX_FALLBACK), 'Exportando la variante 2');
  assert.equal(deskPhase('Montando la pista transformada de la variante 1', REMIX_FALLBACK), 'Montando la pista transformada de la variante 1');
  assert.equal(deskPhase('El modelo local analiza el audio', ANALYSIS_FALLBACK), 'El modelo local analiza el audio');
  assert.equal(deskPhase('  Rehaciendo el audio \n', REMIX_FALLBACK), REMIX_FALLBACK);
});

test('una fase vacía o desconocida usa el recambio', () => {
  assert.equal(deskPhase('', REMIX_FALLBACK), REMIX_FALLBACK);
  assert.equal(deskPhase(null, ANALYSIS_FALLBACK), ANALYSIS_FALLBACK);
  assert.equal(deskPhase('Modelo del motor: sft (guidance 9, 50 pasos).', REMIX_FALLBACK), REMIX_FALLBACK);
});

test('el 80 % de la conversión no es un avance', () => {
  assert.equal(movingPercent('Convirtiendo a audio', 0.8), null);
  assert.equal(movingPercent('Convirtiendo a audio final', 0.8), null);
  assert.equal(movingPercent('Error', 0.8), null);
  assert.equal(movingPercent('Error de análisis', 0.5), null);
  assert.equal(movingPercent('Rehaciendo el audio', 0.4), 40);
  assert.equal(movingPercent('Sintetizando el audio (difusión por pasos)', 0.5), 50);
  assert.equal(movingPercent('Rehaciendo el audio', 1), null);
  assert.equal(movingPercent('Rehaciendo el audio', 0), null);
  assert.equal(movingPercent('Decoding audio...', 0.8), null);
});
