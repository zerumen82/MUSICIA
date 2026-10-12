/** Real served UI, real audio and requests. webRequest observes; it never mocks. */
const fs = require('node:fs');
const path = require('node:path');
const { app, BrowserWindow } = require('electron');
const root = path.resolve(__dirname, '..');
const mode = process.env.MUSICIA_PROBE_MODE || 'full';
const source = process.env.MUSICIA_PROBE_SOURCE || 'pista-sin-nombre (2).mp3';
const api = process.env.MUSICIA_API_URL || 'http://127.0.0.1:8000';
const id = Date.now().toString(36);
const dir = path.join(root, 'logs', `plan-completion-ui-${mode}-${id}`);
const timeout = Number(process.env.MUSICIA_PROBE_TIMEOUT_MS || 1800000);
const report = { status: 'RUNNING', mode, id, steps: [], requests: [], errors: [], artistic_quality: 'NOT CERTIFIED' };
fs.mkdirSync(dir, { recursive: true });
app.setPath('userData', path.join(dir, 'profile'));
let win;
let finished = false;
const checkpoint = (label) => fs.appendFileSync(path.join(dir, 'progress.log'), `${new Date().toISOString()} ${label}\n`);
function finish(code, error) {
  if (finished) return;
  finished = true;
  report.status = code ? 'FAIL' : 'PASS';
  if (error) report.error = error.stack || String(error);
  fs.writeFileSync(path.join(dir, 'result.json'), JSON.stringify(report, null, 2));
  console.log(JSON.stringify({ status: report.status, evidence: dir, error: report.error }));
  if (win && !win.isDestroyed()) win.destroy();
  app.exit(code);
}
process.on('uncaughtException', (error) => finish(1, error));
process.on('unhandledRejection', (error) => finish(1, error));
app.on('window-all-closed', () => {});
const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const ev = (fn, ...args) => win.webContents.executeJavaScript(`(${fn.toString()})(...${JSON.stringify(args)})`, true);
async function wait(label, callback) {
  checkpoint(`waiting ${label}`);
  const limit = Date.now() + timeout;
  while (Date.now() < limit) {
    const value = await callback();
    if (value) { report.steps.push({ label, value }); checkpoint(`PASS ${label}`); console.log(label); return value; }
    await delay(200);
  }
  throw new Error(`Timeout: ${label}`);
}
async function click(text, selector = 'document') {
  return wait(`click ${text}`, () => ev((label, query) => {
    const parent = query === 'document' ? document : document.querySelector(query);
    const el = [...(parent?.querySelectorAll('button,summary') || [])].find((b) => !b.disabled && (b.textContent.trim() === label || [...b.querySelectorAll('span')].some((s) => s.textContent.trim() === label)));
    if (!el) return false;
    el.scrollIntoView({ block: 'center' }); el.click(); return true;
  }, text, selector));
}
async function set(selector, value) {
  await ev((query, next) => {
    const el = document.querySelector(query);
    if (!el) throw new Error(`Missing ${query}`);
    Object.getOwnPropertyDescriptor(Object.getPrototypeOf(el), 'value').set.call(el, next);
    el.dispatchEvent(new Event(el.tagName === 'SELECT' ? 'change' : 'input', { bubbles: true }));
  }, selector, value);
  await delay(100);
}
async function keyboard(selector, key) {
  await ev((query) => { const el = document.querySelector(query); el.scrollIntoView({ block: 'center' }); el.focus(); }, selector);
  win.webContents.sendInputEvent({ type: 'keyDown', keyCode: key });
  win.webContents.sendInputEvent({ type: 'keyUp', keyCode: key });
  await delay(200);
}
async function capture(name) {
  const metrics = await ev(() => ({ width: window.innerWidth, height: window.innerHeight,
    scrollWidth: document.documentElement.scrollWidth, overflow: document.documentElement.scrollWidth > window.innerWidth,
    overlaps: [...document.querySelectorAll('[data-remix-project] button,[data-remix-project] input:not([type="range"]),[data-remix-project] select')]
      .filter((e) => !e.closest('.sr-only') && e.offsetParent !== null).map((e) => ({ label: e.getAttribute('aria-label') || e.textContent.trim(), rect: e.getBoundingClientRect().toJSON() })) }));
  if (metrics.overflow) throw new Error(`Horizontal overflow ${name}: ${JSON.stringify(metrics)}`);
  report.steps.push({ label: `window ${name}`, metrics });
  fs.writeFileSync(path.join(dir, `${name}.png`), (await win.webContents.capturePage()).toPNG());
}
async function openSource(tab, name) {
  await click(tab);
  await wait(`open actual ${tab} source ${name}`, () => ev((filename) => {
    const stem = filename.replace(/\.mp3$/, '');
    const title = [...document.querySelectorAll('main span')].find((e) => e.textContent === filename || e.textContent === stem);
    let parent = title?.parentElement;
    while (parent && parent !== document.body) {
      const button = [...parent.querySelectorAll('button')].find((e) => e.textContent.trim() === 'REMIX');
      if (button) { button.click(); return true; } parent = parent.parentElement;
    }
    return false;
  }, name));
  await wait('remix mounted with live capabilities', () => ev(() => document.querySelectorAll('[aria-label="Ámbito del remix"] button').length === 3));
}
async function remixChecks(tab, filename, generate) {
  await openSource(tab, filename);
  await set('[aria-label="Prompt del remix"]', 'Jazz con contrabajo; batería suave al fondo, sin añadir instrumentos');
  await set('[aria-label="Clasificación del audio original"]', 'electronic');
  await click('PARÁMETROS DEL MOTOR', '[data-remix-project] > [data-effective-preview]');
  report[`${tab}_preview`] = await wait('real server-computed preview', () => ev(() => {
    const pre = document.querySelector('[data-remix-project] > [data-effective-preview] [data-engine-parameters]');
    if (!pre) return false; const data = JSON.parse(pre.textContent); return data.prompt && data.model ? data : false;
  }));
  await click('Tramo', '[data-remix-project]');
  await set('[aria-label="Inicio del tramo"]', '6');
  await set('[aria-label="Final del tramo"]', '18');
  await wait('numeric fields and actual waveform agree', () => ev(() => Number(document.querySelector('[aria-label="Inicio de la selección en la onda"]')?.value) === 6 && Number(document.querySelector('[aria-label="Final de la selección en la onda"]')?.value) === 18));
  await keyboard('[aria-label="Inicio de la selección en la onda"]', 'Right');
  const next = await ev(() => Number(document.querySelector('[aria-label="Inicio del tramo"]').value));
  if (!(next > 6 && next < 18)) throw new Error(`Waveform keyboard did not update numeric field: ${next}`);
  await click('Canción completa', '[data-remix-project]');
  await click('Tramo', '[data-remix-project]');
  await wait('remount preserves selected interval', () => ev((start) => Number(document.querySelector('[aria-label="Inicio del tramo"]').value) === start && Number(document.querySelector('[aria-label="Final del tramo"]').value) === 18, next));
  await wait('preview agrees with remounted region', () => ev((start) => {
    const data = JSON.parse(document.querySelector('[data-remix-project] > [data-effective-preview] [data-engine-parameters]').textContent);
    return data.repainting_start === start && data.repainting_end === 18 ? data : false;
  }, next));
  win.setContentSize(1400, 900); await capture(`${tab}-region-1400x900`);
  win.setContentSize(1080, 700); await capture(`${tab}-region-1080x700`);
  if (!generate) return;
  await click('Por pistas', '[data-remix-project]');
  await click('SEPARAR PISTAS DEL ORIGINAL', '[data-remix-project]');
  await wait('four actual stems with one exclusive action each', () => ev(() => document.querySelectorAll('[data-remix-project] select[aria-label^="Acción de"]').length === 4));
  await ev(() => {
    const e = [...document.querySelectorAll('select[aria-label^="Acción de"]')].find((e) => /voz/i.test(e.getAttribute('aria-label')));
    Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'value').set.call(e, 'remove'); e.dispatchEvent(new Event('change', { bubbles: true }));
  });
  await click('SOLO', '[data-remix-project]');
  await wait('solo actually playing a decoded stem', () => ev(() => {
    const a = document.querySelector('audio[aria-label^="Escuchar "]');
    return a && !a.paused && a.readyState >= 2 ? { src: a.src, time: a.currentTime, playing: [...document.querySelectorAll('audio')].filter((a) => !a.paused).length } : false;
  }));
  await keyboard('[data-audio-comparator] button[aria-label="Reproducir comparación"]', 'Return');
  await wait('comparison pauses solo and never overlaps', () => ev(() => {
    const a = document.querySelector('audio[aria-label="Reproductor de comparación"]');
    const playing = [...document.querySelectorAll('audio')].filter((a) => !a.paused);
    return a && !a.paused && playing.length === 1 ? { time: a.currentTime, playing: playing.length } : false;
  }));
  await click('CERRAR SOLO', '[data-remix-project]');
  await click('REFERENCIA Y AVANZADOS +', '[data-remix-project]');
  await set('[aria-label="Nombre del remix"]', `prueba-plan-ui-dsp-${id}`);
  await click('REMIX', '[data-remix-project]');
  await wait('deterministic DSP generates actual comparison variant', () => ev(() => [...document.querySelectorAll('[aria-label="Audio de la comparación"] button')].some((e) => e.textContent.startsWith('VARIANTE A'))));
  await set('[aria-label="Inicio de comparación"]', '6');
  await set('[aria-label="Final de comparación"]', '18');
  await set('[aria-label="Posición compartida A/B"]', '10');
  await keyboard('[data-audio-comparator] button[aria-label="Reproducir comparación"]', 'Return');
  const before = await ev(() => document.querySelector('audio[aria-label="Reproductor de comparación"]').currentTime);
  await ev(() => { const b = [...document.querySelectorAll('[aria-label="Audio de la comparación"] button')].find((b) => b.textContent.startsWith('VARIANTE A')); b.focus(); });
  win.webContents.sendInputEvent({ type: 'keyDown', keyCode: 'Return' }); win.webContents.sendInputEvent({ type: 'keyUp', keyCode: 'Return' });
  report.ab_switch = await wait('keyboard A/B keeps actual time and active playback', () => ev((t) => {
    const a = document.querySelector('audio[aria-label="Reproductor de comparación"]');
    return a.src.includes('prueba-plan-ui-dsp') && !a.paused && a.currentTime >= t - 0.15 && a.currentTime < t + 2 && [...document.querySelectorAll('audio')].filter((a) => !a.paused).length === 1 ? { before: t, after: a.currentTime, src: a.src } : false;
  }, before));
  await keyboard('[aria-label="Posición compartida A/B"]', 'Right');
  await click('PAUSAR', '[data-audio-comparator]');
  win.setContentSize(1400, 900); await capture('groups-1400x900');
  win.setContentSize(1080, 700); await capture('groups-1080x700');
  await click('VOZ ORIGINAL + BASE NUEVA', '[data-remix-project]');
  await set('[aria-label="Prompt de la base con voz original"]', 'Jazz con contrabajo y batería suave');
  await set('[aria-label="Minutos de la base con voz original"]', '0.5');
  await set('[aria-label="Semilla de la base con voz original"]', '733217');
  await click('PARÁMETROS DEL MOTOR', '[data-voice-backing]');
  report.voice_preview = await wait('voice route minutes and seed are effective', () => ev(() => {
    const pre = document.querySelector('[data-voice-backing] [data-engine-parameters]'); if (!pre) return false;
    const p = JSON.parse(pre.textContent); return p.audio_duration === 30 && p.seed === 733217 ? p : false;
  }));
}
async function creation() {
  await click('CREAR');
  await set('[aria-label="Prompt de crear"]', 'Jazz con contrabajo; batería suave al fondo, sin añadir instrumentos');
  await set('[aria-label="Duración"]', '30');
  await ev((label) => { const input = [...document.querySelectorAll('input')].find((e) => e.placeholder?.startsWith('sin nombre')); Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(input, label); input.dispatchEvent(new Event('input', { bubbles: true })); }, `prueba-plan-create-${id}`);
  await ev(() => { const input = [...document.querySelectorAll('input')].find((e) => e.placeholder === 'auto'); Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(input, '733216'); input.dispatchEvent(new Event('input', { bubbles: true })); });
  await click('VER LO QUE SE ENVÍA');
  report.create_preview = await wait('React computed creation preview', () => ev(() => {
    const p = document.querySelector('[data-engine-parameters]'); if (!p) return false;
    const data = JSON.parse(p.textContent); return data.audio_duration === 30 && data.seed === 733216 ? data : false;
  }));
  await capture('crear-before-generation');
  await click('GENERAR');
  report.create_wire = await wait('Observed genuine HTTP creation request', () => report.requests.find((r) => new URL(r.url).pathname === '/music/generate'));
  const job = await wait('Real generation returns decodable served audio', async () => {
    const jobs = await ev(async (base) => (await (await fetch(base + '/music/jobs')).json()).items, api);
    const item = jobs.find((j) => j.prompt === report.create_wire.body.prompt && j.output_name?.startsWith(`prueba-plan-create-${id}`));
    if (!item) return false;
    const state = await ev(async (base, id) => (await (await fetch(base + '/music/status/' + id)).json()), api, item.job_id);
    if (state.status === 'failed') throw new Error(JSON.stringify(state));
    return state.status === 'succeeded' ? state : false;
  });
  report.create_job = job;
  if (JSON.stringify(job.effective_parameters) !== JSON.stringify(report.create_preview)) throw new Error('Creation preview differs from executed job');
  await wait('Served generated audio plays', () => ev(() => { const a = document.querySelector('audio[controls]'); return a && a.readyState >= 2 && !a.error ? { src: a.src, duration: a.duration } : false; }));
}
app.whenReady().then(async () => {
  if (!['127.0.0.1', 'localhost'].includes(new URL(api).hostname)) throw new Error('Local API only');
  win = new BrowserWindow({ width: 1400, height: 900, show: false, webPreferences: { sandbox: true, contextIsolation: true, nodeIntegration: false } });
  checkpoint('window created');
  win.webContents.on('did-finish-load', () => checkpoint('did-finish-load'));
  win.webContents.on('did-fail-load', (_e, code, description) => checkpoint(`did-fail-load ${code} ${description}`));
  win.webContents.on('render-process-gone', (_e, details) => finish(1, new Error(JSON.stringify(details))));
  setTimeout(() => finish(1, new Error('Overall Electron probe timeout')), timeout + 30000);
  win.webContents.on('console-message', (_event, level, message) => { if (level === 3 && !message.includes('status code of 422')) report.errors.push(message); });
  win.webContents.session.webRequest.onBeforeRequest({ urls: [api + '/*'] }, (details, callback) => {
    if (details.method === 'POST') {
      const bytes = Buffer.concat((details.uploadData || []).filter((e) => e.bytes).map((e) => e.bytes));
      let body; try { body = JSON.parse(bytes.toString()); } catch { body = { multipart_bytes: bytes.length }; }
      report.requests.push({ time: Date.now(), url: details.url, method: details.method, body });
    }
    callback({ cancel: false });
  });
  checkpoint(`loadURL ${api}`);
  await win.loadURL(api);
  checkpoint('loadURL complete');
  if (mode === 'create') await creation();
  else {
    await remixChecks('BIBLIOTECA', source, mode === 'full');
    if (mode === 'full') {
      await click('SUBIR');
      const bytes = fs.readFileSync(path.join(root, 'backend', 'outputs', source));
      await ev((base64, name) => {
        const raw = Uint8Array.from(atob(base64), (c) => c.charCodeAt(0));
        const file = new File([raw], name, { type: 'audio/mpeg' }); const dt = new DataTransfer(); dt.items.add(file);
        const input = document.querySelector('input[type="file"]'); input.files = dt.files; input.dispatchEvent(new Event('change', { bubbles: true }));
      }, bytes.toString('base64'), `prueba-plan-upload-${id}.mp3`);
      await click('Solo voz'); await click('Crear base para la voz');
      await set('[aria-label="Prompt del acompañamiento"]', 'Jazz con contrabajo y batería suave');
      await set('[aria-label="Duración del acompañamiento"]', '30'); await set('[aria-label="Semilla del acompañamiento"]', '733215');
      await click('ENVÍO EFECTIVO');
      report.backing_preview = await wait('backing tools and effective controls present', () => ev(() => {
        const tools = document.querySelector('[data-prompt-tools]'); const pre = document.querySelector('[data-engine-parameters]');
        if (!tools || !pre || !tools.textContent.includes('GLOSARIO') || !tools.textContent.includes('AÑADIR') || !tools.textContent.includes('SUGERENCIAS OPTATIVAS')) return false;
        const p = JSON.parse(pre.textContent); return p.audio_duration === 30 && p.seed === 733215 ? p : false;
      }));
      await capture('accompaniment-1080x700');
      const uploaded = report.requests.find((r) => new URL(r.url).pathname === '/audio/upload');
      if (!uploaded) throw new Error('No actual upload');
      const items = await ev(async (base) => (await (await fetch(base + '/audio/uploads')).json()).items, api);
      const name = items.find((item) => item.name.includes(`prueba-plan-upload-${id}`))?.name;
      if (!name) throw new Error('Uploaded source not persisted');
      await click('CREAR'); await remixChecks('SUBIR', name, false);
    }
  }
  if (report.errors.length) throw new Error(`Console errors: ${report.errors.join(' | ')}`);
  finish(0);
}).catch((error) => finish(1, error));
