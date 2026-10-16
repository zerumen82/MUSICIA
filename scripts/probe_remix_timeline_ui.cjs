/** Live R11 Electron probe. Requests observed without substituting responses. */
const fs = require('node:fs');
const path = require('node:path');
const { app, BrowserWindow } = require('electron');
const root = path.resolve(__dirname, '..');
const manifest = JSON.parse(fs.readFileSync(process.env.MUSICIA_R11_MANIFEST, 'utf8').replace(/^\uFEFF/, ''));
const dir = process.env.MUSICIA_R11_OUTPUT;
const api = process.env.MUSICIA_API_URL || 'http://127.0.0.1:8000';
const timeout = Number(process.env.MUSICIA_PROBE_TIMEOUT_MS || 1200000);
const panel = '[data-active="true"] [data-remix-project]';
const report = { status: 'RUNNING', manifest, requests: [], steps: [], errors: [] };
fs.mkdirSync(dir, { recursive: true });
app.setPath('userData', path.join(dir, 'profile'));
let win;
let finished = false;
function checkpoint() { fs.writeFileSync(path.join(dir, 'running.json'), JSON.stringify(report, null, 2)); }
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
  const deadline = Date.now() + timeout;
  while (Date.now() < deadline) {
    const value = await callback();
    if (value) { report.steps.push({ label, value }); checkpoint(); console.log(label); return value; }
    await delay(250);
  }
  throw new Error(`Timeout: ${label}`);
}
async function click(label, selector = panel) {
  return wait(`click ${label}`, () => ev((text, query) => {
    const parent = query === 'document' ? document : document.querySelector(query);
    const node = [...(parent?.querySelectorAll('button,summary') || [])].find((el) => !el.matches(':disabled') && el.getClientRects().length &&
      (el.textContent.trim() === text || [...el.querySelectorAll('span')].some((span) => span.textContent.trim() === text)));
    if (!node) return false;
    node.scrollIntoView({ block: 'center' }); node.click(); return true;
  }, label, selector));
}
async function set(label, value) {
  await ev((query, field, next) => {
    const input = document.querySelector(query)?.querySelector(`[aria-label="${field}"]`);
    if (!input || input.disabled || !input.getClientRects().length) throw new Error(`Missing/disabled/hidden: ${field}`);
    input.scrollIntoView({ block: 'center' });
    Object.getOwnPropertyDescriptor(Object.getPrototypeOf(input), 'value').set.call(input, String(next));
    input.dispatchEvent(new Event(input.tagName === 'SELECT' ? 'change' : 'input', { bubbles: true }));
  }, panel, label, value);
  await delay(120);
}
async function apiGet(url) { return ev(async (endpoint) => { const response = await fetch(endpoint); if (!response.ok) throw new Error(`${endpoint}:${response.status}`); return response.json(); }, api + url); }
async function capture(size) {
  win.setContentSize(...size);
  await ev((query) => { document.querySelector(query).scrollIntoView({ block: 'start' }); }, panel);
  await ev(() => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve))));
  await delay(150);
  const metrics = await ev((query) => ({ viewport: [innerWidth, innerHeight], overflow: document.documentElement.scrollWidth > innerWidth,
    text: document.querySelector(query).innerText,
    controls: [...document.querySelector(query).querySelectorAll('input,select,button')].filter((el) => el.getClientRects().length)
      .map((el) => ({ label: el.getAttribute('aria-label') || el.textContent.trim(), disabled: el.disabled, value: el.value,
        rect: el.getBoundingClientRect().toJSON(), color: getComputedStyle(el).color, background: getComputedStyle(el).backgroundColor })) }), panel);
  if (metrics.overflow) throw new Error(`Horizontal overflow at ${size.join('x')}`);
  const visible = metrics.controls.filter((control) => control.rect.bottom > 0 && control.rect.top < size[1]);
  metrics.overlaps = [];
  for (let i = 0; i < visible.length; i += 1) for (let j = i + 1; j < visible.length; j += 1) {
    const a = visible[i].rect; const b = visible[j].rect;
    if (Math.min(a.right, b.right) - Math.max(a.left, b.left) > 1 && Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top) > 1)
      metrics.overlaps.push([visible[i].label, visible[j].label]);
  }
  if (metrics.overlaps.length) throw new Error(`Overlapping controls at ${size.join('x')}: ${JSON.stringify(metrics.overlaps)}`);
  report.steps.push({ label: `Layout ${size.join('x')}`, value: metrics });
  fs.writeFileSync(path.join(dir, `groups-${size.join('x')}.png`), (await win.webContents.capturePage()).toPNG());
  checkpoint();
}

app.whenReady().then(async () => {
  if (!['127.0.0.1', 'localhost'].includes(new URL(api).hostname)) throw new Error('Local API only');
  win = new BrowserWindow({ width: 1400, height: 900, show: false,
    webPreferences: { sandbox: true, contextIsolation: true, nodeIntegration: false } });
  win.webContents.on('console-message', (_event, level, message) => { if (level === 3) report.errors.push(message); });
  win.webContents.session.webRequest.onBeforeRequest({ urls: [`${api}/*`] }, (details, callback) => {
    if (details.method === 'POST') {
      const bytes = (details.uploadData || []).filter((item) => item.bytes).map((item) => item.bytes);
      const raw = Buffer.concat(bytes).toString('utf8');
      let body;
      try { body = JSON.parse(raw); } catch { body = raw; }
      report.requests.push({ url: details.url, method: details.method, body, at: Date.now() }); checkpoint();
    }
    callback({ cancel: false });
  });
  await win.loadURL(api);
  await click('BIBLIOTECA', 'document');
  await wait('exact library source', () => ev((filename) => {
    const container = document.querySelector('[data-active="true"]');
    const stem = filename.replace(/\.mp3$/i, '');
    const title = [...container.querySelectorAll('span')].find((node) => node.textContent === filename || node.textContent === stem);
    const row = title?.closest('div.border-b');
    const action = [...(row?.querySelectorAll('button') || [])].find((node) => node.textContent.trim() === 'ACCIONES');
    if (!action) return false;
    row.dataset.r11Source = filename; action.scrollIntoView({ block: 'center' }); action.click(); return true;
  }, manifest.source_name));
  await click('REMIX', `[data-active="true"] [data-r11-source="${manifest.source_name}"]`);
  await wait('exact remix source mounted', () => ev((query, filename) => {
    const workspace = document.querySelector(query);
    return workspace?.textContent.includes(filename) && workspace.querySelector('[aria-label="Qué hacer"]')?.options.length === 5;
  }, panel, manifest.source_name));
  await set('Qué hacer', 'groups');
  await click('SEPARAR PISTAS DEL ORIGINAL');
  await wait('four new actual stems', async () => {
    const count = await ev((query) => document.querySelector(query)?.querySelectorAll('select[aria-label^="Acción de"]').length, panel);
    const request = report.requests.find((req) => new URL(req.url).pathname === '/music/remix/separate');
    return count === 4 && request?.body.file_name === manifest.source_name;
  });
  const jobs = await apiGet('/music/jobs');
  const separation = jobs.items.filter((job) => job.stage === manifest.source_name && job.status === 'succeeded' && !job.audio_url).at(-1);
  if (!separation) throw new Error('New separation job not found');
  report.separation_id = separation.job_id;
  report.separation = await apiGet('/audio/separate/' + separation.job_id);
  if (!report.separation.result?.groups || report.separation.result.groups.length !== 4) throw new Error('Four stem API missing');
  await click('SOLO');
  report.solo = await wait('SOLO plays decoded actual stem without overlap', () => ev((query) => {
    const audio = document.querySelector(query).querySelector('audio[aria-label^="Escuchar "]');
    if (!audio) return false;
    audio.muted = true;
    return audio.readyState >= 2 && !audio.paused && !audio.error && audio.currentTime > 0 ?
      { src: audio.src, duration: audio.duration, current_time: audio.currentTime,
        playing: [...document.querySelectorAll('audio')].filter((a) => !a.paused).length } : false;
  }, panel));
  if (report.solo.playing !== 1) throw new Error('SOLO overlaps another audio');
  await click('CERRAR SOLO');
  await set('Acción de Voz', 'remove');
  await set('BPM del remix', manifest.bpm);
  await set('BPM original de las pistas', manifest.source_bpm);
  await set('Minutos del remix', Math.floor(manifest.duration_seconds / 60));
  await set('Segundos del remix', manifest.duration_seconds % 60);
  await click('RECORTE');
  await set('Inicio del recorte', manifest.repeat_start);
  await set('Final del recorte', manifest.repeat_end);
  await click('PARÁMETROS DEL MOTOR', `${panel} > [data-effective-preview]`);
  await click('OPERACIONES DE AUDIO', `${panel} > [data-effective-preview]`);
  report.preview_operations = await wait('live preview has tempo and repeat operations', () => ev((query, expected) => {
    const pre = document.querySelector(query).querySelector('[data-audio-operations]');
    if (!pre) return false;
    const operations = JSON.parse(pre.textContent);
    return operations.timeline?.target_duration_seconds === expected.duration_seconds && operations.timeline?.source_bpm === expected.source_bpm &&
      operations.timeline?.target_bpm === expected.bpm && operations.timeline?.repeat_start === expected.repeat_start &&
      operations.timeline?.repeat_end === expected.repeat_end && operations.timeline?.method === 'continue_bed' ? operations : false;
  }, panel, manifest));
  await capture([1400, 900]);
  await capture([1080, 700]);
  const previousIds = new Set((await apiGet('/music/jobs')).items.map((job) => job.job_id));
  await click('REMIX');
  report.project_request = await wait('actual HTTP project has BPM source and final duration', () => {
    const req = report.requests.find((r) => new URL(r.url).pathname === '/music/remix/project' && r.body.source_name === manifest.source_name);
    if (!req) return false;
    if (req.body.bpm !== manifest.bpm || req.body.source_bpm !== manifest.source_bpm || req.body.duration_seconds !== manifest.duration_seconds ||
        req.body.repeat_start !== manifest.repeat_start || req.body.repeat_end !== manifest.repeat_end || req.body.transition_seconds != null ||
        req.body.groups.vocals !== 'remove' || Object.values(req.body.groups).filter((v) => v === 'keep').length !== 3) throw new Error(JSON.stringify(req));
    return req.body;
  });
  const id = await wait('actual project job appears', async () => {
    const jobs = await apiGet('/music/jobs');
    return jobs.items.find((job) => !previousIds.has(job.job_id) && job.stage === manifest.source_name)?.job_id;
  });
  report.job_id = id; checkpoint();
  report.project = await wait('real deterministic tempo and repeat mix succeeds', async () => {
    const job = await apiGet('/audio/remix/ai/' + id);
    if (job.status === 'failed') throw new Error(JSON.stringify(job));
    return job.status === 'succeeded' ? job : false;
  });
  await wait('UI result comparison is decoded', () => ev((query) => {
    const button = [...document.querySelector(query).querySelectorAll('[data-audio-comparator] button')].find((el) => el.textContent.startsWith('VARIANTE A'));
    return !!button;
  }, panel));
  await ev((query) => {
    const button = [...document.querySelector(query).querySelectorAll('[data-audio-comparator] button')].find((el) => el.textContent.startsWith('VARIANTE A'));
    button.click();
  }, panel);
  report.result_audio = await wait('actual result audio decodes with extended duration', () => ev((query, duration) => {
    const audio = document.querySelector(query).querySelector('audio[aria-label="Reproductor de comparación"]');
    return audio && audio.readyState >= 2 && !audio.error && Math.abs(audio.duration - duration) < 0.15 ?
      { src: audio.src, duration: audio.duration, ready_state: audio.readyState } : false;
  }, panel, manifest.duration_seconds));
  await capture([1400, 900]);
  if (report.errors.length) throw new Error(report.errors.join(' | '));
  finish(0);
}).catch((error) => finish(1, error));
