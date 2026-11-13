import test from 'node:test';
import assert from 'node:assert/strict';

import {
  emptyPattern, PATTERN_LABELS, patternCellTarget, patternCheckLabel, patternHits, patternPayload,
  patternSummary, togglePatternCell,
} from './remix_pattern.js';

const INSTRUMENTS = ['kick', 'snare', 'hihat', 'clap'];

test('el platillo y las palmas conservan identidades distintas', () => {
  assert.equal(PATTERN_LABELS.cymbal, 'PLATILLO');
  assert.equal(PATTERN_LABELS.clap, 'PALMAS');
});

test('sin resolución declarada no se fabrica una rejilla de dieciséis pasos', () => {
  assert.equal(emptyPattern(['kick']).kick.length, 0);
});

test('un patrón vacío tiene una fila por instrumento', () => {
  const pattern = emptyPattern(INSTRUMENTS, 16);
  assert.deepEqual(Object.keys(pattern), INSTRUMENTS);
  assert.ok(Object.values(pattern).every((row) => row.length === 16 && row.every((on) => on === false)));
});

test('cambiar una celda no muta el patrón anterior', () => {
  const pattern = emptyPattern(INSTRUMENTS, 16);
  const changed = togglePatternCell(pattern, 'kick', 0);
  assert.equal(pattern.kick[0], false);
  assert.equal(changed.kick[0], true);
  assert.equal(changed.snare[0], false);
});

test('una celda fuera de la fila no cambia nada', () => {
  const pattern = emptyPattern(INSTRUMENTS, 16);
  assert.equal(togglePatternCell(pattern, 'kick', 99), pattern);
  assert.equal(togglePatternCell(pattern, 'tambor', 0), pattern);
});

test('se cuentan los golpes marcados', () => {
  const pattern = emptyPattern(INSTRUMENTS, 16);
  const once = togglePatternCell(pattern, 'kick', 0);
  const twice = togglePatternCell(once, 'snare', 4);
  assert.equal(patternHits(twice), 2);
  assert.equal(patternHits(pattern), 0);
});

test('un patrón sin golpes no viaja al servidor', () => {
  assert.equal(patternPayload(emptyPattern(INSTRUMENTS, 16)), null);
  assert.equal(patternPayload(null), null);
  const pattern = togglePatternCell(emptyPattern(INSTRUMENTS, 16), 'kick', 0);
  assert.deepEqual(patternPayload(pattern).kick.length, 16);
});

test('el resumen dice cuántos golpes hay', () => {
  assert.equal(patternSummary(emptyPattern(INSTRUMENTS, 16)), 'vacío');
  const one = togglePatternCell(emptyPattern(INSTRUMENTS, 16), 'kick', 0);
  assert.equal(patternSummary(one), '1 golpe');
  const two = togglePatternCell(one, 'snare', 0);
  assert.equal(patternSummary(two), '2 golpes');
});

test('la frase de la verificación cuenta lo acertado y lo fallado', () => {
  assert.match(patternCheckLabel({ measured: true, marked: 4, hit: [1, 5], missed: [9, 13] }),
    /2 de 4 golpes donde marcaste; fallaron los pasos 9, 13\./);
  assert.match(patternCheckLabel({ measured: true, marked: 2, hit: [1, 5], missed: [] }),
    /2 de 2 golpes donde marcaste\./);
  assert.equal(patternCheckLabel({ measured: false, reason: 'Sin patrón.' }), 'Sin patrón.');
  assert.equal(patternCheckLabel(null), null);
});

test('la medición nueva informa de todos los compases y conserva lectura de fichas antiguas', () => {
  assert.equal(patternCheckLabel({ measured: true, expected_count: 16, hit_count: 4, missed_count: 12 }),
    '4 de 16 golpes de bombo donde marcaste; faltaron 12.');
});

test('el teclado recorre las celdas sin activarlas ni salirse de la rejilla', () => {
  assert.deepEqual(patternCellTarget('ArrowRight', 0, 0, 4, 16), { row: 0, column: 1 });
  assert.deepEqual(patternCellTarget('ArrowLeft', 0, 0, 4, 16), { row: 0, column: 0 });
  assert.deepEqual(patternCellTarget('ArrowDown', 0, 6, 4, 16), { row: 1, column: 6 });
  assert.deepEqual(patternCellTarget('End', 1, 6, 4, 16, true), { row: 3, column: 15 });
  assert.equal(patternCellTarget(' ', 0, 0, 4, 16), null);
  assert.equal(patternCellTarget('ArrowRight', 0, 0, 0, 0), null);
});
