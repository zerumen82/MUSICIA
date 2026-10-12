import test from 'node:test';
import assert from 'node:assert/strict';
import { releaseAudioSources } from './audio_player.js';

const outputUrl = 'http://127.0.0.1:8000/music/audio/tema%20uno.mp3';

function player(src, currentSrc = src) {
  return {
    src, currentSrc, paused: false, unloaded: false,
    pause() { this.paused = true; },
    removeAttribute(name) { if (name === 'src') this.src = ''; },
    load() { this.currentSrc = ''; this.unloaded = !this.src; },
  };
}

test('libera todas las lecturas del mismo MP3, incluida la de un panel oculto', () => {
  const active = player(outputUrl);
  const hidden = player('', outputUrl);
  const other = player('http://127.0.0.1:8000/audio/uploads/file/tema%20uno.mp3');
  const root = { baseURI: 'http://127.0.0.1:8000/', querySelectorAll: () => [active, hidden, other] };
  releaseAudioSources(['/music/audio/tema%20uno.mp3'], root);
  assert.equal(active.paused && active.unloaded, true);
  assert.equal(hidden.paused && hidden.unloaded, true);
  assert.equal(other.paused || other.unloaded, false);
});

test('borrado múltiple libera solo las pistas elegidas y admite repetirlo', () => {
  const first = player(outputUrl);
  const secondUrl = 'http://127.0.0.1:8000/music/audio/segunda.mp3';
  const second = player(secondUrl);
  const other = player('http://127.0.0.1:8000/music/audio/tercera.mp3');
  const root = { baseURI: 'http://127.0.0.1:8000/', querySelectorAll: () => [first, second, other] };
  releaseAudioSources([outputUrl, secondUrl], root);
  releaseAudioSources([outputUrl, secondUrl], root);
  assert.equal(first.unloaded && second.unloaded, true);
  assert.equal(other.paused || other.unloaded, false);
});
