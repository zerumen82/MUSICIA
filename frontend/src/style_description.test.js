import test from 'node:test';
import assert from 'node:assert/strict';
import { descriptionFor, descriptionSourceUrl } from './style_description.js';

test('una etiqueta sin ficha no hereda la descripción de una subfrase', () => {
  const jazz = { text: 'An existing catalog description', provenance: { label: 'Musicia' } };
  assert.equal(descriptionFor({ jazz }, 'acid jazz'), null);
  assert.equal(descriptionFor({ jazz }, 'jazz'), jazz);
  assert.equal(descriptionFor({}, 'jazz'), null);
  assert.equal(descriptionFor({ jazz: { text: '  ' } }, 'jazz'), null);
  assert.equal(descriptionFor(Object.create({ jazz }), 'jazz'), null);
});

test('las fuentes permiten enlaces web y rechazan código, archivos y rutas relativas', () => {
  assert.equal(descriptionSourceUrl('https://example.org/source'), 'https://example.org/source');
  assert.equal(descriptionSourceUrl('http://example.org/source'), 'http://example.org/source');
  for (const value of ['javascript:alert(1)', 'data:text/html,source', 'file:///C:/source', '/source', undefined]) {
    assert.equal(descriptionSourceUrl(value), null);
  }
});
