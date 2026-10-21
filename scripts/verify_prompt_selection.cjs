/** B9b: exercise the served React UI in installed Electron; observe real HTTP. */
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const http = require('node:http');
const { execFileSync } = require('node:child_process');
const { app, BrowserWindow } = require('electron');

const api = process.env.MUSICIA_API_URL || 'http://127.0.0.1:8000';
const option = (name) => { const index = process.argv.indexOf(name); return index >= 0 ? process.argv[index + 1] : undefined; };
const outputBase = option('--output') || process.env.MUSICIA_PROMPT_OUTPUT;
const output = process.argv.includes('--append') && outputBase ? path.join(outputBase, 'run-' + Date.now()) : outputBase;
const manifestPath = option('--manifest') || process.env.MUSICIA_PROMPT_MANIFEST;
if (!output || !manifestPath) throw new Error('MUSICIA_PROMPT_OUTPUT and MUSICIA_PROMPT_MANIFEST are required');
const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8').replace(/^\uFEFF/, ''));
const timeout = Number(process.env.MUSICIA_PROBE_TIMEOUT_MS || 120000);
const interactionTimeout = 20000;
const generate = process.env.MUSICIA_PROMPT_GENERATE === '1';
const report = { status: 'RUNNING', process_id: process.pid, started_at: new Date().toISOString(), manifest, generate, requests: [], steps: [], errors: [] };
if (!['127.0.0.1', 'localhost'].includes(new URL(api).hostname)) throw new Error('Local API required');
fs.mkdirSync(output, { recursive: true });
if (fs.existsSync(path.join(output, 'result.json'))) throw new Error('Use a fresh evidence directory');
app.setPath('userData', path.join(output, 'profile'));
let win;
let finished = false;
const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const ev = (fn, ...args) => win.webContents.executeJavaScript(`(${fn.toString()})(...${JSON.stringify(args)})`, true);
function checkpoint() { fs.writeFileSync(path.join(output, 'running.json'), JSON.stringify(report, null, 2)); }
function log(message) { fs.appendFileSync(path.join(output, 'probe.log'), String(message) + '\n'); }
function finish(code, error) {
  if (finished) return;
  finished = true;
  report.status = code ? 'FAIL' : 'PASS';
  report.completed_at = new Date().toISOString();
  if (error) report.error = error.stack || String(error);
  fs.writeFileSync(path.join(output, 'result.json'), JSON.stringify(report, null, 2));
  log(JSON.stringify({ status: report.status, evidence: output, error: report.error }));
  if (win && !win.isDestroyed()) win.destroy();
  app.exit(code);
}
process.on('uncaughtException', (error) => finish(1, error));
process.on('unhandledRejection', (error) => finish(1, error));
app.on('window-all-closed', () => {});
async function wait(label, callback, milliseconds = timeout) {
  const end = Date.now() + milliseconds;
  while (Date.now() < end) {
    const value = await callback();
    if (value) {
      report.steps.push({ label, value, at: new Date().toISOString() });
      checkpoint(); log(label); return value;
    }
    await delay(200);
  }
  try {
    report.timeout_dom = await ev(() => ({ text: document.body.innerText,
      selections: [...document.querySelectorAll('[data-style-selection]')].map((node) => node.textContent),
      inputs: [...document.querySelectorAll('input,textarea,select')].map((node) => ({ label: node.getAttribute('aria-label'), value: node.value })) }));
    fs.writeFileSync(path.join(output, 'timeout.png'), (await win.webContents.capturePage()).toPNG()); checkpoint();
  } catch (error) { report.timeout_capture_error = error.message; }
  throw new Error(`Timeout: ${label}`);
}
async function click(text, selector = '[data-active="true"]') {
  return wait(`click ${text}`, () => ev((label, query) => {
    const parent = query === 'document' ? document : document.querySelector(query);
    const node = [...(parent?.querySelectorAll('button,summary') || [])].find((el) =>
      !el.disabled && el.getClientRects().length && (el.textContent.trim() === label ||
        [...el.querySelectorAll('span')].some((span) => span.textContent.trim() === label)));
    if (!node) return false;
    node.scrollIntoView({ block: 'center' }); node.click(); return true;
  }, text, selector), interactionTimeout);
}
async function set(selector, value) {
  await wait(`set ${selector}`, () => ev((query, next) => {
    const input = document.querySelector(query);
    if (!input || input.disabled || !input.getClientRects().length) return false;
    input.scrollIntoView({ block: 'center' });
    Object.getOwnPropertyDescriptor(Object.getPrototypeOf(input), 'value').set.call(input, String(next));
    input.dispatchEvent(new Event(input.tagName === 'SELECT' ? 'change' : 'input', { bubbles: true }));
    return true;
  }, selector, value), interactionTimeout);
}
async function glossary(scope, style, role) {
  await click('GLOSARIO', scope);
  await set('select[aria-label="Rol del estilo"]', role);
  await set('input[aria-label="Buscar estilo"]', style);
  await wait(`select literal ${role} ${style}`, () => ev((term) => {
    const search = document.querySelector('input[aria-label="Buscar estilo"]');
    const menu = search?.parentElement;
    const button = [...(menu?.querySelectorAll('button') || [])].find((el) =>
      el.textContent.trim() === term && !el.disabled && el.getClientRects().length);
    if (!button) return false;
    button.click(); return true;
  }, style), interactionTimeout);
  const rendered = await ev((query) => [...document.querySelectorAll(query + ' [data-style-selection]')].map((node) => ({
    textContent: node.textContent, innerText: node.innerText })), scope);
  report.steps.push({ label: `selection rendered ${role} ${style}`, value: rendered }); checkpoint();
}
async function snapshot(label, selector) {
  await ev(() => document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true })));
  await win.webContents.capturePage(undefined, { stayHidden: true, stayAwake: true });
  await ev(() => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve))));
  await delay(150);
  const value = await ev((query) => {
    const parent = document.querySelector(query);
    if (!parent) throw new Error(`Missing ${query}`);
    return { text: parent.innerText, inputs: [...parent.querySelectorAll('input,textarea,select')].map((node) =>
      ({ label: node.getAttribute('aria-label'), value: node.value })),
    prepared: [...parent.querySelectorAll('[data-effective-prompt]')].map((node) => node.value ?? node.textContent) };
  }, selector);
  report.steps.push({ label, value }); checkpoint();
  fs.writeFileSync(path.join(output, `${label}.png`), (await win.webContents.capturePage(undefined, { stayHidden: true, stayAwake: true })).toPNG());
  return value;
}
async function apiGet(route) {
  return new Promise((resolve, reject) => {
    const req = http.get(api + route, { timeout }, (response) => {
      let body = '';
      response.setEncoding('utf8');
      response.on('data', (chunk) => { body += chunk; });
      response.on('end', () => {
        if (response.statusCode !== 200) { reject(new Error(`${route}: HTTP ${response.statusCode}`)); return; }
        try { resolve(JSON.parse(body)); } catch (error) { reject(error); }
      });
    });
    req.on('error', reject);
    req.on('timeout', () => req.destroy(new Error(`${route}: real HTTP timeout`)));
  });
}
function subset(actual, expected) {
  if (expected === null || typeof expected !== 'object') return Object.is(actual, expected);
  if (Array.isArray(expected)) return JSON.stringify(actual) === JSON.stringify(expected);
  return actual && Object.entries(expected).every(([key, value]) => subset(actual[key], value));
}

log('Probe imported: waiting for Electron ready'); checkpoint();
app.whenReady().then(async () => {
  log('Electron ready: reading real local health'); checkpoint();
  report.health = await apiGet('/health');
  log('API health read: checking real jobs'); checkpoint();
  report.initial_jobs = await apiGet('/music/jobs');
  log('API jobs read: creating sandbox BrowserWindow'); checkpoint();
  if (generate && report.initial_jobs.items.some((job) => ['running', 'queued'].includes(job.status))) throw new Error('Active job; no generation audit submitted');
  win = new BrowserWindow({ width: 1400, height: 1000, show: false,
    webPreferences: { sandbox: true, contextIsolation: true, nodeIntegration: false, backgroundThrottling: false } });
  log('BrowserWindow constructed: loading served UI'); checkpoint();
  win.webContents.on('console-message', (_event, level, message) => { if (level === 3) report.errors.push(message); });
  await win.loadURL(api);
  log('Served UI loaded: attaching CDP observation'); checkpoint();
  // Observation only: every request and response proceeds to the actual API.
  win.webContents.debugger.attach('1.3');
  await win.webContents.debugger.sendCommand('Network.enable');
  log('CDP network observation enabled'); checkpoint();
  const pending = new Map();
  win.webContents.debugger.on('message', (_event, method, params) => {
    if (method === 'Network.requestWillBeSent' && params.request.method === 'POST' && params.request.url.startsWith(api + '/')) {
      let body = params.request.postData;
      try { body = JSON.parse(body); } catch { /* Preserve non-JSON uploads literally. */ }
      const item = { url: params.request.url, body, at: new Date().toISOString() };
      report.requests.push(item); pending.set(params.requestId, item); checkpoint();
    }
    if (method === 'Network.responseReceived' && pending.has(params.requestId)) pending.get(params.requestId).status = params.response.status;
    if (method === 'Network.loadingFinished' && pending.has(params.requestId)) {
      const item = pending.get(params.requestId);
      win.webContents.debugger.sendCommand('Network.getResponseBody', { requestId: params.requestId }).then((result) => {
        try { item.response = JSON.parse(result.body); } catch { item.response = result.body; }
        checkpoint();
      }).catch((error) => { item.response_error = error.message; });
    }
  });
  await wait('served UI mounted', () => ev(() => Boolean(document.querySelector('[data-active="true"]'))));
  // Scenario selectors and optional operations are explicit audit input, not app internals.
  for (const operation of manifest.operations) {
    if (operation.kind === 'click') {
      if (operation.text === 'SEPARAR PISTAS DEL ORIGINAL') {
        if (!manifest.allow_separation) throw new Error('Real separation was not enabled in this audit manifest');
        report.waiting_for_jobs_before_separation = true; checkpoint(); log('Waiting for actual jobs to finish before real separation');
        await wait('real jobs idle before real separation', async () => !(await apiGet('/music/jobs')).items.some((job) => ['running', 'queued'].includes(job.status)),
          Number(process.env.MUSICIA_AUDIO_TIMEOUT_MS || 1900000));
        report.waiting_for_jobs_before_separation = false; checkpoint();
        if (manifest.separation_cpu_guard) {
          const free = Number(execFileSync('nvidia-smi', ['--query-gpu=memory.free', '--format=csv,noheader,nounits'], { encoding: 'utf8' }).trim());
          report.separation_gpu_free_mb = free; checkpoint();
          assert.equal(manifest.separation_cpu_guard.configured_device, 'auto');
          assert.ok(Number.isFinite(free) && free < manifest.separation_cpu_guard.auto_gpu_threshold_mb,
            'Separation would be eligible for CUDA; preserved user GPU priority');
        }
      }
      await click(operation.text, operation.scope);
    }
    else if (operation.kind === 'set') await set(operation.selector, operation.value);
    else if (operation.kind === 'glossary') await glossary(operation.scope, operation.style, operation.role);
    else if (operation.kind === 'snapshot') await snapshot(operation.label, operation.scope);
    else if (operation.kind === 'assert-value') await wait(operation.label, () => ev((query, expected) => document.querySelector(query)?.value === expected, operation.selector, operation.value));
    else if (operation.kind === 'assert-text') await wait(operation.label, () => ev((query, includes, excludes) => {
      const text = document.querySelector(query)?.textContent.replace(/\s+/g, ' ') ?? '';
      return includes.every((part) => text.includes(part)) && excludes.every((part) => !text.includes(part)) ? text : false;
    }, operation.scope, operation.includes || [], operation.excludes || []), interactionTimeout);
    else if (operation.kind === 'request') await wait(operation.label, () => report.requests.findLast((request) => new URL(request.url).pathname === operation.path && request.status === 200 && request.response));
    else if (operation.kind === 'assert-request') await wait(operation.label, () => report.requests.findLast((request) =>
      new URL(request.url).pathname === operation.path && request.status === 200 && subset(request.body, operation.expected)));
    else if (operation.kind === 'assert-preview') await wait(operation.label, async () => {
      await ev((query) => {
        const details = document.querySelector(query)?.querySelector('details[data-effective-preview]');
        if (details && !details.open) details.querySelector('summary')?.click();
      }, operation.scope);
      const preview = report.requests.findLast((request) => new URL(request.url).pathname === operation.path && request.status === 200 && request.response);
      if (!preview || !subset(preview.body, operation.expected || {})) return false;
      const shown = await ev((query) => {
        const node = document.querySelector(query)?.querySelector('[data-effective-prompt]');
        return node?.textContent.replace(/^Se envía:\s*/, '').trim();
      }, operation.scope);
      const prompt = preview.response.effective_parameters?.prompt;
      return prompt && shown === prompt ? { shown, request: preview.body, effective_parameters: preview.response.effective_parameters } : false;
    });
    else if (operation.kind === 'library-remix') {
      await click('BIBLIOTECA', 'document');
      const row = await wait('exact real library source', () => ev((filename) => {
        const parent = document.querySelector('[data-active="true"]');
        const stem = filename.replace(/\.mp3$/i, '');
        const title = [...(parent?.querySelectorAll('span') || [])].find((node) => node.textContent === filename || node.textContent === stem);
        const item = title?.closest('div.border-b');
        const action = [...(item?.querySelectorAll('button') || [])].find((node) => node.textContent.trim() === 'ACCIONES');
        if (!action) return false;
        item.dataset.promptAuditSource = 'selected'; action.scrollIntoView({ block: 'center' }); action.click(); return true;
      }, operation.source));
      assert.ok(row);
      await click('REMIX', '[data-prompt-audit-source="selected"]');
    }
    else if (operation.kind === 'generate') {
      if (!generate) throw new Error('Generation requires MUSICIA_PROMPT_GENERATE=1');
      await click(operation.text, operation.scope);
      const submitted = await wait('real generation admitted', () => report.requests.findLast((request) => new URL(request.url).pathname === operation.path && request.response?.job_id));
      const preview = report.requests.findLast((request) => new URL(request.url).pathname === operation.previewPath && request.status === 200);
      assert.ok(preview, 'Real preview request missing');
      assert.deepEqual(submitted.body, preview.body, 'Preview and generation request differ');
      report.completed_job = await wait('real audio job terminal', async () => {
        const job = await apiGet(operation.jobPath + submitted.response.job_id);
        if (job.status === 'failed') throw new Error(`Actual generation failed: ${JSON.stringify(job)}`);
        return job.status === 'succeeded' ? job : false;
      }, Number(process.env.MUSICIA_AUDIO_TIMEOUT_MS || 1900000));
    } else throw new Error(`Unknown audit operation ${operation.kind}`);
  }
  await delay(400);
  finish(0);
});
