import test from 'node:test';
import assert from 'node:assert/strict';
import { comparisonBounds, comparisonPosition, switchComparisonSource } from './audio_comparison.js';

test('A/B usa el tramo común del audio más corto y admite regiones decimales', () => {
  const common = comparisonBounds({ start: 6.25, end: 18.75 }, [30, 14.5, 32]);
  assert.deepEqual(common, { start: 6.25, end: 14.5, duration: 14.5, valid: true });
  assert.equal(comparisonPosition(10.2, common), 10.2);
  assert.equal(comparisonPosition(18, common), 6.25);
  assert.equal(comparisonPosition(14.5, common), 6.25);
  assert.equal(comparisonPosition(-2, common), 6.25);
});

test('ningún intervalo vacío, invertido o fuera de ambos audios permite reproducir', () => {
  for (const interval of [{ start: 15, end: 15 }, { start: 8, end: 4 }, { start: 20, end: 25 }]) {
    assert.equal(comparisonBounds(interval, [12, 30]).valid, false);
  }
  assert.equal(comparisonBounds(null, []).valid, false);
  assert.deepEqual(comparisonBounds(null, [30, 18]), { start: 0, end: 18, duration: 18, valid: true });
});

test('el transporte espera metadata, mantiene el segundo absoluto y reanuda después de parar el origen anterior', async () => {
  const events = [];
  const listeners = new Map();
  const player = {
    currentTime: 12.3,
    pause() { events.push('pause'); },
    load() { events.push('load'); },
    play() { events.push(['play', this.currentTime]); return Promise.resolve(); },
    addEventListener(name, callback) { listeners.set(name, callback); },
    removeEventListener(name, callback) { if (listeners.get(name) === callback) listeners.delete(name); },
  };
  const bounds = comparisonBounds({ start: 6, end: 18 }, [30, 30]);
  const cleanup = switchComparisonSource(player, '/variante.mp3', 12.3, true, () => bounds, assert.fail);
  assert.deepEqual(events, ['pause', 'load']);
  assert.equal(player.src, '/variante.mp3');
  player.currentTime = 0; // El navegador reinicia el tiempo al cambiar src.
  listeners.get('loadedmetadata')();
  await Promise.resolve();
  assert.deepEqual(events, ['pause', 'load', ['play', 12.3]]);
  cleanup();
  assert.equal(listeners.size, 0);
});

test('cambio pausado conserva pausa y metadatos obsoletos se pueden cancelar', () => {
  const listeners = new Map();
  let plays = 0;
  const player = {
    currentTime: 0, pause() {}, load() {}, play() { plays++; return Promise.resolve(); },
    addEventListener(name, callback) { listeners.set(name, callback); },
    removeEventListener(name, callback) { if (listeners.get(name) === callback) listeners.delete(name); },
  };
  const bounds = comparisonBounds({ start: 6, end: 10 }, [30, 30]);
  const cleanup = switchComparisonSource(player, '/b.mp3', 15, false, () => bounds, assert.fail);
  listeners.get('loadedmetadata')();
  assert.equal(player.currentTime, 6);
  assert.equal(plays, 0);
  cleanup();
  assert.equal(listeners.size, 0);
  let wantsPlayback = true;
  const pending = switchComparisonSource(player, '/c.mp3', 8, () => wantsPlayback, () => bounds, assert.fail);
  wantsPlayback = false; // Otro reproductor tomó el control durante la carga.
  listeners.get('loadedmetadata')();
  assert.equal(player.currentTime, 8);
  assert.equal(plays, 0);
  const stale = listeners.get('loadedmetadata');
  pending();
  player.currentTime = 9;
  stale();
  assert.equal(player.currentTime, 9);
});
