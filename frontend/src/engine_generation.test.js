import test from 'node:test';
import assert from 'node:assert/strict';
import { canAttemptEngineOperation, generationWaitMessage } from './engine_generation.js';

test('a lifecycle error keeps generation retryable', () => {
  assert.equal(canAttemptEngineOperation({
    ok: false, idle: false, starting: false, error: 'readiness failed',
  }), true);
});

test('engine unavailable without a recoverable lifecycle state stays disabled', () => {
  assert.equal(canAttemptEngineOperation({
    ok: false, idle: false, starting: false,
  }), false);
});

test('a generation waiting for the UI-started model shows an explicit wait message', () => {
  assert.match(
    generationWaitMessage({ status: 'queued' }, { starting: true }),
    /Conectando con el modelo; espera/,
  );
});

test('a generation stops showing the connection wait after the motor accepts the job', () => {
  assert.equal(
    generationWaitMessage({ status: 'queued', job_id: 'job-1' }, { starting: true }),
    null,
  );
});
