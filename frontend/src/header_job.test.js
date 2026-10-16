import test from 'node:test';
import assert from 'node:assert/strict';
import { headerWatchText, latestJob, runningJob } from './header_job.js';

const failed = {
  job_id: 'remix',
  status: 'failed',
  created_at: '2026-10-16T15:41:03+00:00',
  output_name: 'amrem',
  error: 'El BPM final medido 136.36 no cumple el pedido 170 (tolerancia 2 BPM)',
  phase: 'Error',
  prompt: 'GABBER HARDCORE',
};

const older = {
  job_id: 'old',
  status: 'succeeded',
  created_at: '2026-10-16T06:12:38+00:00',
  output_name: 'AM1.mp3',
  phase: 'Listo',
};

test('sin trabajos no hay nada que pintar', () => {
  assert.equal(runningJob(null), null);
  assert.equal(runningJob([]), null);
  assert.equal(latestJob([]), null);
  assert.equal(headerWatchText(null, 10), '');
});

test('el remix fallido sigue siendo el último aunque no esté en curso', () => {
  assert.equal(runningJob([older, failed]), null);
  assert.equal(latestJob([older, failed]).job_id, 'remix');
  assert.equal(latestJob([failed, older]).job_id, 'remix');
  assert.match(headerWatchText(failed), /amrem · El BPM final medido 136\.36/);
});

test('un trabajo en curso tapa al último y enseña el porcentaje', () => {
  const running = {
    job_id: 'live',
    status: 'running',
    created_at: '2026-10-16T18:00:00+00:00',
    output_name: 'amrem',
  };
  const queued = { job_id: 'wait', status: 'queued', created_at: '2026-10-16T18:01:00+00:00' };
  assert.equal(runningJob([failed, running]).job_id, 'live');
  assert.equal(runningJob([failed, queued]).job_id, 'wait');
  assert.equal(headerWatchText(running, 40), 'amrem · 40%');
  assert.equal(headerWatchText(running, null), 'amrem');
});

test('uno terminado bien enseña la fase, no un error vacío', () => {
  assert.equal(headerWatchText(older), 'AM1.mp3 · Listo');
  assert.equal(headerWatchText({ status: 'cancelled', phase: 'Cancelado' }), 'Trabajo · Cancelado');
});
