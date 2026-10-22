import test from 'node:test';
import assert from 'node:assert/strict';
import { applyTrackAction, chooseStyle, effectiveTrackSelection, emptyStyleSelection, emptyTouchedRoles, stylePromptKey, stylePromptRequest, stylePromptStatus } from './style_prompt.js';

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

test('en Por pistas la pista hereda el estilo global hasta que elija el suyo', () => {
  const global = { main_style: 'gabber', influence_styles: ['hardcore'], include_descriptions: true };
  const empty = emptyStyleSelection();

  // Sin tocar el glosario de la pista: hereda principal y matices globales.
  const inherited = effectiveTrackSelection(empty, emptyTouchedRoles(), global);
  assert.equal(inherited.main_style, 'gabber');
  assert.deepEqual(inherited.influence_styles, ['hardcore']);
  assert.equal(inherited.include_descriptions, true);

  // Al elegir su propio principal, ese manda con sus matices.
  const own = chooseStyle(chooseStyle(empty, 'techno', 'main'), 'trance', 'influence');
  const chosen = effectiveTrackSelection(own, { main: true, influence: true, descriptions: false }, global);
  assert.equal(chosen.main_style, 'techno');
  assert.deepEqual(chosen.influence_styles, ['trance']);

  // Si solo apaga la ficha, los roles siguen heredados pero sin descripción.
  const noDescription = { ...empty, include_descriptions: false };
  const quiet = effectiveTrackSelection(noDescription, { main: false, influence: false, descriptions: true }, global);
  assert.equal(quiet.main_style, 'gabber');
  assert.deepEqual(quiet.influence_styles, ['hardcore']);
  assert.equal(quiet.include_descriptions, false);

  // Sin estilo global no hay nada que heredar.
  const none = effectiveTrackSelection(empty, emptyTouchedRoles(), emptyStyleSelection());
  assert.equal(none.main_style, null);
  assert.deepEqual(none.influence_styles, []);
});

test('elegir solo un matiz en la pista no pierde el matiz elegido', () => {
  // Defecto A: al tocar la pista se descartaba su matiz y volvía el global.
  const global = { main_style: 'gabber', influence_styles: ['hardcore'], include_descriptions: true };
  const empty = emptyStyleSelection();
  const own = chooseStyle(empty, 'trance', 'influence');
  const chosen = effectiveTrackSelection(own, { main: false, influence: true, descriptions: false }, global);
  assert.equal(chosen.main_style, 'gabber');
  assert.deepEqual(chosen.influence_styles, ['trance']);
});

test('QUITAR un estilo heredado en la pista no lo reinserta', () => {
  // Defecto B: la «×» no quitaba nada porque la herencia volvía a ponerlo.
  const global = { main_style: 'gabber', influence_styles: ['hardcore'], include_descriptions: true };
  const empty = emptyStyleSelection();
  const step = applyTrackAction(empty, emptyTouchedRoles(), global, (current) => ({
    ...current, main_style: null,
  }));
  assert.equal(step.effective.main_style, null);
  assert.equal(step.touched.main, true);
  // Un segundo toque no lo devuelve: lo quitado no se reinserta solo.
  const again = applyTrackAction(step.own, step.touched, global, (current) => ({ ...current }));
  assert.equal(again.effective.main_style, null);
});

test('elegir en la pista solo toca ese papel; los demás siguen heredados', () => {
  const global = { main_style: 'gabber', influence_styles: ['hardcore'], include_descriptions: true };
  const empty = emptyStyleSelection();
  const step = applyTrackAction(empty, emptyTouchedRoles(), global, (current) => ({
    ...current, influence_styles: [...current.influence_styles, 'trance'],
  }));
  assert.deepEqual(step.effective.influence_styles, ['hardcore', 'trance']);
  assert.equal(step.effective.main_style, 'gabber');
  assert.equal(step.touched.influence, true);
  assert.equal(step.touched.main, false);
  assert.equal(step.touched.descriptions, false);
});

