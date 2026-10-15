import test from 'node:test';
import assert from 'node:assert/strict';
import { toggleVariantText, VARIANTS } from './variants.js';

const energia = VARIANTS.find((item) => item.id === 'energia').add;

test('la variante entra en la misma caption y sale entera aunque lleve comas', () => {
  const once = toggleVariantText('A track with gabber', energia);
  assert.equal(once, `A track with gabber · ${energia}`);
  assert.equal(toggleVariantText(once, energia), 'A track with gabber');
});
