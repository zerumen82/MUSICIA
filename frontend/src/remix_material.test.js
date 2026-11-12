import test from 'node:test';
import assert from 'node:assert/strict';
import { MATERIAL_ENTRY_NOTE, MATERIAL_ORIGIN_MIX, MATERIAL_ORIGIN_STEMS, materialOriginLabel } from './remix_material.js';

test('la entrada de REMIX declara el origen del material', () => {
  assert.match(MATERIAL_ENTRY_NOTE, /bootleg/);
  assert.match(MATERIAL_ENTRY_NOTE, /stems propios/);
});

test('la ficha se lee en palabras, no en claves', () => {
  assert.match(materialOriginLabel(MATERIAL_ORIGIN_MIX), /bootleg/);
  assert.match(materialOriginLabel(MATERIAL_ORIGIN_STEMS), /stems/);
  assert.equal(materialOriginLabel('otra_cosa'), null);
  assert.equal(materialOriginLabel(null), null);
});
