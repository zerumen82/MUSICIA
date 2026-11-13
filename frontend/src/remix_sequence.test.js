import test from 'node:test';
import assert from 'node:assert/strict';
import {
  defaultSequenceSteps, sequenceCostText, sequenceEnabledCount, sequenceIntervalLabel,
  sequencePayloadSteps, sequencePreparationError, sequencePreviewStep, sequenceStepStatus,
  sequencePreviewState, sequenceStepsPending, sequenceValidation,
} from './remix_sequence.js';

test('los pasos por defecto vienen apagados y sin texto', () => {
  const steps = defaultSequenceSteps(8);
  assert.equal(steps.length, 8);
  assert.deepEqual(steps[0], { index: 0, enabled: false, focus: 'todo', prompt: '', patternEnabled: false });
  assert.deepEqual(steps.map((step) => step.index), [0, 1, 2, 3, 4, 5, 6, 7]);
  assert.ok(steps.every((step) => step.enabled === false && step.prompt === ''));
  assert.deepEqual(defaultSequenceSteps(0), []);
});

test('la lista que se manda solo lleva lo que el contrato acepta', () => {
  const payload = sequencePayloadSteps([
    { index: 0, enabled: true, focus: 'todo', prompt: 'bombo a cuatro', extra: 'no viaja' },
    { index: 1, enabled: false, focus: 'todo', prompt: '' },
  ]);
  assert.deepEqual(payload, [
    { index: 0, enabled: true, focus: 'todo', prompt: 'bombo a cuatro' },
    { index: 1, enabled: false, focus: 'todo', prompt: '' },
  ]);
  assert.deepEqual(Object.keys(payload[0]).sort(), ['enabled', 'focus', 'index', 'prompt']);
});

test('sin pasos encendidos no se envía nada', () => {
  const steps = defaultSequenceSteps(3).map((step) => ({ ...step, prompt: 'algo' }));
  const result = sequenceValidation(steps, { maxSteps: 16 });
  assert.match(result.error, /Enciende al menos un paso/);
});

test('un paso encendido sin texto no vale', () => {
  const steps = defaultSequenceSteps(3).map((step, index) => ({ ...step, enabled: index === 1, prompt: index === 1 ? '   ' : 'algo' }));
  const result = sequenceValidation(steps, { maxSteps: 16 });
  assert.match(result.error, /paso 2 necesita su texto/i);
});

test('más pasos que el máximo no se envían', () => {
  const steps = defaultSequenceSteps(5).map((step) => ({ ...step, enabled: true, prompt: 'algo' }));
  const result = sequenceValidation(steps, { maxSteps: 4 });
  assert.match(result.error, /hasta 4 pasos/);
  assert.equal(sequenceValidation(steps, { maxSteps: 5 }).error, null);
});

test('una secuencia bien escrita no da error', () => {
  const steps = defaultSequenceSteps(2).map((step, index) => ({ ...step, enabled: true, prompt: index ? 'bajo más grave' : 'bombo a cuatro' }));
  assert.deepEqual(sequenceValidation(steps, { maxSteps: 16 }), { error: null });
});

test('el estado de un paso sale del trabajo que corre', () => {
  const job = { steps: [
    { index: 0, status: 'done' },
    { index: 1, status: 'running' },
    { index: 2, status: 'pending' },
    { index: 3, status: 'kept', warning: 'Este paso no llegó a rehacerse: conserva el material original.' },
  ] };
  assert.deepEqual(sequenceStepStatus(job, 0), { status: 'done', text: 'HECHO', warning: null, check: null });
  assert.equal(sequenceStepStatus(job, 1).text, 'EN MARCHA');
  assert.equal(sequenceStepStatus(job, 2).text, 'PENDIENTE');
  assert.equal(sequenceStepStatus(job, 3).text, 'SIN TOCAR');
  assert.match(sequenceStepStatus(job, 3).warning, /material original/);
  assert.deepEqual(sequenceStepStatus(job, 9), { status: 'idle', text: 'SIN EMPEZAR', warning: null, check: null });
  assert.deepEqual(sequenceStepStatus(null, 0), { status: 'idle', text: 'SIN EMPEZAR', warning: null, check: null });
});

test('el tramo del paso se lee en mm:ss', () => {
  assert.equal(sequenceIntervalLabel(0, 15.4), '0:00–0:15');
  assert.equal(sequenceIntervalLabel(61.2, 125.9), '1:01–2:06');
  assert.equal(sequenceIntervalLabel(undefined, 10), null);
});

test('el tramo sale de la vista previa del servidor', () => {
  const preview = { sequence: { steps: [{ index: 0, start: 0, end: 12.5 }] } };
  assert.equal(sequencePreviewStep(preview, 0).end, 12.5);
  assert.equal(sequencePreviewStep(preview, 4), null);
  assert.equal(sequencePreviewStep(null, 0), null);
});

test('el coste declarado cuenta los pasos encendidos', () => {
  assert.equal(sequenceEnabledCount(defaultSequenceSteps(4).map((step) => ({ ...step, enabled: true }))), 4);
  assert.match(sequenceCostText(3), /3 pasos son 3 generaciones/);
  assert.match(sequenceCostText(1), /1 paso es 1 generación/);
  assert.match(sequenceCostText(0), /Ningún paso encendido/);
});

test('un texto sin preparar bloquea el envío', () => {
  const steps = defaultSequenceSteps(2).map((step, index) => ({ ...step, enabled: true, prompt: index ? 'bajo grave' : '' }));
  const prepared = { 0: { ready: true, effectivePrompt: '', error: null }, 1: { ready: true, effectivePrompt: 'bajo grave', error: null } };
  assert.equal(sequenceStepsPending(steps, prepared), false);
  assert.equal(sequencePreparationError(steps, prepared), null);
  const waiting = { 1: { ready: false, effectivePrompt: '', error: null } };
  assert.equal(sequenceStepsPending(steps, waiting), true);
  const broken = { 1: { ready: false, effectivePrompt: '', error: 'El prompt necesita al menos 3 caracteres' } };
  assert.match(sequencePreparationError(steps, broken), /paso 2/);
});

test('desactivar un patrón conserva sus marcas locales pero no lo envía', () => {
  const pattern = { kick: [true, false], cymbal: [false, true] };
  const step = { index: 0, enabled: true, focus: 'todo', prompt: 'techno', patternEnabled: false, pattern };
  assert.equal('pattern' in sequencePayloadSteps([step])[0], false);
  assert.deepEqual(step.pattern, pattern);
  assert.deepEqual(sequencePayloadSteps([{ ...step, patternEnabled: true }])[0].pattern, pattern);
  assert.equal('pattern' in sequencePayloadSteps([{ ...step, patternEnabled: true, enabled: false }])[0], false);
});

test('los textos de pasos apagados no bloquean los pasos activos', () => {
  const steps = [{ index: 0, enabled: true, prompt: 'techno' }, { index: 1, enabled: false, prompt: 'x' }];
  const prepared = { 0: { ready: true, effectivePrompt: 'techno' }, 1: { ready: false, error: 'demasiado corto' } };
  assert.equal(sequenceStepsPending(steps, prepared), false);
  assert.equal(sequencePreparationError(steps, prepared), null);
});

test('una respuesta antigua nunca habilita el envío de otro patrón, texto, origen o parámetros', () => {
  const request = { source_name: 'source.mp3', source_bpm: 120, guidance_scale: 9,
    steps: [{ index: 0, enabled: true, prompt: 'without vocals', pattern: { kick: [true, false] } }] };
  const key = JSON.stringify(request);
  const answer = { key, result: { sequence: { steps: [{ index: 0, effective_prompt: 'exact server caption' }] } } };
  assert.equal(sequencePreviewState(key, answer).ready, true);
  for (const changed of [
    { ...request, source_name: 'other.mp3' },
    { ...request, source_bpm: 130 },
    { ...request, guidance_scale: 8 },
    { ...request, steps: [{ ...request.steps[0], prompt: 'a new prepared global style' }] },
    { ...request, steps: [{ ...request.steps[0], pattern: { kick: [false, true] } }] },
  ]) {
    const status = sequencePreviewState(JSON.stringify(changed), answer);
    assert.equal(status.ready, false);
    assert.equal(status.result, null);
    assert.equal(status.pending, true);
  }
  const error = sequencePreviewState(key, { key, error: 'La fuente no tiene tempo fiable' });
  assert.equal(error.ready, false);
  assert.match(error.error, /tempo fiable/);
});
