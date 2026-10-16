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
const report = { status: 'RUNNING', mode, id, steps: [], requests: [], responses: [], errors: [], artistic_quality: 'NOT CERTIFIED' };
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
  let diag = '';
  try {
    diag = JSON.stringify(await ev(() => ({ title: document.title, url: location.href,
      buttons: [...document.querySelectorAll('button,summary')].slice(0, 40).map((node) => node.innerText.replace(/\s+/g, ' ').trim()) })));
  } catch (error) { diag = error.message; }
  throw new Error(`Timeout: ${label} ${diag}`);
}
async function click(text, selector = 'document') {
  return wait(`click ${text}`, () => ev((label, query) => {
    const parent = query === 'document' ? document : document.querySelector(query);
    const el = [...(parent?.querySelectorAll('button,summary') || [])].find((b) => !b.matches(':disabled') && b.getClientRects().length && (b.textContent.trim() === label || [...b.querySelectorAll('span')].some((s) => s.textContent.trim() === label)));
    if (!el) return false;
    el.scrollIntoView({ block: 'center' }); el.click(); return true;
  }, text, selector));
}
async function set(selector, value) {
  await ev((query, next) => {
    const el = document.querySelector(query);
    if (!el) throw new Error(`Missing ${query}`);
    if (!el.getClientRects().length || el.matches(':disabled')) throw new Error(`Hidden or disabled control: ${query}`);
    if (el.tagName === 'SELECT' && ![...el.options].some((option) => option.value === next)) throw new Error(`Unavailable option ${next}: ${query}`);
    Object.getOwnPropertyDescriptor(Object.getPrototypeOf(el), 'value').set.call(el, next);
    el.dispatchEvent(new Event(el.tagName === 'SELECT' ? 'change' : 'input', { bubbles: true }));
  }, selector, value);
  await delay(100);
}
async function keyboard(selector, key) {
  if (!win.isVisible()) win.show();
  win.focus();
  win.webContents.focus();
  const focused = await ev((query) => {
    const el = document.querySelector(query);
    if (!el) return false;
    el.scrollIntoView({ block: 'center' });
    el.focus();
    return document.activeElement === el;
  }, selector);
  if (!focused) {
    const info = await ev((query) => {
      const nodes = [...document.querySelectorAll(query)];
      return {
        active: document.activeElement?.getAttribute?.('aria-label') || document.activeElement?.tagName,
        nodes: nodes.map((node) => ({ disabled: node.disabled, tab: node.tabIndex, type: node.type,
          rect: node.getBoundingClientRect().toJSON(), panel: node.closest('main > div')?.className,
          hiddenAncestor: node.closest('.hidden,[hidden]')?.className || node.closest('.hidden,[hidden]')?.getAttribute('hidden'),
          details: node.closest('details') ? node.closest('details').open : null })),
      };
    }, selector);
    throw new Error(`No se pudo enfocar ${selector} ${JSON.stringify(info)}`);
  }
  win.webContents.sendInputEvent({ type: 'keyDown', keyCode: key });
  win.webContents.sendInputEvent({ type: 'keyUp', keyCode: key });
  await delay(300);
}
async function capture(name) {
  win.show(); win.focus(); win.webContents.focus();
  await ev(() => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve))));
  await delay(100);
  const metrics = await ev(() => ({ captured_at: new Date().toISOString(), width: window.innerWidth, height: window.innerHeight,
    active_panel: document.querySelector('[data-active="true"]')?.getAttribute('data-panel'),
    panel_text: document.querySelector('[data-active="true"]')?.innerText,
    visible_text: [...document.querySelectorAll('[data-active="true"] button,[data-active="true"] p,[data-active="true"] summary')]
      .filter((node) => { const rect = node.getBoundingClientRect(); return rect.width && rect.height && rect.bottom > 0 && rect.top < window.innerHeight; })
      .map((node) => node.innerText.trim()),
    scrollWidth: document.documentElement.scrollWidth, overflow: document.documentElement.scrollWidth > window.innerWidth,
    overlaps: [...document.querySelectorAll('[data-active="true"] [data-remix-project] button,[data-active="true"] [data-remix-project] input:not([type="range"]),[data-active="true"] [data-remix-project] select')]
      .filter((e) => !e.closest('.sr-only') && e.offsetParent !== null).map((e) => ({ label: e.getAttribute('aria-label') || e.textContent.trim(), rect: e.getBoundingClientRect().toJSON() })) }));
  if (metrics.overflow) throw new Error(`Horizontal overflow ${name}: ${JSON.stringify(metrics)}`);
  report.steps.push({ label: `window ${name}`, metrics });
  fs.writeFileSync(path.join(dir, `${name}.png`), (await win.webContents.capturePage()).toPNG());
  fs.writeFileSync(path.join(dir, `${name}.json`), JSON.stringify(metrics, null, 2));
}
const seen = (selector) => `[data-active="true"] ${selector}`;
async function openSource(tab, name) {
  await click(tab);
  await wait(`visible ${tab}`, () => ev((label) => {
    const button = [...document.querySelectorAll('nav button')].find((node) => [...node.querySelectorAll('span')].some((span) => span.textContent.trim() === label));
    return button?.getAttribute('aria-pressed') === 'true';
  }, tab));
  const alreadyOpen = await ev((filename) => [...document.querySelectorAll('[data-active="true"] [data-remix-project]')]
    .some((workspace) => [...workspace.querySelectorAll('span')].some((node) => node.textContent === `REMIX · ${filename}`)), name);
  if (!alreadyOpen) {
    await wait(`locate exact ${tab} source ${name}`, () => ev((filename, library) => {
      const root = document.querySelector('[data-active="true"]');
      const stem = filename.replace(/\.mp3$/i, '');
      const title = [...root.querySelectorAll('span')].find((node) => node.textContent === filename || node.textContent === stem);
      const row = title?.closest('div.border-b');
      if (!row) return false;
      row.dataset.probeSource = filename;
      if (library) {
        const menu = [...row.querySelectorAll('button')].find((node) => node.textContent.trim() === 'ACCIONES');
        if (!menu) return false;
        menu.scrollIntoView({ block: 'center' }); menu.click();
      }
      return { name: filename, title: title.textContent };
    }, name, tab === 'BIBLIOTECA'));
    const rowSelector = seen(`[data-probe-source=${JSON.stringify(name)}]`);
    await click('REMIX', rowSelector);
  }
  await wait('exact source mounted with live capabilities', () => ev((filename) => {
    const workspace = [...document.querySelectorAll('[data-active="true"] [data-remix-project]')]
      .find((panel) => [...panel.querySelectorAll('span')].some((node) => node.textContent === `REMIX · ${filename}`));
    if (!workspace) return false;
    const heading = [...workspace.querySelectorAll('span')].find((node) => node.textContent === `REMIX · ${filename}`);
    return heading && workspace.querySelector('[aria-label="Qué hacer"]')?.options.length === 5 ? { name: filename, heading: heading.textContent } : false;
  }, name));
  const count = await ev(() => document.querySelectorAll('[data-active="true"] [data-remix-project]').length);
  if (count !== 1) throw new Error(`Expected one active remix workspace, found ${count}`);
}
async function actionChecks() {
  const expected = ['full', 'region', 'groups', 'voice', 'adjust'];
  const options = await ev(() => [...document.querySelector('[data-active="true"] [aria-label="Qué hacer"]').options].map((option) => option.value));
  if (JSON.stringify(options) !== JSON.stringify(expected)) throw new Error(`Unexpected remix actions: ${JSON.stringify(options)}`);
  for (const action of expected) {
    await set(seen('[aria-label="Qué hacer"]'), action);
    await wait(`single contextual form ${action}`, () => ev((chosen) => {
      const workspace = document.querySelector('[data-active="true"] [data-remix-project]');
      const shown = (query) => !!workspace.querySelector(query)?.getClientRects().length;
      const state = { prompt: shown('[aria-label="Prompt del remix"]'), region: shown('[aria-label="Inicio del tramo"]'),
        groups: [...workspace.querySelectorAll('button')].some((button) => button.getClientRects().length && button.textContent.trim() === 'SEPARAR PISTAS DEL ORIGINAL'),
        voice: shown('[data-voice-backing]'), adjust: shown('[aria-label="BPM del ajuste"]') };
      const expected = { prompt: ['full', 'region', 'groups'].includes(chosen), region: chosen === 'region', groups: chosen === 'groups', voice: chosen === 'voice', adjust: chosen === 'adjust' };
      return Object.keys(state).every((key) => state[key] === expected[key]) ? state : false;
    }, action));
  }
  await set(seen('[aria-label="Qué hacer"]'), 'full');
}
async function remixChecks(tab, filename, generate) {
  await openSource(tab, filename);
  await actionChecks();
  await wait('real capability controls loaded', () => ev(() => !!document.querySelector('[data-active="true"] [aria-label="FIDELIDAD AL ORIGINAL"]')));
  const literalPrompt = 'Jazz con contrabajo; batería suave al fondo, sin añadir instrumentos';
  await set(seen('[aria-label="Prompt del remix"]'), literalPrompt);
  await click('REFERENCIA Y AVANZADOS', seen('[data-remix-project]'));
  await set(seen('[aria-label="Clasificación del audio original"]'), 'electronic');
  await click('REFERENCIA Y AVANZADOS', seen('[data-remix-project]'));
  await click('PARÁMETROS DEL MOTOR', seen('[data-remix-project] > [data-effective-preview]'));
  report[`${tab}_preview`] = await wait('real server-computed preview preserves prompt and source', () => ev((prompt, filename) => {
    const pre = document.querySelector('[data-active="true"] [data-remix-project] > [data-effective-preview] [data-engine-parameters]');
    if (!pre) return false; const data = JSON.parse(pre.textContent);
    return data.prompt === prompt && data.model && data.src_audio_path?.replace(/\\/g, '/').endsWith(`/${filename}`) ? data : false;
  }, literalPrompt, filename));
  await set(seen('[aria-label="Qué hacer"]'), 'region');
  await set(seen('[aria-label="Inicio del tramo"]'), '6');
  await set(seen('[aria-label="Final del tramo"]'), '18');
  await wait('numeric interval and real waveform loaded', () => ev(() => !!document.querySelector('[data-active="true"] [data-remix-project] canvas') && Number(document.querySelector('[data-active="true"] [aria-label="Inicio del tramo"]')?.value) === 6 && Number(document.querySelector('[data-active="true"] [aria-label="Final del tramo"]')?.value) === 18));
  await keyboard(seen('[aria-label="Inicio del tramo"]'), 'Right');
  const next = await ev(() => Number(document.querySelector('[data-active="true"] [aria-label="Inicio del tramo"]').value));
  if (!(next > 6 && next < 18)) throw new Error(`Waveform keyboard did not update numeric field: ${next}`);
  await set(seen('[aria-label="Qué hacer"]'), 'full');
  await set(seen('[aria-label="Qué hacer"]'), 'region');
  await wait('remount preserves selected interval', () => ev((start) => Number(document.querySelector('[data-active="true"] [aria-label="Inicio del tramo"]').value) === start && Number(document.querySelector('[data-active="true"] [aria-label="Final del tramo"]').value) === 18, next));
  await wait('preview agrees with remounted region', () => ev((start) => {
    const pre = document.querySelector('[data-active="true"] [data-remix-project] > [data-effective-preview] [data-engine-parameters]');
    if (!pre) return false;
    const data = JSON.parse(pre.textContent);
    return data.repainting_start === start && data.repainting_end === 18 ? data : false;
  }, next));
  win.setContentSize(1400, 900); await capture(`${tab}-region-1400x900`);
  win.setContentSize(1080, 700); await capture(`${tab}-region-1080x700`);
  if (!generate) return;
  await set(seen('[aria-label="Qué hacer"]'), 'groups');
  await click('SEPARAR PISTAS DEL ORIGINAL', seen('[data-remix-project]'));
  await wait('four actual stems with one exclusive action each', () => ev(() => document.querySelectorAll('[data-active="true"] [data-remix-project] select[aria-label^="Acción de"]').length === 4));
  await ev(() => {
    const e = [...document.querySelectorAll('[data-active="true"] select[aria-label^="Acción de"]')].find((e) => /voz/i.test(e.getAttribute('aria-label')));
    Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'value').set.call(e, 'remove'); e.dispatchEvent(new Event('change', { bubbles: true }));
  });
  await click('SOLO', seen('[data-remix-project]'));
  await wait('solo actually playing a decoded stem', () => ev(() => {
    const a = document.querySelector('[data-active="true"] audio[aria-label^="Escuchar "]');
    return a && !a.paused && a.readyState >= 2 ? { src: a.src, time: a.currentTime, playing: [...document.querySelectorAll('audio')].filter((a) => !a.paused).length } : false;
  }));
  await click('CERRAR SOLO', seen('[data-remix-project]'));
  await click('REFERENCIA Y AVANZADOS', seen('[data-remix-project]'));
  await set(seen('[aria-label="Nombre del remix"]'), `prueba-plan-ui-dsp-${id}`);
  await click('REMIX', seen('[data-remix-project]'));
  await wait('deterministic DSP generates actual comparison variant', () => ev(() => [...document.querySelectorAll('[data-active="true"] [aria-label="Audio de la comparación"] button')].some((e) => e.textContent.startsWith('VARIANTE A'))));
  await click('SOLO', seen('[data-remix-project]'));
  await wait('solo playing before comparison switch', () => ev(() => {
    const a = document.querySelector('[data-active="true"] audio[aria-label^="Escuchar "]');
    return a && !a.paused && a.readyState >= 2;
  }));
  await keyboard(seen('[data-audio-comparator] button[aria-label="Reproducir comparación"]'), 'Return');
  await wait('comparison pauses solo and never overlaps', () => ev(() => {
    const a = document.querySelector('[data-active="true"] audio[aria-label="Reproductor de comparación"]');
    const playing = [...document.querySelectorAll('audio')].filter((player) => !player.paused);
    return a && !a.paused && playing.length === 1 ? { time: a.currentTime, playing: playing.length } : false;
  }));
  await click('CERRAR SOLO', seen('[data-remix-project]'));
  await click('PAUSAR', seen('[data-audio-comparator]'));
  await set(seen('[aria-label="Inicio de comparación"]'), '6');
  await set(seen('[aria-label="Final de comparación"]'), '18');
  await set(seen('[aria-label="Posición compartida A/B"]'), '10');
  await keyboard(seen('[data-audio-comparator] button[aria-label="Reproducir comparación"]'), 'Return');
  const before = await ev(() => document.querySelector('[data-active="true"] audio[aria-label="Reproductor de comparación"]').currentTime);
  await ev(() => { const b = [...document.querySelectorAll('[data-active="true"] [aria-label="Audio de la comparación"] button')].find((b) => b.textContent.startsWith('VARIANTE A')); b.focus(); });
  win.webContents.sendInputEvent({ type: 'keyDown', keyCode: 'Return' }); win.webContents.sendInputEvent({ type: 'keyUp', keyCode: 'Return' });
  report.ab_switch = await wait('keyboard A/B keeps actual time and active playback', () => ev((t) => {
    const a = document.querySelector('[data-active="true"] audio[aria-label="Reproductor de comparación"]');
    return a.src.includes('prueba-plan-ui-dsp') && !a.paused && a.currentTime >= t - 0.15 && a.currentTime < t + 2 && [...document.querySelectorAll('audio')].filter((a) => !a.paused).length === 1 ? { before: t, after: a.currentTime, src: a.src } : false;
  }, before));
  await keyboard(seen('[aria-label="Posición compartida A/B"]'), 'Right');
  await click('PAUSAR', seen('[data-audio-comparator]'));
  win.setContentSize(1400, 900); await capture('groups-1400x900');
  win.setContentSize(1080, 700); await capture('groups-1080x700');
  await set(seen('[aria-label="Qué hacer"]'), 'voice');
  await set(seen('[aria-label="Prompt de la base con voz original"]'), 'Jazz con contrabajo y batería suave');
  await set(seen('[aria-label="Minutos de la base con voz original"]'), '0.5');
  await set(seen('[aria-label="Semilla de la base con voz original"]'), '733217');
  await click('PARÁMETROS DEL MOTOR', seen('[data-voice-backing]'));
  report.voice_preview = await wait('voice route minutes and seed are effective', () => ev(() => {
    const pre = document.querySelector('[data-active="true"] [data-voice-backing] [data-engine-parameters]'); if (!pre) return false;
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
  const jobId = await wait('creation submitted job ID', async () => {
    const jobs = await ev(async (base) => (await (await fetch(base + '/music/jobs')).json()).items, api);
    return jobs.find((job) => job.prompt === report.create_wire.body.prompt && job.output_name?.startsWith(`prueba-plan-create-${id}`))?.job_id;
  });
  report.create_job_id = jobId;
  fs.writeFileSync(path.join(dir, 'submitted.json'), JSON.stringify({ job_id: jobId, request: report.create_wire.body }, null, 2));
  console.log(`CREATE_JOB ${jobId}`);
  let conversion = false;
  const job = await wait('Real generation returns decodable served audio', async () => {
    const state = await ev(async (base, id) => (await (await fetch(base + '/music/status/' + id)).json()), api, jobId);
    if (state.status === 'failed') throw new Error(JSON.stringify(state));
    if (!conversion && state.phase === 'Convirtiendo a audio final' && state.progress_ratio === null && state.engine_progress === 0.8) {
      const ui = await ev(() => {
        const composer = document.querySelector('[data-panel="composer"][data-active="true"]');
        const progress = composer.querySelector('progress');
        return { text: composer.innerText, indeterminate: !!progress && !progress.hasAttribute('value'), header: document.querySelector('header')?.innerText };
      });
      if (ui.text.includes('Convirtiendo a audio final') && ui.indeterminate && !/80\s*%/.test(ui.text + ui.header)) {
        conversion = true; report.create_conversion = { state, ui };
        await capture('create-final-decode-indeterminate');
      }
    }
    if (state.status === 'succeeded' && !conversion) throw new Error('Final decode 0.8/null UI was not observed');
    return state.status === 'succeeded' ? state : false;
  });
  report.create_job = job;
  if (JSON.stringify(job.effective_parameters) !== JSON.stringify(report.create_preview)) throw new Error('Creation preview differs from executed job');
  report.create_terminal_ui = await wait('visible creation ready state with the track in the library', () => ev(async (output, base) => {
    const composer = document.querySelector('[data-panel="composer"][data-active="true"]');
    const generate = [...composer.querySelectorAll('button')].find((button) => button.textContent.trim() === 'GENERAR');
    const ready = generate && !generate.disabled && !composer.innerText.includes('CREANDO…') && composer.innerText.includes('Está en BIBLIOTECA');
    const library = await (await fetch(base + '/music/library')).json();
    const listed = (library.items ?? []).some((item) => item.name === output);
    return ready && listed ? { output, busy: false, library: true } : false;
  }, job.output_name, api));
  await capture('create-completed');
}
async function adjustmentBusy() {
  await set(seen('[aria-label="Qué hacer"]'), 'adjust');
  await wait('adjustment waveform loaded', () => ev(() => !!document.querySelector('[data-active="true"] fieldset[aria-label="Ajustes del audio"] canvas')));
  await set(seen('[aria-label="Velocidad del ajuste"]'), '1.05');
  await set(seen('fieldset[aria-label="Ajustes del audio"] input[type="text"]'), `prueba-ui-ajuste-${id}`);
  await click('APLICAR REMIX', seen('[data-remix-project]'));
  report.adjustment_wire = await wait('one real DSP HTTP submission', () => report.requests.find((request) => new URL(request.url).pathname === '/audio/remix'));
  report.adjustment_busy = await wait('all adjustment controls disabled while real HTTP is pending', async () => {
    if (report.responses.some((response) => response.request_id === report.adjustment_wire.request_id)) throw new Error('DSP completed before busy state was observed');
    return ev(() => {
      const fieldset = document.querySelector('[data-active="true"] fieldset[aria-label="Ajustes del audio"]');
      const inputs = [...fieldset.querySelectorAll('input,button')];
      return fieldset.disabled && inputs.every((input) => input.matches(':disabled')) ? {
        fieldset_disabled: true, controls_disabled: inputs.length,
        selection: [...fieldset.querySelectorAll('input[type="range"][aria-label*="onda"]')].map((input) => input.value),
      } : false;
    });
  });
  await capture('adjustment-busy');
  const rect = await ev(() => {
    const canvas = document.querySelector('[data-active="true"] fieldset[aria-label="Ajustes del audio"] canvas');
    canvas.scrollIntoView({ block: 'center' }); return canvas.getBoundingClientRect().toJSON();
  });
  const pointer = { x: Math.round(rect.x + rect.width / 2), y: Math.round(rect.y + rect.height / 2), button: 'left', clickCount: 1 };
  win.webContents.sendInputEvent({ type: 'mouseDown', ...pointer });
  win.webContents.sendInputEvent({ type: 'mouseUp', ...pointer });
  await delay(100);
  const afterPointer = await ev(() => [...document.querySelectorAll('[data-active="true"] fieldset[aria-label="Ajustes del audio"] input[type="range"][aria-label*="onda"]')].map((input) => input.value));
  if (JSON.stringify(afterPointer) !== JSON.stringify(report.adjustment_busy.selection)) throw new Error('Busy waveform changed its interval');
  report.steps.push({ label: 'busy waveform ignores native pointer input', value: afterPointer });
  const response = await wait('real DSP response completed successfully', () => report.responses.find((entry) => entry.request_id === report.adjustment_wire.request_id));
  if (response.status_code !== 200) throw new Error(`DSP returned HTTP ${response.status_code}`);
  await wait('adjustment controls recover and actual variant appears', () => ev(() => {
    const fieldset = document.querySelector('[data-active="true"] fieldset[aria-label="Ajustes del audio"]');
    const apply = [...fieldset.querySelectorAll('button')].find((button) => button.textContent.trim() === 'APLICAR REMIX');
    const variant = [...document.querySelectorAll('[data-active="true"] [aria-label="Audio de la comparación"] button')].find((button) => button.textContent.startsWith('VARIANTE A'));
    return !fieldset.disabled && apply && !apply.matches(':disabled') && variant ? { recovered: true, variant: variant.textContent } : false;
  }));
  await ev(() => [...document.querySelectorAll('[data-active="true"] [aria-label="Audio de la comparación"] button')].find((button) => button.textContent.startsWith('VARIANTE A')).click());
  report.adjustment_audio = await wait('actual served DSP variant has positive decoded duration', () => ev(() => {
    const player = document.querySelector('[data-active="true"] audio[aria-label="Reproductor de comparación"]');
    return player?.src.includes('prueba-ui-ajuste') && player.readyState >= 1 && player.duration > 0 && !player.error ? { src: player.src, duration: player.duration } : false;
  }));
  if (report.requests.filter((request) => new URL(request.url).pathname === '/audio/remix').length !== 1) throw new Error('More than one DSP request was submitted');
  await capture('adjustment-recovered');
}
async function decode() {
  await openSource('SUBIR', source);
  await set(seen('[aria-label="Prompt del remix"]'), 'gabber hardcore');
  await wait('original analysis finished before generation', () => ev(() => [...document.querySelectorAll('[data-active="true"] [data-remix-project] button')]
    .some((button) => button.textContent.trim() === 'REMIX' && !button.disabled)));
  await set(seen('[aria-label="Qué hacer"]'), 'groups');
  await click('SEPARAR PISTAS DEL ORIGINAL', seen('[data-remix-project]'));
  await wait('four real separated source groups', () => ev(() => document.querySelectorAll('[data-active="true"] select[aria-label^="Acción de"]').length === 4));
  await ev(() => {
    const controls = [...document.querySelectorAll('[data-active="true"] select[aria-label^="Acción de"]')];
    for (const control of controls) {
      const label = control.getAttribute('aria-label');
      const action = /batería|acompañamiento/i.test(label) ? 'transform' : 'keep';
      Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'value').set.call(control, action);
      control.dispatchEvent(new Event('change', { bubbles: true }));
    }
  });
  await click('REFERENCIA Y AVANZADOS', seen('[data-remix-project]'));
  await set(seen('[aria-label="Nombre del remix"]'), `prueba-decode-ui-${id}`);
  await click('REMIX', seen('[data-remix-project]'));
  report.decode_wire = await wait('real HTTP remix submission from visible UI', () => report.requests.find((request) => new URL(request.url).pathname === '/music/remix/project'));
  const actions = report.decode_wire.body.groups;
  if (actions?.vocals !== 'keep' || actions?.bass !== 'keep' || actions?.drums !== 'transform' || actions?.other !== 'transform') throw new Error(`Wrong historical groups: ${JSON.stringify(actions)}`);
  const jobId = await wait('submitted remix job ID', async () => {
    const response = await ev(async (base) => (await (await fetch(base + '/music/jobs')).json()), api);
    return response.items.find((job) => job.prompt === 'gabber hardcore' && job.stage === source && ['queued', 'running'].includes(job.status))?.job_id;
  });
  report.decode_job_id = jobId;
  fs.writeFileSync(path.join(dir, 'submitted.json'), JSON.stringify({ job_id: jobId, source, request: report.decode_wire.body }, null, 2));
  console.log(`DECODE_JOB ${jobId}`);
  let conversion = false;
  report.decode_job = await wait('real remix completes after observed conversion', async () => {
    const state = await ev(async (base, jobId) => (await (await fetch(base + '/audio/remix/ai/' + jobId)).json()), api, jobId);
    if (state.status === 'failed' || state.status === 'cancelled') throw new Error(JSON.stringify(state));
    if (!conversion && state.phase === 'Convirtiendo a audio' && state.progress_ratio === null && state.engine_progress === 0.8) {
      const ui = await ev(() => {
        const workspace = document.querySelector('[data-active="true"] [data-remix-project]');
        const progress = workspace.querySelector('progress');
        return { line: workspace.querySelector('[aria-live="polite"]')?.textContent, indeterminate: !!progress && !progress.hasAttribute('value'), header: document.querySelector('header')?.textContent };
      });
      if (ui.line?.includes('Convirtiendo el audio a archivo') && ui.indeterminate && !/80\s*%/.test(ui.line + ui.header)) {
        conversion = true; report.decode_conversion = { state, ui };
        await capture('decode-indeterminate');
      }
    }
    if (state.status !== 'succeeded') return false;
    if (!conversion) throw new Error('Conversion UI was not observed; no conversion PASS can be claimed');
    return state;
  });
  report.decode_terminal_ui = await wait('exact source idle with completed job variants visible', () => ev((filename, variants) => {
    const workspace = [...document.querySelectorAll('[data-active="true"] [data-remix-project]')]
      .find((panel) => [...panel.querySelectorAll('span')].some((node) => node.textContent === `REMIX · ${filename}`));
    if (!workspace) return false;
    const buttons = [...workspace.querySelectorAll('button')];
    const run = buttons.find((button) => button.textContent.trim() === 'REMIX');
    const actual = [...workspace.querySelectorAll('[aria-label="Audio de la comparación"] button')].map((button) => button.textContent);
    return run && !run.disabled && !buttons.some((button) => button.textContent.includes('TRABAJANDO')) && !workspace.querySelector('[aria-live="polite"]')
      && variants.every((name) => actual.some((label) => label.endsWith(name)))
      ? { source: filename, variants: actual, busy: false, text: workspace.innerText } : false;
  }, source, report.decode_job.result.variants));
  await capture('decode-completed');
}
app.whenReady().then(async () => {
  if (!['127.0.0.1', 'localhost'].includes(new URL(api).hostname)) throw new Error('Local API only');
  win = new BrowserWindow({ width: 1400, height: 900, show: true, webPreferences: { sandbox: true, contextIsolation: true, nodeIntegration: false } });
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
      report.requests.push({ time: Date.now(), request_id: details.id, url: details.url, method: details.method, body });
    }
    callback({ cancel: false });
  });
  win.webContents.session.webRequest.onCompleted({ urls: [api + '/*'] }, (details) => {
    report.responses.push({ request_id: details.id, url: details.url, status_code: details.statusCode });
  });
  checkpoint(`loadURL ${api}`);
  await win.loadURL(api);
  checkpoint('loadURL complete');
  await wait('app shell', () => ev(() => [...document.querySelectorAll('nav button span')].some((node) => node.textContent.trim() === 'BIBLIOTECA')));
  if (mode === 'create') await creation();
  else if (mode === 'decode') await decode();
  else {
    await remixChecks('BIBLIOTECA', source, mode === 'full');
    if (mode === 'layout') await adjustmentBusy();
    if (mode === 'full') {
      await click('SUBIR');
      const bytes = fs.readFileSync(path.join(root, 'backend', 'outputs', source));
      await ev((base64, name) => {
        const raw = Uint8Array.from(atob(base64), (c) => c.charCodeAt(0));
        const file = new File([raw], name, { type: 'audio/mpeg' }); const dt = new DataTransfer(); dt.items.add(file);
        const input = document.querySelector('input[type="file"]'); input.files = dt.files; input.dispatchEvent(new Event('change', { bubbles: true }));
      }, bytes.toString('base64'), `prueba-plan-upload-${id}.mp3`);
      await click('ACOMPAÑAMIENTO NUEVO', seen('[data-new-backing]'));
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
