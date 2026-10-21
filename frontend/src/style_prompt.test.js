import test from 'node:test';
import assert from 'node:assert/strict';
import { chooseStyle, emptyStyleSelection, stylePromptKey, stylePromptRequest, stylePromptStatus } from './style_prompt.js';

test('principal y matices tienen roles explícitos sin promover el primero', () => {
  const influence = chooseStyle(emptyStyleSelection(), 'trance', 'influence');
  assert.equal(influence.main_style, null);
  assert.deepEqual(influence.influence_styles, ['trance']);
  const main = chooseStyle(influence, 'gabber', 'main');
  assert.equal(main.main_style, 'gabber');
  assert.deepEqual(main.influence_styles, ['trance']);
  assert.equal(chooseStyle(main, 'gabber', 'main').main_style, null);
  assert.deepEqual(chooseStyle(main, 'trance', 'influence').influence_styles, []);
  const promoted = chooseStyle(main, 'trance', 'main');
  assert.equal(promoted.main_style, 'trance');
  assert.deepEqual(promoted.influence_styles, []);
});

test('preparar conserva detalles y quitar descripción conserva los roles', () => {
  const selection = chooseStyle(chooseStyle(emptyStyleSelection(), 'gabber', 'main'), 'trance', 'influence');
  const original = stylePromptRequest('sin voz y sin guitarras', selection);
  const without = stylePromptRequest('sin voz y sin guitarras', { ...selection, include_descriptions: false });
  assert.equal(without.prompt, original.prompt);
  assert.equal(without.main_style, original.main_style);
  assert.deepEqual(without.influence_styles, original.influence_styles);
  assert.equal(without.include_descriptions, false);
  assert.notEqual(stylePromptKey(original), stylePromptKey(without));
  assert.equal(original.bpm, null);
});

test('la respuesta anterior no habilita envío durante debounce ni tras cambiar roles', () => {
  const original = stylePromptRequest('sin voz', chooseStyle(emptyStyleSelection(), 'techno', 'main'));
  const result = { enhanced: 'Main style: techno. sin voz', warnings: ['aviso'] };
  const answer = { key: stylePromptKey(original), result };
  assert.equal(stylePromptStatus(original, answer).effectivePrompt, result.enhanced);
  assert.equal(stylePromptStatus(original, answer).ready, true);
  for (const next of [
    { ...original, prompt: 'sin voz y sin bombo' },
    { ...original, main_style: 'gabber' },
    { ...original, influence_styles: ['trance'] },
    { ...original, include_descriptions: false },
  ]) {
    const status = stylePromptStatus(next, answer);
    assert.equal(status.ready, false);
    assert.equal(status.effectivePrompt, '');
    assert.equal(status.pending, true);
  }
});

test('error real y matices sin principal bloquean; campo vacío no bloquea pistas', () => {
  const request = stylePromptRequest('sin voz');
  const failed = stylePromptStatus(request, { key: stylePromptKey(request), error: 'HTTP 503' });
  assert.equal(failed.error, 'HTTP 503');
  assert.equal(failed.ready, false);
  assert.equal(failed.pending, false);
  const invalid = stylePromptStatus(stylePromptRequest('', chooseStyle(emptyStyleSelection(), 'trance', 'influence')));
  assert.equal(invalid.ready, false);
  assert.match(invalid.error, /principal/);
  assert.equal(stylePromptStatus(stylePromptRequest('')).ready, true);
});

test('cada nueva preparación usa los detalles y nunca reanaliza la prosa derivada', () => {
  const selection = chooseStyle(emptyStyleSelection(), 'techno', 'main');
  const raw = 'sin guitarras';
  const request = stylePromptRequest(raw, selection);
  const answer = { key: stylePromptKey(request), result: { enhanced: 'techno, electronic sound. sin guitarras' } };
  assert.equal(stylePromptStatus(request, answer).ready, true);
  assert.deepEqual(stylePromptRequest(raw, selection), request);
  assert.equal(selection.main_style, 'techno');
  assert.deepEqual(selection.influence_styles, []);
});
