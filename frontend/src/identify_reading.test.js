import test from 'node:test';
import assert from 'node:assert/strict';
import { formatClock, identifyCopyText, identifyModelPrompt, identifyReading, identifyScopeReading, markedRegionReading } from './identify_reading.js';

test('IDENTIFY enseña la descripción del modelo y el género del glosario', () => {
  const withGenre = { description: 'hard gabber con kick distorsionado', glossary_genre: 'gabber, hardstyle, hardcore', genres: 'otra cosa' };
  assert.equal(identifyReading(withGenre), 'hard gabber con kick distorsionado · Género: gabber, hardstyle, hardcore');
  assert.equal(identifyCopyText(withGenre), 'hard gabber con kick distorsionado');
  assert.equal(identifyReading({ description: '', glossary_genre: null, genres: 'piano contemplativo' }), 'No está en el glosario: piano contemplativo');
  assert.equal(identifyCopyText({ description: '', glossary_genre: null, genres: 'piano contemplativo' }), 'piano contemplativo');
  assert.equal(identifyReading({}), 'El modelo no devolvió un género del glosario');
  assert.equal(identifyCopyText({}), 'El modelo no devolvió un género del glosario');
});

test('IDENTIFY declara ANTES de la descripción qué parte se describió', () => {
  const range = { start: 30, end: 90, source_duration: 189, truncated: false };
  assert.equal(
    identifyScopeReading({ analysis_range: range }, { start: 30, end: 90 }),
    'TRAMO ELEGIDO 0:30–1:30 · DESCRIPCIÓN DE ESE TROZO',
  );
  assert.equal(
    identifyScopeReading({ analysis_range: { start: 0, end: 240, source_duration: 600, truncated: true } }, { start: 0, end: 600 }),
    'TRAMO ELEGIDO 0:00–4:00 · DESCRIPCIÓN DE ESE TROZO · recortado al máximo',
  );
  assert.equal(
    identifyScopeReading({ analysis_range: { start: 0, end: 189, source_duration: 189, truncated: false } }, null),
    'TEMA COMPLETO · OÍDO 0:00–3:09 de 3:09',
  );
  assert.equal(identifyScopeReading({}, { start: 0, end: 10 }), '');
});

test('La onda marca el tramo elegido y el reloj formatea m:ss', () => {
  assert.equal(markedRegionReading({ start: 30, end: 90 }), 'TRAMO MARCADO 0:30–1:30 · IDENTIFY describirá ese trozo');
  assert.equal(markedRegionReading({ start: 0, end: null }), 'TRAMO MARCADO 0:00–FINAL · IDENTIFY describirá ese trozo');
  assert.equal(markedRegionReading(null), null);
  assert.equal(formatClock(189), '3:09');
});

test('COPIAR PARA EL MODELO monta el prompt con el género del glosario delante', () => {
  const result = { description: 'An aggressive, driving synth arpeggio with a gritty texture.', glossary_genre: 'gabber, hardstyle, hardcore', genres: 'gabber techno' };
  assert.equal(identifyModelPrompt(result), 'gabber, hardstyle, hardcore. An aggressive, driving synth arpeggio with a gritty texture.');
  // Sin género del glosario usa los géneros brutos del motor, nunca etiquetas de interfaz.
  assert.equal(identifyModelPrompt({ description: 'Desc.', glossary_genre: '', genres: 'italo-disco' }), 'italo-disco. Desc.');
  // Sin descripción, el género solo; sin nada, vacío (el botón no copia mentiras).
  assert.equal(identifyModelPrompt({ glossary_genre: 'gabber', description: '' }), 'gabber');
  assert.equal(identifyModelPrompt({}), '');
});
