/** Real served React/Electron R9 interaction. No mocked responses or packages. */
const fs = require('node:fs');
const path = require('node:path');
const { app, BrowserWindow } = require('electron');
const { randomUUID } = require('node:crypto');

const root = path.resolve(__dirname, '..');
const runId = randomUUID().slice(0, 8);
const dir = path.join(root, 'logs', `remix-integral-ui-${runId}`);
const api = process.env.MUSICIA_API_URL || 'http://127.0.0.1:8000';
const source = process.env.MUSICIA_PROBE_SOURCE || 'pista-sin-nombre (2).mp3';
const timeout = Number(process.env.MUSICIA_PROBE_TIMEOUT_MS || 180000);
const report = { status: 'RUNNING', run_id: runId, source, steps: [], errors: [] };
fs.mkdirSync(dir, { recursive: true });
app.setPath('userData', path.join(dir, 'profile'));
let window;
let finished = false;
function finish(code, error) {
  if (finished) return;
  finished = true;
  report.status = code ? 'FAIL' : 'PASS';
  if (error) report.error = error.stack || String(error);
  fs.writeFileSync(path.join(dir, 'result.json'), JSON.stringify(report, null, 2));
  console.log(JSON.stringify({ status: report.status, evidence: dir, error: report.error }));
  if (window && !window.isDestroyed()) window.destroy();
  app.exit(code);
}
process.on('uncaughtException', (error) => finish(1, error));
process.on('unhandledRejection', (error) => finish(1, error));
app.on('window-all-closed', () => {});

async function evaluate(fn, ...args) {
  return window.webContents.executeJavaScript(`(${fn.toString()})(...${JSON.stringify(args)})`, true);
}
async function wait(label, condition) {
  const deadline = Date.now() + timeout;
  while (Date.now() < deadline) {
    const value = await condition();
    if (value) { report.steps.push({ label, value }); return value; }
    await new Promise((resolve) => setTimeout(resolve, 200));
  }
  throw new Error(`Timeout: ${label}`);
}
async function choose(id) {
  await wait(`Choose ${id}`, () => evaluate((value) => {
    const select = document.querySelector('[aria-label="Qué hacer"]');
    if (!select) return false;
    Object.getOwnPropertyDescriptor(Object.getPrototypeOf(select), 'value').set.call(select, value);
    select.dispatchEvent(new Event('change', { bubbles: true }));
    return select.value === value;
  }, id));
}
async function click(label, panel = true) {
  await wait(`Click ${label}`, () => evaluate((text, inPanel) => {
    const parent = inPanel ? document.querySelector('[data-remix-project]') : document;
    const target = [...(parent?.querySelectorAll('button,summary') || [])].find((item) => !item.disabled && (item.textContent.trim() === text || [...item.querySelectorAll('span')].some((span) => span.textContent.trim() === text)));
    if (!target) return false;
    target.click(); return true;
  }, label, panel));
}
async function set(selector, value) {
  await evaluate((query, next) => {
    const element = document.querySelector(query);
    if (!element) throw new Error(`Missing field ${query}`);
    const nativeSet = Object.getOwnPropertyDescriptor(Object.getPrototypeOf(element), 'value').set;
    nativeSet.call(element, next);
    element.dispatchEvent(new Event(element.tagName === 'SELECT' ? 'change' : 'input', { bubbles: true }));
  }, selector, value);
}

app.whenReady().then(async () => {
  if (!['127.0.0.1', 'localhost'].includes(new URL(api).hostname)) throw new Error('Local API only');
  window = new BrowserWindow({ width: 1400, height: 900, show: false,
    webPreferences: { sandbox: true, contextIsolation: true, nodeIntegration: false } });
  window.webContents.on('console-message', (_event, level, message) => { if (level === 3) report.errors.push(message); });
  await window.loadURL(api);
  await click('BIBLIOTECA', false);
  await wait('Original library row', () => evaluate((name) => {
    const stem = name.replace(/\.mp3$/, '');
    const title = [...document.querySelectorAll('main span')].find((item) => item.textContent === stem);
    const row = title?.closest('[class~="border-b"]');
    const action = [...(row?.querySelectorAll('button') || [])].find((item) => item.textContent.trim() === 'REMIX');
    if (!action) return false;
    action.click(); return true;
  }, source));
  await wait('Action menu loaded', () => evaluate(() => document.querySelector('[aria-label="Qué hacer"]')?.options.length >= 5));
  await wait('Automatic real analysis completed', () => evaluate(() => {
    const panel = document.querySelector('[data-remix-project]');
    if (panel.textContent.includes('Detección no disponible')) throw new Error(panel.textContent);
    return panel.querySelector('select[aria-label="Clasificación del audio original"]') && !panel.textContent.includes('Analizando') && !panel.textContent.includes('Esperando análisis');
  }));
  const literal = 'Jazz con contrabajo; batería suave al fondo, sin añadir instrumentos';
  await set('[aria-label="Prompt del remix"]', literal);
  await set('[aria-label="Clasificación del audio original"]', 'electronic');
  await click('REFERENCIA Y AVANZADOS');
  await evaluate(() => {
    const summary = [...document.querySelectorAll('[data-remix-project] summary')].find((item) => item.textContent === 'ENVÍO EFECTIVO');
    if (!summary) throw new Error('Missing effective payload'); summary.click();
  });
  report.full_preview = await wait('Literal preview without recipes', () => evaluate((text) => {
    const element = document.querySelector('[data-remix-project] pre');
    if (!element) return false;
    const payload = JSON.parse(element.textContent);
    return payload.prompt === text && payload.source_classification === 'electronic' && payload.instrumental === undefined ? payload : false;
  }, literal));
  fs.writeFileSync(path.join(dir, 'full-1400x900.png'), (await window.webContents.capturePage()).toPNG());
  await choose('region');
  await set('[aria-label="Inicio del tramo"]', '6');
  await set('[aria-label="Final del tramo"]', '18');
  report.region_preview = await wait('Explicit regional payload', () => evaluate(() => {
    const payload = JSON.parse(document.querySelector('[data-remix-project] pre').textContent);
    return payload.scope === 'region' && payload.region_start === 6 && payload.region_end === 18 ? payload : false;
  }));
  fs.writeFileSync(path.join(dir, 'region-1400x900.png'), (await window.webContents.capturePage()).toPNG());
  await choose('groups');
  await click('SEPARAR PISTAS DEL ORIGINAL');
  await wait('Four actual separated groups', () => evaluate(() => document.querySelectorAll('[data-remix-project] select[aria-label^="Acción de"]').length === 4));
  report.group_labels = await evaluate(() => [...document.querySelectorAll('[data-remix-project] select[aria-label^="Acción de"]')].map((item) => item.getAttribute('aria-label')));
  await evaluate(() => {
    const select = [...document.querySelectorAll('[data-remix-project] select[aria-label^="Acción de"]')].find((item) => /voz/i.test(item.getAttribute('aria-label')));
    if (!select) throw new Error('Real voice group missing');
    Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'value').set.call(select, 'remove');
    select.dispatchEvent(new Event('change', { bubbles: true }));
  });
  await set('[aria-label="Prompt del remix"]', '');
  report.groups_preview = await wait('One action per actual group', () => evaluate(() => {
    const payload = JSON.parse(document.querySelector('[data-remix-project] pre').textContent);
    return payload.scope === 'groups' && payload.groups.vocals === 'remove' && Object.values(payload.groups).filter((item) => item === 'keep').length === 3 ? payload : false;
  }));
  await evaluate(() => {
    const solo = [...document.querySelectorAll('[data-remix-project] button')].find((item) => item.textContent === 'SOLO');
    solo.click();
  });
  report.solo_audio = await wait('Actual stem audio resource', () => evaluate(() => {
    const audio = document.querySelector('[data-remix-project] audio[aria-label^="Escuchar "]:not([aria-label="Escuchar original"])');
    if (!audio) return false;
    audio.muted = true;
    return audio.readyState >= audio.HAVE_CURRENT_DATA && !audio.error ? { src: audio.src, ready_state: audio.readyState, current_time: audio.currentTime } : false;
  }));
  await set('[aria-label="Nombre del remix"]', `prueba-ui-remix-${runId}`);
  await click('REMIX');
  await wait('Real deterministic mix exported', () => evaluate(() => document.querySelector('[data-remix-project] audio[aria-label="Escuchar variante 1"]')));
  report.final_ui = await evaluate(() => ({ text: document.querySelector('[data-remix-project]').textContent,
    audio: document.querySelector('[data-remix-project] audio[aria-label="Escuchar variante 1"]').src,
    horizontal_overflow: document.documentElement.scrollWidth > window.innerWidth }));
  if (report.final_ui.horizontal_overflow) throw new Error('Horizontal overflow at actual Electron size');
  fs.writeFileSync(path.join(dir, 'groups-1400x900.png'), (await window.webContents.capturePage()).toPNG());
  window.setSize(1280, 800);
  report.compact_overflow = await evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
  if (report.compact_overflow) throw new Error('Horizontal overflow at 1280x800');
  fs.writeFileSync(path.join(dir, 'groups-1280x800.png'), (await window.webContents.capturePage()).toPNG());
  if (report.errors.length) throw new Error(`Console errors: ${report.errors.join(' | ')}`);
  finish(0);
}).catch((error) => finish(1, error));
