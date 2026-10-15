import test from 'node:test';
import assert from 'node:assert/strict';
import { arrowDirection, nudgeInterval, nudgePosition } from './timeline_nudge.js';

test('las flechas del teclado mueven el inicio sin pisar el final', () => {
  assert.equal(arrowDirection('ArrowRight'), 1);
  assert.equal(arrowDirection('Right'), 1);
  assert.equal(arrowDirection('ArrowLeft'), -1);
  assert.equal(arrowDirection('Enter'), 0);
  assert.deepEqual(nudgeInterval({ start: '6', end: '18', duration: 30, edge: 'start', direction: 1, step: 1 }), { start: 7, end: 18 });
  assert.equal(nudgeInterval({ start: 6, end: 18, duration: 30, edge: 'start', direction: 1, step: 20 }), null);
  assert.equal(nudgeInterval({ start: 0, end: 18, duration: 30, edge: 'start', direction: -1, step: 1 }), null);
});

test('el final explicito se conserva y el final abierto sigue hasta la duración', () => {
  assert.deepEqual(nudgeInterval({ start: 6, end: null, duration: 30, edge: 'start', direction: 1, step: 1 }), { start: 7, end: null });
  assert.deepEqual(nudgeInterval({ start: 6, end: 18, duration: 30, edge: 'end', direction: -1, step: 1 }), { start: 6, end: 17 });
  assert.deepEqual(nudgeInterval({ start: 6, end: 18, duration: 30, edge: 'end', direction: 1, step: 1 }), { start: 6, end: 19 });
  assert.equal(nudgeInterval({ start: 6, end: 30, duration: 30, edge: 'end', direction: 1, step: 1 }), null);
});

test('sin paso configurado no se inventa un desplazamiento', () => {
  assert.equal(nudgeInterval({ start: 6, end: 18, duration: 30, edge: 'start', direction: 1, step: undefined }), null);
  assert.equal(nudgePosition(10, { start: 6, end: 18, valid: true }, 1, 0), null);
  assert.equal(nudgePosition(10, { start: 6, end: 18, valid: true }, 1, 1), 11);
  assert.equal(nudgePosition(17.5, { start: 6, end: 18, valid: true }, 1, 1), null);
});
