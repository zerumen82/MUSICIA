/** Current served UI audit. Real requests/audio; no mocks, GPU jobs or deletion. */
const fs = require('node:fs');
const path = require('node:path');
const { app, BrowserWindow } = require('electron');
const root = path.resolve(__dirname, '..');
const api = process.env.MUSICIA_API_URL || 'http://127.0.0.1:8000';
const source = process.env.MUSICIA_AUDIT_SOURCE;
const upload = process.env.MUSICIA_AUDIT_UPLOAD;
const cpu = process.env.MUSICIA_AUDIT_CPU === '1';
const phase = process.env.MUSICIA_AUDIT_PHASE || 'full';
const timeout = Number(process.env.MUSICIA_AUDIT_TIMEOUT_MS || 120000);
const id = Date.now().toString(36);
const dir = path.join(root, 'logs', `functional-ui-audit-${id}`);
fs.mkdirSync(dir, { recursive: true });
app.setPath('userData', path.join(dir, 'profile'));
const report = { status: 'RUNNING', id, source, upload, cpu, phase, started_at: new Date().toISOString(),
  criteria: [], frames: [], requests: [], responses: [], console_errors: [],
  limits: ['No GPU generation, source analysis, separation, shutdown or cancellation in this audit.',
    'Existing files are never renamed or deleted.', 'Artistic quality requires listening.'] };
let win;
let done = false;
const save = () => fs.writeFileSync(path.join(dir, 'result.json'), JSON.stringify(report, null, 2));
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const ev = (fn, ...args) => win.webContents.executeJavaScript(`(${fn.toString()})(...${JSON.stringify(args)})`, true);
const active = (selector) => `[data-active="true"] ${selector}`;
async function wait(label, fn) {
  const limit = Date.now() + timeout;
  while (Date.now() < limit) { const value = await fn(); if (value) return value; await sleep(200); }
  throw new Error(`Timeout: ${label}`);
}
async function render() {
  await ev(() => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve))));
}
async function click(text, scope = '[data-active="true"]') {
  await wait(`visible enabled ${text}`, () => ev((label, query) => {
    const parent = document.querySelector(query);
    const matches = [...(parent?.querySelectorAll('button,summary') || [])].filter((node) =>
      !node.matches(':disabled') && node.getClientRects().length &&
      (node.textContent.trim() === label || [...node.querySelectorAll('span')].some((span) => span.textContent.trim() === label)));
    if (matches.length !== 1) return false;
    matches[0].scrollIntoView({ block: 'center' }); matches[0].click(); return true;
  }, text, scope));
  await render();
}
async function set(selector, value) {
  await ev((query, next) => {
    const node = document.querySelector(query);
    if (!node || !node.getClientRects().length || node.matches(':disabled')) throw new Error(`Unavailable control ${query}`);
    node.scrollIntoView({ block: 'center' });
    Object.getOwnPropertyDescriptor(Object.getPrototypeOf(node), 'value').set.call(node, next);
    node.dispatchEvent(new Event(node.tagName === 'SELECT' ? 'change' : 'input', { bubbles: true }));
  }, selector, value);
  await render();
}
async function tab(label, panel) {
  await click(label, 'nav');
  await wait(`active ${panel}`, () => ev((name) => document.querySelector(`[data-panel="${name}"]`)?.dataset.active === 'true', panel));
  await render();
}
async function frame(name, target) {
  if (target) await ev((query) => document.querySelector(query)?.scrollIntoView({ block: 'center' }), target);
  await render();
  const snapshot = await ev(() => {
    const panel = document.querySelector('[data-active="true"]');
    const onScreen = (node) => { const box = node.getBoundingClientRect(); return node.getClientRects().length && box.width > 0 && box.height > 0 && box.left >= 0 && box.top >= 0 && box.right <= innerWidth && box.bottom <= innerHeight; };
    const nodes = [...panel.querySelectorAll('button,input,select,textarea,summary,a')].filter((node) => node.getClientRects().length);
    return { at: new Date().toISOString(), panel: panel.dataset.panel, width: innerWidth, height: innerHeight,
      header: document.querySelector('header')?.innerText, panel_text: panel.innerText,
      visible_controls: nodes.filter(onScreen).map((node) => ({ text: node.innerText || node.getAttribute('aria-label') || node.placeholder || node.title,
        disabled: node.matches(':disabled'), bounds: node.getBoundingClientRect().toJSON() })),
      horizontal_overflow: panel.scrollWidth > panel.clientWidth || document.documentElement.scrollWidth > innerWidth,
      fixed_overflow: [...document.querySelectorAll('.fixed')].filter((node) => node.getClientRects().length).map((node) => ({ text: node.innerText.slice(0, 160), bounds: node.getBoundingClientRect().toJSON() })).filter((node) => node.bounds.left < 0 || node.bounds.right > innerWidth),
    };
  });
  fs.writeFileSync(path.join(dir, `${name}.json`), JSON.stringify(snapshot, null, 2));
  fs.writeFileSync(path.join(dir, `${name}.png`), (await win.webContents.capturePage()).toPNG());
  report.frames.push({ name, ...snapshot }); save();
  if (snapshot.horizontal_overflow || snapshot.fixed_overflow.length) throw new Error(`Visible horizontal overflow: ${name}`);
  return snapshot;
}
async function check(label, fn) {
  try { const evidence = await fn(); report.criteria.push({ label, result: 'PASS', evidence }); }
  catch (error) {
    report.criteria.push({ label, result: 'FAIL', error: error.stack || String(error) });
    try { await frame(`failure-${report.criteria.length}`); } catch { /* Original error retained above. */ }
  }
  save();
}
async function choose(label, option) {
  await click(label);
  const menu = await wait(`${label} real options`, () => ev(() => {
    const nodes = [...document.querySelectorAll('[data-active="true"] .fixed')].filter((node) => node.getClientRects().length);
    return nodes.length === 1 ? nodes[0].innerText : false;
  }));
  await frame(`menu-${label}-${report.frames.length}`);
  await click(option, '[data-active="true"] .fixed');
  return menu;
}
async function padding() {
  const values = await ev(() => {
    const pick = (selector) => { const node = document.querySelector(selector); const css = getComputedStyle(node); return { selector, classes: node.className, left: css.paddingLeft, right: css.paddingRight, top: css.paddingTop, bottom: css.paddingBottom }; };
    return { rem: parseFloat(getComputedStyle(document.documentElement).fontSize), aside: pick('aside'),
      composer: pick('[data-panel="composer"] > div'), header: pick('header'),
      button_h8: (() => { const node = [...document.querySelectorAll('[data-panel="composer"] button')].find((button) => button.classList.contains('h-8')); const css = getComputedStyle(node); return { text: node.innerText, height: css.height, classes: node.className }; })() };
  });
  const expected = { aside: { left: values.rem, top: values.rem * 1.25 }, composer: { left: values.rem * 1.5, top: values.rem * 1.5 }, header: { left: values.rem * 1.75 } };
  report.padding_measurements = { values, expected }; save();
  for (const [name, sides] of Object.entries(expected)) for (const [side, target] of Object.entries(sides)) {
    if (Math.abs(parseFloat(values[name][side]) - target) > 0.01) throw new Error(`Declared Tailwind padding lost: ${name}.${side}=${values[name][side]}, expected ${target}px`);
  }
  if (Math.abs(parseFloat(values.button_h8.height) - values.rem * 2) > 0.01) throw new Error(`h-8 button height overridden: ${values.button_h8.height}, expected ${values.rem * 2}px`);
  return report.padding_measurements;
}
async function creation() {
  await tab('CREAR', 'composer');
  await check('CREAR: empty prompt blocks generation', async () => {
    await set(active('[aria-label="Prompt de crear"]'), '');
    const value = await ev(() => [...document.querySelectorAll('[data-active="true"] button')].find((node) => node.textContent.trim() === 'GENERAR')?.disabled);
    if (!value) throw new Error('GENERAR enabled with empty prompt'); return value;
  });
  await check('CREAR: glossary adds a real genre and marks it chosen', async () => {
    await set(active('[aria-label="Prompt de crear"]'), 'Jazz con contrabajo');
    await click('GLOSARIO');
    await set(active('input[placeholder="Buscar estilo o subestilo…"]'), 'techno');
    await wait('literal glossary entry', () => ev(() => [...document.querySelectorAll('[data-active="true"] .fixed button')].some((node) => node.textContent.trim() === 'techno')));
    await frame('crear-glossary-search', active('input[placeholder="Buscar estilo o subestilo…"]'));
    await click('techno', '[data-active="true"] .fixed');
    const prompt = await ev(() => document.querySelector('[data-active="true"] [aria-label="Prompt de crear"]').value);
    if (!prompt.endsWith('techno')) throw new Error(prompt);
    await click('GLOSARIO');
    await wait('chosen real glossary entry', () => ev(() => document.querySelector('[data-active="true"] .fixed')?.innerText.includes('ELEGIDO')));
    await ev(() => document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true })));
    return prompt;
  });
  await check('CREAR: optional improve draft leaves original unchanged until applied', async () => {
    const original = 'Jazz con contrabajo; batería suave al fondo, sin añadir instrumentos';
    await set(active('[aria-label="Prompt de crear"]'), original); await click('MEJORAR PROMPT');
    const draft = await wait('real draft response visible', () => ev(() => document.querySelector('[data-active="true"] [aria-label="Borrador del prompt"]')?.value));
    if (await ev(() => document.querySelector('[data-active="true"] [aria-label="Prompt de crear"]').value) !== original) throw new Error('Draft rewrote original');
    await frame('crear-optional-draft', active('[aria-label="Borrador del prompt"]'));
    await click('DESCARTAR'); return { original, draft };
  });
  await check('CREAR: selected BPM/key/meter reach the real preview', async () => {
    await choose('BPM', '140'); await choose('TONO', 'La m');
    await choose('COMPÁS', '3/4');
    await click('VER LO QUE SE ENVÍA');
    const value = await wait('real preview selected controls', () => ev(() => {
      const pre = document.querySelector('[data-active="true"] [data-engine-parameters]'); if (!pre) return false;
      const data = JSON.parse(pre.textContent); return data.bpm === 140 && data.time_signature === '3/4' && data.key_scale === 'A minor' ? data : false;
    }));
    await frame('crear-effective-preview', active('[data-engine-parameters]')); return value;
  });
  await check('CREAR: conflicting text/control produces real visible API error', async () => {
    await set(active('[aria-label="Prompt de crear"]'), 'techno a 180 BPM');
    const error = await wait('real preview rejection', () => ev(() => document.querySelector('[data-active="true"] [data-effective-preview] [role="alert"]')?.innerText));
    if (!/BPM|tempo/i.test(error)) throw new Error(error);
    await frame('crear-real-conflict-error', active('[role="alert"]')); return error;
  });
  await check('CREAR: vocal controls and lyric structuring update actual preview', async () => {
    await choose('BPM', 'AUTO'); await choose('COMPÁS', 'AUTO');
    await set(active('[aria-label="Prompt de crear"]'), 'Una canción tranquila'); await click('CANCIÓN CON VOZ');
    await set(active('textarea[placeholder^="Letra que se canta"]'), 'Hoy camino despacio\nLa ciudad se queda atrás');
    await click('ESTRUCTURAR LETRA');
    const value = await wait('structured lyrics reach preview', () => ev(() => {
      const pre = document.querySelector('[data-active="true"] [data-engine-parameters]'); if (!pre) return false;
      const data = JSON.parse(pre.textContent); return data.lyrics.includes('[Verse]') && data.lyrics.includes('La ciudad') ? data : false;
    }));
    await frame('crear-vocal-lyrics', active('textarea[placeholder^="Letra que se canta"]')); await click('MÚSICA'); return value;
  });
}
async function locate(name) {
  return wait(`exact row ${name}`, () => ev((filename) => {
    const title = [...document.querySelectorAll('[data-active="true"] span')].find((node) => node.textContent === filename || node.textContent === filename.replace(/\.mp3$/i, ''));
    const row = title?.closest('div.border-b'); if (!row) return false;
    row.dataset.auditSource = filename; return true;
  }, name));
}
const rowSelector = (name) => active(`[data-audit-source=${JSON.stringify(name)}]`);
async function playback(name, kind) {
  await locate(name);
  await ev((query) => { const button = document.querySelector(query).querySelector('button'); button.scrollIntoView({ block: 'center' }); button.click(); }, rowSelector(name));
  const audio = await wait(`served ${kind} audio plays`, () => ev((filename) => {
    const audio = [...document.querySelectorAll('[data-active="true"] audio')].find((node) => decodeURIComponent(new URL(node.src).pathname).endsWith('/' + filename));
    return audio && audio.readyState >= 2 && !audio.paused && !audio.error && audio.duration > 0 ? { src: audio.src, duration: audio.duration, time: audio.currentTime } : false;
  }, name));
  await frame(`${kind}-real-playback`, active('audio'));
  await ev(() => [...document.querySelectorAll('audio')].forEach((node) => node.pause())); return audio;
}
async function library() {
  await tab('BIBLIOTECA', 'library');
  await check('BIBLIOTECA: exact real source playback', () => playback(source, 'library'));
  await check('BIBLIOTECA: exact source menu, download and cancel deletion', async () => {
    await locate(source); await click('ACCIONES', rowSelector(source));
    const menu = await ev((query) => [...document.querySelector(query).querySelectorAll('[data-acciones] button,a')].filter((node) => node.getClientRects().length).map((node) => ({ text: node.innerText, href: node.href })), rowSelector(source));
    if (!menu.some((node) => node.text === 'BAJAR' && decodeURIComponent(new URL(node.href).pathname).endsWith('/' + source))) throw new Error('Download points at different source');
    await frame('library-exact-menu', rowSelector(source));
    await click('BORRAR', rowSelector(source)); await frame('library-delete-confirmation', rowSelector(source));
    await click('NO', rowSelector(source)); return menu;
  });
  await check('BIBLIOTECA: selection can be entered and exited without deletion', async () => {
    await click('SELECCIONAR'); await frame('library-selection');
    await click('SALIR'); return true;
  });
}
async function uploads() {
  await tab('SUBIR', 'uploads');
  await check('SUBIR: exact existing upload playback', () => playback(upload, 'upload'));
  await check('SUBIR: file picker is keyboard reachable', async () => {
    const value = await ev(() => {
      const input = document.querySelector('[data-active="true"] input[type="file"]');
      const zone = input.parentElement;
      return { native_input_visible: input.getClientRects().length > 0, parent_tag: zone.tagName,
        parent_role: zone.getAttribute('role'), parent_tabindex: zone.getAttribute('tabindex') };
    });
    if (!value.native_input_visible && value.parent_role !== 'button' && value.parent_tabindex === null) throw new Error(JSON.stringify(value));
    return value;
  });
}
async function mix() {
  await tab('MEZCLA', 'mix');
  await check('MEZCLA: requires base and vocal before mixing', async () => {
    const disabled = await ev(() => [...document.querySelectorAll('[data-active="true"] button')].find((node) => node.textContent.trim() === 'MEZCLAR')?.disabled);
    if (!disabled) throw new Error('Mix enabled without two inputs'); return disabled;
  });
  await check('MEZCLA: real sources reach the real arrangement plan', async () => {
    await choose('BASE', `${source} · bib`); await choose('VOZ', `${upload} · sub`);
    await wait('real mix plan response', () => report.responses.some((entry) => new URL(entry.url).pathname === '/audio/mix/plan' && entry.status_code === 200));
    await frame('mix-real-plan'); return report.requests.filter((entry) => new URL(entry.url).pathname === '/audio/mix/plan');
  });
  if (!cpu) { report.criteria.push({ label: 'MEZCLA: new ffmpeg mix/crossfade exports', result: 'NO-VERIFICADO', reason: 'Enable MUSICIA_AUDIT_CPU=1 for real reversible exports.' }); return; }
  await check('MEZCLA: actual ffmpeg export and served playback', async () => {
    await set(active('[aria-label="Nombre de la mezcla"]'), `auditoria-mix-${id}`); await click('MEZCLAR');
    const audio = await wait('actual completed mixture', () => ev((prefix) => {
      const player = document.querySelector('[data-active="true"] audio[controls]');
      return player?.src.includes(prefix) && player.readyState >= 2 && player.duration > 0 && !player.error ? { src: player.src, duration: player.duration } : false;
    }, `auditoria-mix-${id}`));
    await frame('mix-completed', active('audio[controls]')); await ev(() => [...document.querySelectorAll('audio')].forEach((node) => node.pause())); return audio;
  });
}
function finish(error) {
  if (done) return; done = true;
  if (error) report.criteria.push({ label: 'Audit execution', result: 'FAIL', error: error.stack || String(error) });
  report.status = report.criteria.some((item) => item.result === 'FAIL') || report.console_errors.length ? 'FAIL' : 'PASS';
  report.completed_at = new Date().toISOString(); save();
  console.log(JSON.stringify({ status: report.status, evidence: dir }));
  if (win && !win.isDestroyed()) win.destroy(); app.exit(report.status === 'PASS' ? 0 : 1);
}
process.on('uncaughtException', finish); process.on('unhandledRejection', finish);
app.whenReady().then(async () => {
  if (!source || !upload || !['127.0.0.1', 'localhost'].includes(new URL(api).hostname)) throw new Error('Exact existing source/upload and local API required');
  win = new BrowserWindow({ width: 1400, height: 900, show: true, webPreferences: { sandbox: true, contextIsolation: true, nodeIntegration: false } });
  win.webContents.on('console-message', (_event, level, message) => { if (level >= 3) report.console_errors.push(message); });
  win.webContents.session.webRequest.onBeforeRequest({ urls: [api + '/*'] }, (details, callback) => {
    if (['POST', 'DELETE', 'PATCH'].includes(details.method)) {
      const bytes = Buffer.concat((details.uploadData || []).filter((item) => item.bytes).map((item) => item.bytes));
      let body; try { body = JSON.parse(bytes.toString()); } catch { body = { multipart_bytes: bytes.length }; }
      report.requests.push({ at: new Date().toISOString(), request_id: details.id, url: details.url, method: details.method, body });
    }
    callback({ cancel: false });
  });
  win.webContents.session.webRequest.onCompleted({ urls: [api + '/*'] }, (details) => report.responses.push({ request_id: details.id, url: details.url, status_code: details.statusCode }));
  await win.loadURL(api);
  await wait('real app shell', () => ev(() => document.querySelectorAll('nav button').length >= 4));
  await check('Global declared spacing matches rendered CSS', padding);
  await check('CREAR: recent completed queue matches real newest playable jobs', async () => {
    await tab('CREAR', 'composer');
    await wait('real polled job feed mounted', () => ev(() => document.querySelector('[data-active="true"]')?.innerText.includes('COLA DE TRABAJOS')));
    const jobs = await ev(async (base) => (await (await fetch(base + '/music/jobs')).json()).items, api);
    const newest = jobs.filter((job) => job.status === 'succeeded' && job.output_name).sort((a, b) => (b.created_at || '').localeCompare(a.created_at || '')).slice(0, 8);
    const visible = await ev(() => [...document.querySelectorAll('[data-active="true"] a[download]')].map((link) => ({ text: link.innerText, href: link.href })));
    report.jobs_queue = { newest, actual_downloads: visible }; save();
    const invalid = visible.filter((item) => /\/(?:undefined|null)$/.test(new URL(item.href).pathname));
    if (invalid.length) throw new Error(`Invalid completed audio link: ${JSON.stringify(invalid)}`);
    if (newest.some((job) => !visible.some((item) => decodeURIComponent(new URL(item.href).pathname).endsWith('/' + job.output_name)))) throw new Error('Newest playable completed jobs absent from queue');
    return report.jobs_queue;
  });
  for (const [label, panel] of [['CREAR', 'composer'], ['SUBIR', 'uploads'], ['MEZCLA', 'mix'], ['BIBLIOTECA', 'library']]) {
    await check(`${label}: actual visible layout at both requested sizes`, async () => {
      await tab(label, panel);
      const frames = [];
      for (const [width, height] of [[1400, 900], [1080, 700]]) {
        win.setContentSize(width, height); await render(); frames.push(await frame(`${panel}-${width}x${height}`));
      }
      return frames.map((item) => ({ width: item.width, height: item.height, overflow: item.horizontal_overflow }));
    });
  }
  if (phase === 'baseline') {
    await tab('SUBIR', 'uploads');
    await check('SUBIR: upload zone native keyboard reachability', async () => {
      const value = await ev(() => { const input = document.querySelector('[data-active="true"] input[type="file"]'); const parent = input.parentElement;
        return { input_visible: input.getClientRects().length > 0, role: parent.getAttribute('role'), tabindex: parent.getAttribute('tabindex') }; });
      report.upload_keyboard = value; save();
      if (!value.input_visible && value.role !== 'button' && value.tabindex === null) throw new Error(JSON.stringify(value)); return value;
    });
    finish(); return;
  }
  win.setContentSize(1080, 700);
  await creation(); await uploads(); await mix(); await library();
  const forbidden = report.requests.filter((entry) => ['/music/generate', '/music/remix/project', '/music/remix/analyze', '/audio/separate', '/music/jobs/cancel'].includes(new URL(entry.url).pathname) || entry.method === 'DELETE');
  if (forbidden.length) throw new Error(`Unexpected GPU/destructive request: ${JSON.stringify(forbidden)}`);
  finish();
}).catch(finish);
