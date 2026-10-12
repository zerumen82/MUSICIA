/**
 * B1: clicks en la UI servida por la API y DELETE real mientras reproduce.
 * Solo crea y borra su fixture probe-ui-b1-20261012-UUID.mp3.
 * No importa main.cjs, no arranca/paraliza servicios ni modifica el producto.
 *
 * Ejecutar con Electron instalado (requiere aprobación para la GUI):
 *   Remove-Item Env:ELECTRON_RUN_AS_NODE -ErrorAction SilentlyContinue
 *   & .\frontend\node_modules\electron\dist\electron.exe .\scripts\probe_20261012_library_ui.cjs
 * Opcionales: MUSICIA_API_URL, MUSICIA_PROBE_TIMEOUT_MS, MUSICIA_PROBE_SECONDS,
 * MUSICIA_PROBE_FFMPEG, MUSICIA_PROBE_FFPROBE.
 */
const fs = require('node:fs');
const path = require('node:path');
const { randomUUID } = require('node:crypto');
const { spawnSync } = require('node:child_process');

const PROJECT_ROOT = path.resolve(__dirname, '..');
const EVIDENCE_DIR = path.join(PROJECT_ROOT, 'logs', 'fix-20261012-ui');
const RUN_ID = randomUUID().slice(0, 8);
const API_URL = process.env.MUSICIA_API_URL || 'http://127.0.0.1:8000';
const TIMEOUT_MS = Number(process.env.MUSICIA_PROBE_TIMEOUT_MS || 30000);
const FIXTURE_SECONDS = Number(process.env.MUSICIA_PROBE_SECONDS || 45);
const POLL_MS = 100;
const fixtureName = `probe-ui-b1-20261012-${RUN_ID}.mp3`;
const fixtureStem = path.parse(fixtureName).name;
const evidencePath = path.join(EVIDENCE_DIR, `result-${RUN_ID}.json`);
const result = {
  started_at: new Date().toISOString(), run_id: RUN_ID, fixture_name: fixtureName,
  api_url: API_URL, status: 'RUNNING', steps: [], requests: [], console_errors: [],
  unhandled_errors: [],
  resource_state_criterion: {
    description: 'Sin src, pausado, HAVE_NOTHING, NETWORK_EMPTY/NETWORK_NO_SOURCE y sin rangos buffered antes del DELETE y después.',
    reference: 'https://github.com/whatwg/html/issues/10410',
    current_src: 'Se registra literalmente; Chromium puede conservar la URL tras removeAttribute(src) y load() con el recurso descargado.',
  },
};
fs.mkdirSync(EVIDENCE_DIR, { recursive: true });
let window;
let electronApp;
let finished = false;

function finish(code, error) {
  if (finished) return;
  finished = true;
  result.status = code === 0 ? 'PASS' : 'FAIL';
  result.completed_at = new Date().toISOString();
  if (error) result.error = error.stack || String(error);
  fs.writeFileSync(evidencePath, JSON.stringify(result, null, 2), 'utf8');
  console.log(JSON.stringify({ status: result.status, evidence: evidencePath, error: result.error }));
  if (window && !window.isDestroyed()) window.destroy();
  if (electronApp) electronApp.exit(code);
  else process.exit(code);
}

process.on('uncaughtException', (error) => finish(1, error));
process.on('unhandledRejection', (error) => finish(1, error));

if (process.env.ELECTRON_RUN_AS_NODE || !process.versions.electron) {
  finish(1, new Error('Ejecuta electron.exe sin ELECTRON_RUN_AS_NODE; Node no puede verificar la UI.'));
} else {
  const { app, BrowserWindow } = require('electron');
  electronApp = app;
  const profile = path.join(EVIDENCE_DIR, `profile-${RUN_ID}`);
  fs.mkdirSync(profile, { recursive: true });
  app.setPath('userData', profile);
  app.on('window-all-closed', () => {});
  app.whenReady().then(run).catch((error) => finish(1, error));

  async function evaluate(fn, ...args) {
    return window.webContents.executeJavaScript(`(${fn.toString()})(...${JSON.stringify(args)})`, true);
  }

  async function waitFor(label, check) {
    const deadline = Date.now() + TIMEOUT_MS;
    while (Date.now() < deadline) {
      const value = await check();
      if (value) {
        result.steps.push({ label, at: new Date().toISOString(), value });
        return value;
      }
      await new Promise((resolve) => setTimeout(resolve, POLL_MS));
    }
    throw new Error(`Tiempo agotado: ${label}`);
  }

  function runTool(tool, args) {
    const execution = spawnSync(tool, args, { encoding: 'utf8', windowsHide: true, timeout: TIMEOUT_MS });
    if (execution.error || execution.status !== 0) {
      throw new Error(`${tool} falló (${execution.status}): ${execution.error || execution.stderr}`);
    }
    return execution.stdout;
  }

  async function run() {
    if (!Number.isFinite(TIMEOUT_MS) || TIMEOUT_MS <= 0 || !Number.isFinite(FIXTURE_SECONDS) || FIXTURE_SECONDS <= 0) {
      throw new Error('Timeout y duración de prueba deben ser positivos.');
    }
    const apiOrigin = new URL(API_URL);
    if (!['127.0.0.1', 'localhost', '[::1]'].includes(apiOrigin.hostname)) {
      throw new Error('Esta verificación solo usa la API local.');
    }
    const response = await fetch(new URL('/music/library', API_URL), { signal: AbortSignal.timeout(TIMEOUT_MS) });
    if (!response.ok) throw new Error(`Biblioteca real respondió HTTP ${response.status}`);
    const library = await response.json();
    const outputs = path.resolve(library.outputs_dir);
    if (!outputs.toLowerCase().startsWith(`${PROJECT_ROOT.toLowerCase()}${path.sep}`)) {
      throw new Error(`Salidas fuera del workspace autorizado: ${outputs}`);
    }
    const fixturePath = path.join(outputs, fixtureName);
    const fichaPath = path.join(outputs, `${fixtureStem}.ficha.json`);
    result.fixture_path = fixturePath;
    runTool(process.env.MUSICIA_PROBE_FFMPEG || 'ffmpeg', [
      '-hide_banner', '-loglevel', 'error', '-n', '-f', 'lavfi',
      '-i', `sine=frequency=440:duration=${FIXTURE_SECONDS}`, '-c:a', 'libmp3lame', fixturePath,
    ]);
    const metadata = JSON.parse(runTool(process.env.MUSICIA_PROBE_FFPROBE || 'ffprobe', [
      '-v', 'error', '-show_entries', 'format=duration,size', '-of', 'json', fixturePath,
    ])).format;
    if (!(Number(metadata.duration) > 0 && Number(metadata.size) > 0)) throw new Error('Fixture MP3 inválido');
    result.fixture_metadata = metadata;
    fs.writeFileSync(fichaPath, JSON.stringify({ name: fixtureName, task_type: 'text2music', prompt: 'fixture local B1' }), 'utf8');

    window = new BrowserWindow({
      show: false, width: 1280, height: 900,
      webPreferences: { contextIsolation: true, sandbox: true, nodeIntegration: false, backgroundThrottling: false },
    });
    window.webContents.setAudioMuted(true);
    window.webContents.on('console-message', (details) => {
      if (details.level === 'error') result.console_errors.push(details.message);
    });
    const targetDeleteUrl = new URL(`/music/audio/${encodeURIComponent(fixtureName)}`, API_URL).href;
    window.webContents.session.webRequest.onCompleted({ urls: [`${apiOrigin.origin}/*`] }, (details) => {
      if (details.method === 'DELETE' && details.url === targetDeleteUrl) {
        result.requests.push({ method: details.method, url: details.url, status_code: details.statusCode });
      }
    });
    window.webContents.session.webRequest.onErrorOccurred({ urls: [`${apiOrigin.origin}/*`] }, (details) => {
      if (details.method === 'DELETE' && details.url === targetDeleteUrl) {
        result.requests.push({ method: details.method, url: details.url, error: details.error });
      }
    });
    await window.loadURL(API_URL);
    await waitFor('React montado', () => evaluate(() => document.querySelector('aside nav button') !== null));
    await evaluate(() => {
      const tab = [...document.querySelectorAll('aside nav button')].find((button) => button.textContent.includes('BIBLIOTECA'));
      if (!tab) throw new Error('No existe la pestaña BIBLIOTECA');
      window.addEventListener('error', (event) => {
        window.__probeUnhandledErrors = [...(window.__probeUnhandledErrors || []), event.message];
      });
      window.addEventListener('unhandledrejection', (event) => {
        window.__probeUnhandledErrors = [...(window.__probeUnhandledErrors || []), String(event.reason)];
      });
      tab.click();
    });
    await waitFor('Fixture visible en Biblioteca', () => evaluate((name) => {
      const title = [...document.querySelectorAll('main span')].find((span) => span.textContent === name);
      const row = title?.closest('[class~="border-b"]');
      return Boolean(row && row.getClientRects().length);
    }, fixtureStem));
    await evaluate((name) => {
      const title = [...document.querySelectorAll('main span')].find((span) => span.textContent === name);
      const row = title.closest('[class~="border-b"]');
      const play = row.querySelector('button svg.lucide-play')?.closest('button');
      if (!play) throw new Error('Play no encontrado en la fila fixture');
      play.click();
    }, fixtureStem);
    result.playing = await waitFor('Audio real reproduciéndose, silenciado', () => evaluate((name) => {
      const audio = [...document.querySelectorAll('audio')].find((item) => item.currentSrc.includes(name) || item.src.includes(name));
      if (!audio) return false;
      audio.muted = true;
      window.__probeAudio = audio;
      if (audio.error) throw new Error(`Audio fixture falló: ${audio.error.message}`);
      return !audio.paused && audio.readyState >= audio.HAVE_CURRENT_DATA && audio.currentTime > 0
        ? { src: audio.getAttribute('src'), current_src: audio.currentSrc, current_time: audio.currentTime, paused: audio.paused, muted: audio.muted }
        : false;
    }, fixtureName));
    // Observación pasiva: los métodos originales siguen enviando la petición
    // sin cambiar argumentos ni respuesta. Captura el audio ANTES de send,
    // incluso si React ya lo retiró del documento.
    await evaluate((deleteUrl) => {
      // currentSrc puede seguir mostrando metadatos de la última selección:
      // https://github.com/whatwg/html/issues/10410. Se observa el estado del
      // recurso, sin modificar el reproductor ni sus metadatos.
      const snapshot = (audio = window.__probeAudio) => {
        if (!audio) return null;
        const bufferedRanges = Array.from({ length: audio.buffered.length }, (_value, index) => (
          { start: audio.buffered.start(index), end: audio.buffered.end(index) }
        ));
        return {
          src: audio.getAttribute('src'), current_src: audio.currentSrc,
          paused: audio.paused, connected: audio.isConnected,
          ready_state: audio.readyState, network_state: audio.networkState,
          current_time: audio.currentTime,
          buffered_ranges: bufferedRanges,
          is_unloaded: !audio.hasAttribute('src') && audio.paused
            && audio.readyState === audio.HAVE_NOTHING
            && [audio.NETWORK_EMPTY, audio.NETWORK_NO_SOURCE].includes(audio.networkState)
            && audio.buffered.length === 0,
        };
      };
      window.__probeAudioSnapshot = snapshot;
      window.__probeDeleteObservations = [];
      window.__probeAudioMutations = [];
      new MutationObserver((mutations) => {
        for (const mutation of mutations) {
          window.__probeAudioMutations.push({ at: new Date().toISOString(), attribute: mutation.attributeName, audio: snapshot() });
        }
      }).observe(window.__probeAudio, { attributes: true, attributeFilter: ['src'] });
      const originalOpen = XMLHttpRequest.prototype.open;
      const originalSend = XMLHttpRequest.prototype.send;
      XMLHttpRequest.prototype.open = function (...args) {
        this.__probeRequestMethod = String(args[0]).toUpperCase();
        this.__probeRequestUrl = new URL(args[1], document.baseURI).href;
        return Reflect.apply(originalOpen, this, args);
      };
      XMLHttpRequest.prototype.send = function (...args) {
        if (this.__probeRequestMethod === 'DELETE' && this.__probeRequestUrl === deleteUrl) {
          try {
            window.__probeDeleteObservations.push({
              at: new Date().toISOString(), method: this.__probeRequestMethod, url: this.__probeRequestUrl,
              audio: snapshot(), mounted_audio: [...document.querySelectorAll('audio')].map(snapshot),
            });
          } catch (error) {
            window.__probeDeleteObservations.push({ observation_error: String(error) });
          }
        }
        return Reflect.apply(originalSend, this, args);
      };
    }, targetDeleteUrl);
    await clickRowButton('ACCIONES');
    await clickRowButton('BORRAR');
    fs.writeFileSync(path.join(EVIDENCE_DIR, `before-${RUN_ID}.png`), (await window.webContents.capturePage()).toPNG());
    await clickRowButton('SÍ, BORRAR');
    await waitFor('DELETE real devuelve 200', () => {
      const deletion = result.requests.find((request) => request.method === 'DELETE');
      if (deletion && deletion.status_code !== 200) throw new Error(`Borrado real falló: ${JSON.stringify(deletion)}`);
      return deletion || false;
    });
    await waitFor('MP3 y ficha desaparecen del disco', () => !fs.existsSync(fixturePath) && !fs.existsSync(fichaPath));
    result.player_after = await waitFor('Reproductor original descarga el recurso (estado nativo)', async () => {
      const diagnostic = await evaluate(() => {
        const audio = window.__probeAudio;
        if (!audio) throw new Error('Sin referencia al reproductor verificado');
        return {
          audio: window.__probeAudioSnapshot(audio),
          before_delete: window.__probeDeleteObservations || [],
          src_mutations: window.__probeAudioMutations || [],
        };
      });
      result.player_after_latest = diagnostic.audio;
      result.before_delete = diagnostic.before_delete;
      result.src_mutations = diagnostic.src_mutations;
      const state = diagnostic.audio;
      return state.is_unloaded ? state : false;
    });
    if (result.before_delete.length !== 1 || !result.before_delete[0].audio?.is_unloaded) {
      throw new Error(`El reproductor no estaba descargado antes del DELETE real: ${JSON.stringify(result.before_delete)}`);
    }
    result.steps.push({ label: 'Recurso descargado antes del DELETE real', value: result.before_delete[0].audio });
    await waitFor('Fila fixture retirada de la UI', () => evaluate((name) => (
      ![...document.querySelectorAll('main span')].some((span) => span.textContent === name)
    ), fixtureStem));
    const ui = await evaluate(() => ({
      unhandled_errors: window.__probeUnhandledErrors || [],
      error_messages: [...document.querySelectorAll('main .text-red-300')]
        .map((element) => element.textContent.trim()).filter(Boolean),
    }));
    result.unhandled_errors = ui.unhandled_errors;
    result.ui_error_messages = ui.error_messages;
    fs.writeFileSync(path.join(EVIDENCE_DIR, `after-${RUN_ID}.png`), (await window.webContents.capturePage()).toPNG());
    if (result.console_errors.length || ui.unhandled_errors.length || ui.error_messages.length) {
      throw new Error(`Errores en UI/consola: ${JSON.stringify(ui)} ${result.console_errors.join(' | ')}`);
    }
    finish(0);
  }

  async function clickRowButton(label) {
    await waitFor(`Botón ${label} visible`, () => evaluate((name, text) => {
      const title = [...document.querySelectorAll('main span')].find((span) => span.textContent === name);
      const row = title?.closest('[class~="border-b"]');
      const button = [...(row?.querySelectorAll('button') || [])].find((item) => item.textContent.trim() === text);
      if (!button || button.disabled) return false;
      button.click();
      return true;
    }, fixtureStem, label));
  }
}
