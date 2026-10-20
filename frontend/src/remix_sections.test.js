import test from 'node:test';
import assert from 'node:assert/strict';
import { ACTIONS, ADJUST_SUBMITTING, CONVERTING, REMIX_SUBMITTING, REPAINT, SEPARATION_SUBMITTING, SCOPE_BUSY, SCOPE_WHY, SECTIONS, VOICE_SUBMITTING, actionWhy, remixBusyLine } from './remix_sections.js';

test('un desplegable elige la acción', () => {
  assert.deepEqual(ACTIONS.map((item) => item.id), ['full', 'region', 'groups', 'voice', 'adjust']);
  assert.match(actionWhy('voice'), /voz/);
  assert.match(actionWhy('adjust'), /archivo/);
});

test('cada ámbito dice para qué está', () => {
  assert.match(SCOPE_WHY.full, /canción/);
  assert.match(SCOPE_WHY.region, /trozo/);
  assert.match(SCOPE_WHY.groups, /pista/);
});

test('los títulos de sección no cambian: las sondas los pulsan', () => {
  assert.equal(SECTIONS.advanced.title, 'REFERENCIA Y AVANZADOS');
  assert.equal(SECTIONS.engine.title, 'PARÁMETROS DEL MOTOR');
  assert.equal(SECTIONS.voice.title, 'VOZ ORIGINAL + BASE NUEVA');
  assert.equal(SECTIONS.adjust.title, 'AJUSTES DE AUDIO · TEMPO, TONO, RECORTE Y LOOP');
  for (const section of Object.values(SECTIONS)) assert.ok(section.why.length > 10);
});

test('la línea de trabajo dice el ámbito y, al 100 %, la conversión', () => {
  assert.equal(remixBusyLine('', 'voice', null, false), REMIX_SUBMITTING);
  assert.equal(remixBusyLine('', 'groups', null, false, SEPARATION_SUBMITTING), SEPARATION_SUBMITTING);
  assert.equal(remixBusyLine('', 'adjust', null, false, ADJUST_SUBMITTING), ADJUST_SUBMITTING);
  assert.equal(remixBusyLine('', 'voice', null, false, VOICE_SUBMITTING), VOICE_SUBMITTING);
  assert.equal(remixBusyLine('', 'voice', null), SCOPE_BUSY.voice);
  assert.equal(remixBusyLine('Rehaciendo el audio', 'full', 0.4), SCOPE_BUSY.full);
  assert.equal(remixBusyLine('Rehaciendo el audio', 'region', 0.2), SCOPE_BUSY.region);
  assert.equal(remixBusyLine('Rehaciendo el audio', 'full', 1), CONVERTING);
  assert.equal(remixBusyLine('Cargando el modelo', 'full', 0.1), 'Cargando el modelo');
  assert.equal(remixBusyLine('Convirtiendo a audio', 'groups', 0.8), CONVERTING);
  assert.equal(remixBusyLine('Convirtiendo a audio final', 'full', 0.8), CONVERTING);
  assert.equal(remixBusyLine('Error', 'groups', 0.8), '');
  assert.equal(remixBusyLine('Error de análisis', 'full', 0.2), '');
});

test('el modo del tramo se lee en español', () => {
  assert.equal(REPAINT.conservative.label, 'Conservador');
  assert.match(REPAINT.aggressive.why, /fuera/);
});
