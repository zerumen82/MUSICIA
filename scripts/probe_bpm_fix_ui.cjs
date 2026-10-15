/** B6 served React/Electron probe; observed real requests, no substituted responses. */
const fs = require('node:fs');
const path = require('node:path');
const { app, BrowserWindow } = require('electron');
const root = path.resolve(__dirname, '..');
const manifest = JSON.parse(fs.readFileSync(process.env.MUSICIA_B6_MANIFEST, 'utf8').replace(/^\uFEFF/, ''));
const dir = process.env.MUSICIA_B6_OUTPUT;
const api = process.env.MUSICIA_API_URL || 'http://127.0.0.1:8000';
const timeout = Number(process.env.MUSICIA_PROBE_TIMEOUT_MS || 1200000);
const verifyFull = process.env.MUSICIA_B6_FULL_VERIFY === '1';
const fullSeed = process.env.MUSICIA_B6_SEED ? Number(process.env.MUSICIA_B6_SEED) : null;
const panel = '[data-active="true"] [data-remix-project]';
const report = { status: 'RUNNING', manifest, requests: [], steps: [], errors: [] };
fs.mkdirSync(dir, { recursive: true });
if (fs.existsSync(path.join(dir, 'result.json'))) throw new Error('Use a fresh evidence directory');
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
async function repeatWarning(scope) {
  const visible = await ev((query) => document.querySelector(query)?.querySelector('[data-remix-repeat-clock]')?.checkVisibility(), panel);
  if (!visible) await click('REPETICIÓN Y TRANSICIONES');
  return wait(`actual ${scope} beat-aligned repetition warning visible`, () => ev((query) => {
    const node = document.querySelector(query)?.querySelector('[data-remix-repeat-clock]');
    return node?.checkVisibility() && /dentro del intervalo elegido/.test(node.textContent) && /registrados en el resultado/.test(node.textContent) ? node.textContent : false;
  }, panel));
}
async function executedInspector(job, scope) {
  await click('PARÁMETROS Y SEMILLAS EJECUTADOS');
  const expectedFiles = job.result.metadata.map((variant) => variant.file_name);
  const inspected = await wait(`actual ${scope} inspector has each effective arrangement and beat clock`, () => ev((query, files) => {
    const detail = [...document.querySelector(query).querySelectorAll('details')].find((node) => node.querySelector('summary')?.textContent.includes('PARÁMETROS Y SEMILLAS EJECUTADOS'));
    const pre = detail?.querySelector('pre');
    if (!pre?.checkVisibility()) return false;
    const value = JSON.parse(pre.textContent);
    return value.variants?.length === files.length && value.variants.every((variant, index) => variant.file_name === files[index] && variant.timeline && variant.arrangement?.seam_method === 'beat_clock_aligned') ? value : false;
  }, panel, expectedFiles));
  const actual = job.result.metadata;
  if (inspected.variants.length !== actual.length) throw new Error(`${scope} inspector variant count differs from real job`);
  inspected.variants.forEach((variant, index) => {
    for (const key of ['file_name', 'seed', 'seed_origin', 'timeline', 'arrangement']) {
      if (JSON.stringify(variant[key]) !== JSON.stringify(actual[index][key])) throw new Error(`${scope} inspector ${key} differs from actual variant ${index}`);
    }
  });
  await capture([1400, 900], `${scope}-executed`);
  await capture([1080, 700], `${scope}-executed`);
  return inspected;
}
async function capture(size, scope = 'groups') {
  win.setContentSize(...size);
  await ev((query) => { document.querySelector(query).scrollIntoView({ block: 'start' }); }, panel);
  await ev(() => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve))));
  await delay(150);
  const metrics = await ev((query) => ({ viewport: [innerWidth, innerHeight], overflow: document.documentElement.scrollWidth > innerWidth,
    text: document.querySelector(query).innerText,
    controls: [...document.querySelector(query).querySelectorAll('input,select,button')]
      .filter((el) => el.checkVisibility({ checkOpacity: true, checkVisibilityCSS: true }))
      .map((el) => ({ label: el.getAttribute('aria-label') || el.textContent.trim(), disabled: el.disabled, value: el.value,
        rect: el.getBoundingClientRect().toJSON(), color: getComputedStyle(el).color, background: getComputedStyle(el).backgroundColor })) }), panel);
  fs.writeFileSync(path.join(dir, `${scope}-${size.join('x')}.png`), (await win.webContents.capturePage()).toPNG());
  if (metrics.overflow) throw new Error(`Horizontal overflow at ${size.join('x')}`);
  const visible = metrics.controls.filter((control) => control.rect.bottom > 0 && control.rect.top < size[1]);
  metrics.overlaps = [];
  for (let i = 0; i < visible.length; i += 1) for (let j = i + 1; j < visible.length; j += 1) {
    const a = visible[i].rect; const b = visible[j].rect;
    if (Math.min(a.right, b.right) - Math.max(a.left, b.left) > 1 && Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top) > 1)
      metrics.overlaps.push([visible[i].label, visible[j].label]);
  }
  report.steps.push({ label: `Layout ${scope} ${size.join('x')}`, value: metrics });
  checkpoint();
  if (metrics.overlaps.length) throw new Error(`Overlapping controls at ${size.join('x')}: ${JSON.stringify(metrics.overlaps)}`);
}

app.whenReady().then(async () => {
  if (!['127.0.0.1', 'localhost'].includes(new URL(api).hostname)) throw new Error('Local API only');
  win = new BrowserWindow({ width: 1400, height: 900, show: false,
    webPreferences: { sandbox: true, contextIsolation: true, nodeIntegration: false } });
  win.webContents.on('console-message', (_event, level, message) => { if (level === 3) report.errors.push(message); });
  win.webContents.session.webRequest.onBeforeRequest({ urls: [`${api}/*`] }, (details, callback) => {
    if (details.method === 'GET' && new URL(details.url).pathname.startsWith('/music/remix/analyze/')) {
      (report.analysis_status_requests ||= []).push({ path: new URL(details.url).pathname, at: Date.now() }); checkpoint();
    }
    if (details.method === 'POST') {
      const bytes = (details.uploadData || []).filter((item) => item.bytes).map((item) => item.bytes);
      const raw = Buffer.concat(bytes).toString('utf8');
      let body;
      try { body = JSON.parse(raw); } catch { body = raw; }
      report.requests.push({ url: details.url, method: details.method, body, at: Date.now() }); checkpoint();
    }
    callback({ cancel: false });
  });
  const existingJobs = await fetch(api + '/music/jobs').then((response) => response.json());
  if (existingJobs.items.some((job) => ['running', 'queued'].includes(job.status))) throw new Error('Active jobs; probe will not submit new work');
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
  await set('BPM del remix', manifest.bpm);
  report.automatic_source = await wait('original BPM automatically measured and precargado', () => ev((query) => {
    const parent = document.querySelector(query);
    const input = parent.querySelector('[aria-label="BPM original de las pistas"]');
    const text = parent.querySelector('[data-source-tempo-measurement]')?.textContent;
    return Number(input?.value) > 0 && text?.includes('Confianza:') && parent.textContent.includes('precargado de la medición automática') ? { value: Number(input.value), text } : false;
  }, panel));
  const manualBpm = report.automatic_source.value + 1;
  await set('BPM original de las pistas', manualBpm);
  await click('MEDIR BPM ORIGINAL');
  await wait('manual BPM preserved after real remeasurement', () => ev((query, manual) => {
    const parent = document.querySelector(query);
    return Number(parent.querySelector('[aria-label="BPM original de las pistas"]').value) === manual &&
      parent.textContent.includes('revisado manualmente') && [...parent.querySelectorAll('button')].some((node) => node.textContent.trim() === 'MEDIR BPM ORIGINAL' && !node.disabled);
  }, panel, manualBpm));
  await set('BPM del remix', manifest.bpm + 1);
  await wait('manual BPM preserved after target BPM change', () => ev((query, manual) => Number(document.querySelector(query).querySelector('[aria-label="BPM original de las pistas"]').value) === manual, panel, manualBpm));
  await set('BPM del remix', manifest.bpm);
  await set('BPM original de las pistas', '');
  await click('MEDIR BPM ORIGINAL');
  await wait('explicit reset restores automatic original BPM', () => ev((query, expected) => {
    const parent = document.querySelector(query);
    return Number(parent.querySelector('[aria-label="BPM original de las pistas"]').value) === expected && parent.textContent.includes('precargado de la medición automática');
  }, panel, report.automatic_source.value));
  const minDuration = Math.ceil(manifest.analysis.duration_seconds * report.automatic_source.value / manifest.bpm);
  await set('Minutos del remix', 0);
  await set('Segundos del remix', minDuration - 1);
  report.minimum = await wait('concrete minimum and blocked short duration visible', () => ev((query, minimum) => {
    const parent = document.querySelector(query);
    const minimumText = parent.querySelector('[data-remix-minimum-duration]')?.textContent;
    const errors = [...parent.querySelectorAll('[role="alert"]')].map((node) => node.textContent);
    const remix = [...parent.querySelectorAll('button')].find((node) => node.textContent.trim() === 'REMIX');
    return minimumText?.includes(`${minimum} s`) && errors.some((text) => text.includes(`${minimum} s`)) && remix?.disabled ? { minimumText, errors, remix_disabled: true } : false;
  }, panel, minDuration));
  await set('Minutos del remix', Math.floor(manifest.duration_seconds / 60));
  await set('Segundos del remix', manifest.duration_seconds % 60);
  await click('REPETICIÓN Y TRANSICIONES');
  await set('Inicio de la parte a repetir', manifest.repeat_start);
  await set('Final de la parte a repetir', manifest.repeat_end);
  await set('Fundido entre repeticiones', manifest.transition_seconds);
  report.group_repeat_warning = await repeatWarning('groups');
  await click('PARÁMETROS DEL MOTOR', `${panel} > [data-effective-preview]`);
  await click('OPERACIONES DE AUDIO', `${panel} > [data-effective-preview]`);
  report.preview_operations = await wait('live preview has tempo and repeat operations', () => ev((query, expected) => {
    const pre = document.querySelector(query).querySelector('[data-audio-operations]');
    if (!pre) return false;
    const operations = JSON.parse(pre.textContent);
    return operations.timeline?.target_duration_seconds === expected.duration_seconds && operations.timeline?.source_bpm_origin === 'measurement' &&
      operations.timeline?.target_bpm === expected.bpm && operations.timeline?.repeat_start === expected.repeat_start &&
      operations.timeline?.repeat_end === expected.repeat_end && operations.timeline?.transition_seconds === expected.transition_seconds ? operations : false;
  }, panel, manifest));
  await capture([1400, 900]);
  await capture([1080, 700]);
  // Full preview must expose pending measurements and the newly authorized DSP.
  await set('Qué hacer', 'full');
  await set('Prompt del remix', 'A track with gabber');
  report.full_repeat_warning = await repeatWarning('full');
  report.full_preview = await wait('full preview honestly declares unresolved per-variant DSP timeline', () => ev((query) => {
    const parent = document.querySelector(query);
    const pre = parent.querySelector('[data-audio-operations]');
    if (!pre) return false;
    const operations = JSON.parse(pre.textContent);
    const text = parent.innerText;
    return operations.scope === 'full' && operations.timeline?.natural_duration_seconds === null && operations.timeline?.tempo_ratio === null &&
      operations.timeline?.tempo_method === 'measured_pcm_atempo' && /sin cambiar el tono/i.test(text) && /después de generar/i.test(text) ? { operations, text } : false;
  }, panel));
  await capture([1400, 900], 'full');
  await capture([1080, 700], 'full');
  await set('Qué hacer', 'region');
  report.region = await wait('regional BPM remains explicitly orientativo', () => ev((query) => {
    const text = document.querySelector(query).innerText;
    return /orienta al motor/i.test(text) ? text : false;
  }, panel));
  await set('Qué hacer', 'groups');
  const previousIds = new Set((await apiGet('/music/jobs')).items.map((job) => job.job_id));
  await click('REMIX');
  report.project_request = await wait('actual HTTP project has BPM source and final duration', () => {
    const req = report.requests.find((r) => new URL(r.url).pathname === '/music/remix/project' && r.body.source_name === manifest.source_name);
    if (!req) return false;
    if (req.body.bpm !== manifest.bpm || req.body.source_bpm !== undefined || req.body.duration_seconds !== manifest.duration_seconds ||
        req.body.repeat_start !== manifest.repeat_start || req.body.repeat_end !== manifest.repeat_end || req.body.transition_seconds !== manifest.transition_seconds ||
        Object.values(req.body.groups).filter((v) => v === 'keep').length !== 4) throw new Error(JSON.stringify(req));
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
  const expectedGroupAudio = api + '/music/audio/' + encodeURIComponent(report.project.result.variants[0]);
  report.result_audio = await wait('actual result audio decodes with extended duration and exact source', () => ev((query, duration, expected) => {
    const audio = document.querySelector(query).querySelector('audio[aria-label="Reproductor de comparación"]');
    return audio && audio.src === expected && audio.currentSrc === expected && audio.readyState >= 2 && !audio.error && Math.abs(audio.duration - duration) < 0.15 ?
      { src: audio.src, current_src: audio.currentSrc, expected_src: expected, duration: audio.duration, ready_state: audio.readyState } : false;
  }, panel, manifest.duration_seconds, expectedGroupAudio));
  await capture([1400, 900]);
  report.group_inspector = await executedInspector(report.project, 'groups');
  if (verifyFull) {
    await set('Qué hacer', 'full');
    await repeatWarning('full');
    if (fullSeed !== null) {
      if (!Number.isSafeInteger(fullSeed)) throw new Error('Invalid explicit UI seed');
      await click('REFERENCIA Y AVANZADOS');
      await set('Semilla del remix', fullSeed);
      report.full_seed_selection = await ev((query) => {
        const input = document.querySelector(query)?.querySelector('[aria-label="Semilla del remix"]');
        return { value: Number(input.value), visible: input.checkVisibility() };
      }, panel);
      if (!report.full_seed_selection.visible || report.full_seed_selection.value !== fullSeed) throw new Error('Seed was not explicitly selected through the real UI');
      report.source_analysis = await wait('actual source analysis reaches a terminal result after opening advanced controls', async () => {
        const request = report.analysis_status_requests?.at(-1);
        if (!request) return false;
        const result = await apiGet(request.path);
        return ['failed', 'succeeded'].includes(result.status) ? result : false;
      });
      checkpoint();
    }
    const previousFullIds = new Set((await apiGet('/music/jobs')).items.map((job) => job.job_id));
    if ((await apiGet('/music/jobs')).items.some((job) => ['queued', 'running'].includes(job.status))) throw new Error('Active jobs; do not launch full verification');
    await click('REMIX');
    report.full_project_request = await wait('actual full project HTTP sent with unchanged requested BPM and repeat interval', () => {
      const request = report.requests.find((r) => new URL(r.url).pathname === '/music/remix/project' && r.body.scope === 'full');
      if (!request) return false;
      for (const key of ['source_name','source_kind','bpm','duration_seconds','repeat_start','repeat_end','transition_seconds']) if (request.body[key] !== manifest[key]) throw new Error(`Unexpected full request ${key}`);
      if (fullSeed !== null && request.body.seed !== fullSeed) throw new Error('Full request seed differs from the visible explicit UI choice');
      return request.body;
    });
    report.full_job_id = await wait('actual full job ID appears', async () => (await apiGet('/music/jobs')).items.find((job) => !previousFullIds.has(job.job_id) && job.stage === manifest.source_name)?.job_id);
    checkpoint();
    report.full_project = await wait('actual SFT full batch2 job succeeds after one DSP per variant', async () => {
      const job = await apiGet('/audio/remix/ai/' + report.full_job_id);
      if (job.status === 'failed') { report.full_project = job; checkpoint(); throw new Error(JSON.stringify(job)); }
      return job.status === 'succeeded' ? job : false;
    });
    report.full_inspector = await executedInspector(report.full_project, 'full');
    report.full_result_audio = [];
    for (const [index, label] of ['VARIANTE A', 'VARIANTE B'].entries()) {
      const expectedFullAudio = api + '/music/audio/' + encodeURIComponent(report.full_project.result.variants[index]);
      await wait(`decode actual full ${label}`, () => ev((query, text) => {
        const button = [...document.querySelector(query).querySelectorAll('[data-audio-comparator] button')].find((node) => node.textContent.startsWith(text));
        if (!button) return false; button.click(); return true;
      }, panel, label));
      report.full_result_audio.push(await wait(`actual ${label} audio has final requested duration and exact variant source`, () => ev((query, duration, expected) => {
        const audio = document.querySelector(query)?.querySelector('audio[aria-label="Reproductor de comparación"]');
        return audio?.src === expected && audio.currentSrc === expected && audio.readyState >= 2 && !audio.error && Math.abs(audio.duration-duration) < .15 ?
          {src:audio.src,current_src:audio.currentSrc,expected_src:expected,duration:audio.duration,ready_state:audio.readyState} : false;
      }, panel, manifest.duration_seconds, expectedFullAudio)));
    }
    if (new Set(report.full_result_audio.map((audio) => audio.current_src)).size !== 2) throw new Error('Full A/B did not decode two distinct actual variants');
  }
  if (report.errors.length) throw new Error(report.errors.join(' | '));
  finish(0);
}).catch((error) => finish(1, error));
