/** Regresiones de caption: la vista previa no añade un segundo significado. */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { glossPrompt } from './prompt_gloss.js';

const cases = {
  'instrumentos con papel y carácter distintos': [
    'batería suave al fondo', 'bajo potente, sin voz', 'jazz con contrabajo',
    'voz susurrada y percusión potente', 'guitarra limpia, sin riffs distorsionados',
  ],
  'negaciones y condiciones completas': [
    'sin guitarra ni batería', 'solo cambia la batería; conserva el bajo',
    'si hay voz, consérvala; no añadas una cantante',
    'no techno, mejor jazz', 'más cálido sin ralentizar',
  ],
  'géneros sin recetas implícitas': [
    'electrónica', 'techno', 'gabber', 'jungle', 'rap', 'frenchcore', 'rawstyle',
    'uptempo', 'makina', 'dub', 'hard bounce', 'synth pop',
  ],
  'idiomas y relaciones intactas': [
    'dark techno with gentle background drums',
    'mélodie puissante, voix discrète', 'caja de ritmos y contrabajo',
    'sin melodías, solo baterías; el resto permanece',
  ],
};
for (const [scenario, prompts] of Object.entries(cases)) {
  test(scenario, () => {
    for (const prompt of prompts) assert.equal(glossPrompt(prompt), prompt);
  });
}

test('cláusulas elegidas y texto en inglés no se recomponen', () => {
  const prompt = 'techno. driving drums as the lead of the track';
  assert.equal(glossPrompt(prompt), prompt);
  assert.equal(glossPrompt(glossPrompt(prompt)), prompt);
});

test('solo se limpia el espacio exterior; se conservan saltos y signos', () => {
  assert.equal(glossPrompt('  Conserva esto.\n¡Sin cambios!; aquello.  '), 'Conserva esto.\n¡Sin cambios!; aquello.');
  assert.equal(glossPrompt(''), '');
  assert.equal(glossPrompt('   '), '');
  assert.equal(glossPrompt(null), '');
});
