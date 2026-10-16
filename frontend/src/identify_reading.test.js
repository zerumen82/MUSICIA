import test from 'node:test';
import assert from 'node:assert/strict';
import { identifyReading } from './identify_reading.js';

test('IDENTIFY enseña la línea del glosario y no disfraza un texto ajeno', () => {
  assert.equal(identifyReading({ glossary_genre: 'gabber, hardstyle, hardcore', genres: 'otra cosa' }), 'gabber, hardstyle, hardcore');
  assert.equal(identifyReading({ glossary_genre: null, genres: 'piano contemplativo' }), 'No está en el glosario: piano contemplativo');
  assert.equal(identifyReading({}), 'El modelo no devolvió un género del glosario');
});
