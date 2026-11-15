import test from 'node:test';
import assert from 'node:assert/strict';
import { identifyReading } from './identify_reading.js';

test('IDENTIFY enseña la descripción del modelo y el género del glosario', () => {
  assert.equal(identifyReading({ description: 'hard gabber con kick distorsionado', glossary_genre: 'gabber, hardstyle, hardcore', genres: 'otra cosa' }), 'hard gabber con kick distorsionado · Género: gabber, hardstyle, hardcore');
  assert.equal(identifyReading({ description: '', glossary_genre: null, genres: 'piano contemplativo' }), 'No está en el glosario: piano contemplativo');
  assert.equal(identifyReading({}), 'El modelo no devolvió un género del glosario');
});
