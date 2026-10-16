/** El ánimo elegido añade una cláusula del catálogo, no una frase nueva. */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { ensureModelTerm } from './glossary_pick.js';
import { allMoodClauses, moodClauses, moodTooltip } from './mood_clauses.js';

function withMood(prompt, mood, bpm) {
  let free = String(prompt ?? '').trim();
  for (const clause of moodClauses(mood, bpm)) free = ensureModelTerm(free, clause);
  return free;
}

test('las cláusulas son las del catálogo y no pelean con el bombo', () => {
  const catalog = JSON.parse(readFileSync(new URL('../../backend/style_catalog.json', import.meta.url), 'utf8'));
  const known = new Set(catalog.modifiers.map((item) => item.clause));
  const forbidden = [
    'driving drums as the lead of the track',
    'a fast, energetic tempo',
    'A soft track with evolving synth pads, no drums and a spacious, atmospheric, meditative soundscape',
  ];
  for (const clause of allMoodClauses()) {
    assert.equal(known.has(clause), true, clause);
    assert.equal(forbidden.includes(clause), false, clause);
  }
});

test('oscuro y enérgico entran; el tempo lento no entra si hay BPM', () => {
  assert.equal(
    withMood('gabber', 'oscuro', 170),
    'A track with gabber · a dark aggressive energy',
  );
  assert.equal(
    withMood('gabber', 'energico', 180),
    'A track with gabber · a relentless driving rhythm',
  );
  assert.equal(withMood('gabber', 'tranquilo', 170), 'gabber');
  assert.equal(withMood('gabber', 'chill', 90), 'gabber');
  assert.equal(
    withMood('gabber', 'tranquilo', null),
    'A track with gabber · a slow, laid-back tempo',
  );
  assert.equal(
    withMood('', 'cinematico', null),
    'A track with layered, evolving textures · an epic, euphoric emotional lift throughout',
  );
  assert.equal(
    withMood('A track with gabber · a dark aggressive energy', 'oscuro', null),
    'A track with gabber · a dark aggressive energy',
  );
  assert.equal(withMood('gabber', null, null), 'gabber');
});

test('cada ánimo de CREAR tiene cláusula y el aviso dice lo que se añade', () => {
  const source = readFileSync(new URL('./components/Composer.jsx', import.meta.url), 'utf8');
  const block = source.slice(source.indexOf('const MOODS'), source.indexOf('const BPM_PRESETS'));
  const ids = [...block.matchAll(/id: '([^']+)'/g)].map((match) => match[1]);
  assert.ok(ids.length >= 8);
  for (const id of ids) {
    assert.ok(moodClauses(id, null).length > 0, id);
    assert.match(moodTooltip(id), /^Se añade: /);
  }
  assert.match(moodTooltip('tranquilo'), /Si hay BPM/);
  assert.doesNotMatch(moodTooltip('oscuro'), /Si hay BPM/);
});
