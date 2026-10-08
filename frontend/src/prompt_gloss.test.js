/**
 * Tests de la glosa del prompt (sin GPU, sin red): `node --test src/prompt_gloss.test.js`
 *
 * Cubren el bug del 2026-10-05 («sin melodías» glosaba melody Y without
 * melody a la vez) y las palabras de estilo que la glosa no conocía.
 */

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { glossPrompt } from './prompt_gloss.js';

const terms = (text) => {
  const out = glossPrompt(text);
  const open = out.lastIndexOf(' (');
  if (open === -1 || !out.endsWith(')')) return [];
  return out.slice(open + 2, -1).split(', ').map((s) => s.trim());
};

test('glosa el estilo; lo que ya va en inglés no se repite', () => {
  const out = glossPrompt('baterias gabber de rotterdam');
  assert.ok(out.includes('gabber'), 'gabber ya está en la frase');
  assert.ok(terms(out).includes('drums'));
  const hard = terms('sonido hardstyle oscuro');
  assert.ok(hard.includes('dark'), 'oscuro sí necesita glosa');
  assert.ok(!hard.includes('hardstyle'), 'hardstyle ya está en inglés');
});

test('«sin melodías» no mete el término melody positivo (bug 2026-10-05)', () => {
  const list = terms('baterias hardcore techno de rotterdam, sin melodias, solo baterias, sonido hardstyle');
  assert.ok(!list.includes('melody'), 'no debe aparecer melody suelto');
  assert.ok(list.includes('without melody'));
  assert.ok(list.includes('drums'));
  assert.ok(glossPrompt('baterias hardcore techno de rotterdam, sin melodias, solo baterias, sonido hardstyle').includes('hardstyle'));
});

test('negada sin forma contraria: no se añade nada en su lugar', () => {
  const list = terms('jazz sin saxofón');
  assert.ok(!list.includes('saxophone'));
});

test('frase ya en inglés: se queda igual', () => {
  assert.equal(glossPrompt('dark techno with heavy drums'), 'dark techno with heavy drums');
});

test('sin duplicados aunque la palabra o la glosa se repitan', () => {
  const list = terms('techno techno con baterias baterias');
  assert.equal(list.filter((t) => t === 'drums').length, 1);
  assert.ok(!list.includes('techno'), 'techno ya está en la frase');
  assert.equal(terms('luminosa y brillante').filter((t) => t === 'bright').length, 1);
});

test('texto vacío intacto', () => {
  assert.equal(glossPrompt(''), '');
  assert.equal(glossPrompt('   '), '');
});

test('la frase del usuario nunca se reescribe', () => {
  const frase = 'melodias con sintetizador roland';
  const out = glossPrompt(frase);
  assert.ok(out.startsWith(`${frase} (`), 'la glosa solo se añade al final');
  const list = terms(frase);
  assert.ok(list.includes('melody'));
  assert.ok(list.includes('synthesizers'));
});

test('capa documental: estilo vocal y tempo feel se glosan (guía oficial)', () => {
  const voz = terms('balada con voz susurrada y falsete');
  assert.ok(voz.includes('whispered'));
  assert.ok(voz.includes('falsetto'));
  const tempo = terms('tempo lento y moderado, pulso constante');
  assert.ok(tempo.includes('slow'));
  assert.ok(tempo.includes('mid tempo'));
  assert.ok(tempo.includes('steady'));
  const epica = terms('himno explosivo con riff pegadizo y capas');
  for (const t of ['anthemic', 'explosive', 'riffs', 'catchy', 'layered']) {
    assert.ok(epica.includes(t), `falta ${t}`);
  }
});

test('variantes del remix y moods nuevos se glosan (auditoría 2026-10-06)', () => {
  // «ambiental»: la glosa añade ambient solo si la frase aún no lo trae
  // (lo ya inglés no se repite: primer test de este archivo).
  const calma = terms('tranquila para dormir, tempo lento y espacioso, sonido ambiental');
  for (const t of ['gentle', 'slow', 'spacious']) {
    assert.ok(calma.includes(t), `falta ${t}`);
  }
  assert.ok(glossPrompt('sonido ambiental').includes('ambient'));
  const melancolia = terms('melancólico y emotivo');
  assert.ok(melancolia.includes('melancholic'));
  // «nostálgico/a» contiene a «nostalgic» y viceversa: la glosa no repite
  // (mismo mecanismo que el primer test: lo ya inglés no se duplica).
  assert.equal(glossPrompt('recuerdo nostálgico'), 'recuerdo nostálgico');
  const luz = terms('luminoso y optimista, brillante');
  for (const t of ['bright']) {
    assert.ok(luz.includes(t), `falta ${t}`);
  }
  const minimal = terms('piezas con capas que evolucionan, vinilo');
  for (const t of ['layered', 'evolving', 'vinyl']) {
    assert.ok(minimal.includes(t), `falta ${t}`);
  }
  // «clímax» contiene a «climax» y viceversa: no se repite (sin entrada).
  assert.equal(glossPrompt('gran clímax final'), 'gran clímax final');
  // «minimalista» contiene a «minimalist» y viceversa: no se repite.
  assert.equal(glossPrompt('arreglo minimalista'), 'arreglo minimalista');
});
