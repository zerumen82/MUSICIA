import test from 'node:test';
import assert from 'node:assert/strict';
import { measuredRemixBpm, remixMinimumDurationLabel, remixNaturalDuration, remixTimelineFields } from './remix_timeline.js';

const options = {
  scope: 'groups', targetBpm: '140', sourceBpm: '120', minutes: '2', seconds: '30',
  repeatStart: '5', repeatEnd: '25', transition: '0.2', sourceDuration: 60,
  capabilities: { parameters: { source_bpm: { min: 30, max: 300 }, duration_seconds: { min: 1, max: 600 },
    transition_seconds: { min: 0, max: 5 } }, timeline: { min_repeat_seconds: 1 } },
};

test('el BPM original y la duración se envían también al conservar todos los grupos', () => {
  assert.deepEqual(remixTimelineFields(options), { fields: { source_bpm: 120, duration_seconds: 150,
    repeat_start: 5, repeat_end: 25, transition_seconds: 0.2 }, error: null });
});

test('tramo omite la timeline oculta incluso si hay valores inválidos', () => {
  assert.deepEqual(remixTimelineFields({ ...options, scope: 'region', minutes: 'inválido', sourceBpm: 'inválido' }), { fields: {}, error: null });
});

test('vaciar la duración conserva la natural y omite la parte y fundido ocultos', () => {
  assert.deepEqual(remixTimelineFields({ ...options, minutes: '', seconds: '', repeatStart: 'inválido', transition: 'inválido' }),
    { fields: { source_bpm: 120 }, error: null });
});

test('solo Por pistas usa BPM original y solo cuando hay BPM objetivo', () => {
  assert.equal(remixTimelineFields({ ...options, scope: 'full' }).fields.source_bpm, undefined);
  assert.equal(remixTimelineFields({ ...options, targetBpm: '', sourceBpm: 'inválido' }).fields.source_bpm, undefined);
});

test('rechaza duración fuera de config, segundos sin normalizar y parte fuera del original', () => {
  assert.ok(remixTimelineFields({ ...options, minutes: '20' }).error);
  assert.ok(remixTimelineFields({ ...options, seconds: '60' }).error);
  assert.ok(remixTimelineFields({ ...options, minutes: '1.5' }).error);
  assert.ok(remixTimelineFields({ ...options, repeatEnd: '80' }).error);
  assert.ok(remixTimelineFields({ ...options, repeatStart: '24.5' }).error);
  assert.ok(remixTimelineFields({ ...options, transition: '6' }).error);
  assert.ok(remixTimelineFields({ ...options, sourceBpm: 'no' }).error);
});

test('parte vacía reutiliza el original sin inventar una duración ni tempo de ficha', () => {
  assert.deepEqual(remixTimelineFields({ ...options, sourceBpm: '', repeatStart: '', repeatEnd: '' }).fields,
    { duration_seconds: 150, transition_seconds: 0.2 });
});

test('completa los dos extremos de repetición cuando solo se edita uno', () => {
  assert.equal(remixTimelineFields({ ...options, repeatStart: '' }).fields.repeat_start, 0);
  assert.equal(remixTimelineFields({ ...options, repeatEnd: '' }).fields.repeat_end, 60);
});

test('el límite de fundido procede de timeline y cero no vale', () => {
  const capabilities = { timeline: { min_duration_seconds: 1, max_duration_seconds: 600, max_transition_seconds: 2 } };
  assert.equal(remixTimelineFields({ ...options, capabilities }).error, null);
  assert.ok(remixTimelineFields({ ...options, capabilities, transition: '0' }).error);
  assert.ok(remixTimelineFields({ ...options, capabilities, transition: '2.1' }).error);
});

test('la duración mínima de la parte se valida tras el cambio de tempo conocido', () => {
  assert.equal(remixTimelineFields({ ...options, targetBpm: '60', sourceBpm: '120', repeatStart: '0', repeatEnd: '0.8' }).error, null);
  assert.equal(remixTimelineFields({ ...options, sourceBpm: '', repeatStart: '0', repeatEnd: '0.8' }).error, null);
  assert.ok(remixTimelineFields({ ...options, scope: 'full', targetBpm: '', repeatStart: '0', repeatEnd: '0.8' }).error);
  assert.equal(remixTimelineFields({ ...options, scope: 'full', repeatStart: '0', repeatEnd: '0.8' }).error, null);
});

test('el BPM automático visible se valida sin enviar una procedencia manual', () => {
  const result = remixTimelineFields({ ...options, sourceBpmOrigin: 'measurement' });
  assert.equal(result.error, null);
  assert.equal(result.fields.source_bpm, undefined);
  assert.equal(remixTimelineFields({ ...options, sourceBpmOrigin: 'measurement', sourceBpm: '400' }).error,
    'Escribe un BPM original válido para las pistas.');
  assert.ok(remixTimelineFields({ ...options, sourceBpmOrigin: 'measurement', repeatEnd: '5.8' }).error);
});

test('una medición incierta o fuera de config nunca precarga BPM original', () => {
  const capabilities = { ...options.capabilities, timeline: { min_groove_confidence: 0.12 } };
  assert.equal(measuredRemixBpm({ bpm: 166.25, confidence: 0.249 }, capabilities), 166.25);
  for (const groove of [{ bpm: 363.64, confidence: 0.101 }, { bpm: 120, confidence: 0.1 },
    { bpm: 0, confidence: 0.8 }, { bpm: 'no', confidence: 0.8 }, { bpm: 120 }]) {
    assert.equal(measuredRemixBpm(groove, capabilities), null);
  }
  assert.equal(measuredRemixBpm({ bpm: 120, confidence: 0.9 }, options.capabilities), null);
});

test('la duración mínima por pistas usa el BPM visible y da minutos y segundos concretos', () => {
  const natural = remixNaturalDuration({ scope: 'groups', sourceDuration: 81.4, sourceBpm: 166.25, targetBpm: 199 });
  assert.ok(Math.abs(natural - 68.004) < 0.01);
  assert.equal(remixMinimumDurationLabel(natural), '1:09 (69 s)');
  assert.match(remixTimelineFields({ ...options, sourceDuration: 81.4, sourceBpm: 166.25, targetBpm: 199,
    minutes: '1', seconds: '0' }).error, /1:09 \(69 s\)/);
  assert.equal(remixTimelineFields({ ...options, sourceDuration: 81.4, sourceBpm: 166.25, targetBpm: 199,
    minutes: '1', seconds: '9' }).error, null);
  assert.equal(remixNaturalDuration({ scope: 'groups', sourceDuration: 81.4, sourceBpm: '', targetBpm: 199 }), null);
  assert.equal(remixNaturalDuration({ scope: 'groups', sourceDuration: 81.4, targetBpm: '' }), 81.4);
});

test('canción completa al BPM pedido espera el audio generado antes de prometer una duración', () => {
  assert.equal(remixNaturalDuration({ scope: 'full', sourceDuration: 81.4, sourceBpm: 166.25, targetBpm: 199 }), null);
  assert.equal(remixNaturalDuration({ scope: 'full', sourceDuration: 81.4, targetBpm: '' }), 81.4);
  assert.equal(remixTimelineFields({ ...options, scope: 'full', sourceDuration: 200, minutes: '1', seconds: '0' }).error, null);
  assert.match(remixTimelineFields({ ...options, scope: 'full', targetBpm: '', sourceDuration: 200, minutes: '1', seconds: '0' }).error, /3:20 \(200 s\)/);
});
