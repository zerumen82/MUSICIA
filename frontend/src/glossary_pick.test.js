import test from 'node:test';
import assert from 'node:assert/strict';
import { applyGlossaryPick, applyModelTerm, ensureModelTerm, findStyle, joinStyleAndTracks, joinTrackPrompts, sinBpmEnFrase, stylesForQuery } from './glossary_pick.js';

const GABBER = {
  genre: 'gabber',
  text: 'A track with heavily distorted, punchy kick drums, aggressive snare, a pounding relentless rhythm, dark energy and a raw, aggressive mix',
};

const GABBER_STYLE = {
  name: 'hardcore holandes',
  genre: 'gabber',
  bpm: 180,
  text: GABBER.text,
  keys: ['dutch hardcore', 'gabber', 'hardcore techno', 'hardcore'],
};

test('un estilo del modelo entra como término suyo, no como párrafo', () => {
  assert.equal(applyModelTerm('', 'gabber'), 'A track with gabber');
  assert.equal(applyModelTerm('gabber', 'gabber'), 'A track with gabber');
  assert.equal(applyModelTerm('flautas medievales', 'gabber'), 'A track with gabber');
});

test('otro término del modelo se suma en la misma caption', () => {
  const next = applyModelTerm('A track with gabber', 'medieval');
  assert.equal(next, 'A track with gabber · medieval');
  assert.equal(applyModelTerm(next, 'flute'), 'A track with gabber · medieval · flute');
});

test('una línea con comas entra entera y al pulsarla otra vez sale entera', () => {
  const line = '1960s pop, doo-wop';
  const once = applyModelTerm('', line);
  assert.equal(once, `A track with ${line}`);
  assert.equal(applyModelTerm(once, 'medieval'), `A track with ${line} · medieval`);
  assert.equal(applyModelTerm(once, line), '');
});

test('las pistas en transformar se juntan y una vacía no inventa texto', () => {
  const drums = applyModelTerm('', 'gabber, hardstyle, hardcore');
  const bass = 'distorted kicks';
  assert.equal(
    joinTrackPrompts([drums, '', '   ', bass]),
    'A track with gabber, hardstyle, hardcore · distorted kicks',
  );
  assert.equal(joinTrackPrompts(['', '  ']), '');
  assert.equal(joinStyleAndTracks('A track with gabber', ['', 'distorted kicks']), 'A track with gabber · distorted kicks');
  assert.equal(joinStyleAndTracks('hardstyle with distorted kicks', ['']), 'hardstyle with distorted kicks');
  assert.equal(
    joinTrackPrompts([drums, 'A track with gabber, hardstyle, hardcore · fast double kick']),
    'A track with gabber, hardstyle, hardcore · fast double kick',
  );
});

test('volver a pulsarlo quita solo ese término', () => {
  const mixed = 'A track with gabber · medieval';
  assert.equal(applyModelTerm(mixed, 'gabber'), 'A track with medieval');
  assert.equal(applyModelTerm('A track with gabber', 'gabber'), '');
});

test('la búsqueda gabber encuentra ese estilo y no lista nada en vacío', () => {
  assert.equal(findStyle([GABBER_STYLE], 'gabber')?.bpm, 180);
  assert.equal(findStyle([GABBER_STYLE], 'hardcore gabber'), null);
  assert.deepEqual(stylesForQuery([GABBER_STYLE], ''), []);
  assert.equal(stylesForQuery([GABBER_STYLE], 'gabber')[0].name, 'hardcore holandes');
  assert.equal(stylesForQuery([GABBER_STYLE], 'hardcore gabber')[0].name, 'hardcore holandes');
  assert.equal(stylesForQuery([GABBER_STYLE], 'techno').length, 0);
});

test('la voz añade su término y no lo quita si ya está', () => {
  assert.equal(ensureModelTerm('A track with gabber', 'female vocal'), 'A track with gabber · female vocal');
  assert.equal(
    ensureModelTerm('A track with gabber · female vocal', 'female vocal'),
    'A track with gabber · female vocal',
  );
});

test('el tempo no se queda escrito en la frase', () => {
  assert.equal(sinBpmEnFrase('A track with gabber, 180 bpm'), 'A track with gabber');
  assert.equal(sinBpmEnFrase('A track with gabber · 180 bpm'), 'A track with gabber');
});

test('una palabra del vocabulario entra en la misma caption', () => {
  assert.equal(applyGlossaryPick('A track with gabber', { genre: 'breakcore' }), 'A track with gabber · breakcore');
  assert.equal(applyGlossaryPick('A track with gabber · breakcore', { genre: 'breakcore' }), 'A track with gabber');
});
