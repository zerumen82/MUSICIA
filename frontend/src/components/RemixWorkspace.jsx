import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { AlertTriangle, Loader2, Sparkles } from 'lucide-react';
import { api, API_BASE_URL, JOB_POLL_INTERVAL_MS, JOB_POLL_MAX_MISSES } from '../api';
import RemixPanel from './RemixPanel';
import Waveform from './Waveform';
import PromptTools from './PromptTools';
import EffectivePreview from './EffectivePreview';
import AudioComparator from './AudioComparator';
import VoiceBackingPanel from './VoiceBackingPanel';

const field = 'px-2 py-1.5 bg-transparent border border-[var(--line)] outline-none focus:border-[var(--acc-line)] text-[12px] min-w-0';
const mediaUrl = (url, name) => url ? new URL(url, API_BASE_URL).href : api.audioUrl(name);

export default function RemixWorkspace({ fileName, onDone, initialAction = '', ficha = null, sourceKind = null }) {
  const [capabilities, setCapabilities] = useState(null);
  const [scope, setScope] = useState(initialAction === 'tramo' ? 'region' : 'full');
  const [prompt, setPrompt] = useState('');
  const [controls, setControls] = useState({});
  const [bpm, setBpm] = useState('');
  const [lyrics, setLyrics] = useState('');
  const [vocalMode, setVocalMode] = useState('source');
  const [outputName, setOutputName] = useState('');
  const [seed, setSeed] = useState('');
  const [region, setRegion] = useState({ start: 0, end: null });
  const [duration, setDuration] = useState(ficha?.duration_seconds ?? null);
  const [groups, setGroups] = useState([]);
  const [actions, setActions] = useState({});
  const [gains, setGains] = useState({});
  const [solo, setSolo] = useState(null);
  const [reference, setReference] = useState('');
  const [references, setReferences] = useState([]);
  const [advanced, setAdvanced] = useState(false);
  const [busy, setBusy] = useState(false);
  const [job, setJob] = useState(null);
  const [outputs, setOutputs] = useState([]);
  const [error, setError] = useState(null);
  const [notice, setNotice] = useState(null);
  const [analysis, setAnalysis] = useState(null);
  const [classification, setClassification] = useState('unknown');
  const [classificationOrigin, setClassificationOrigin] = useState('unknown');
  const [analysisStatus, setAnalysisStatus] = useState(null);
  const [analysisError, setAnalysisError] = useState(null);
  const currentJob = useRef(null);
  const alive = useRef(true);
  const classificationEdited = useRef(false);
  const workspace = useRef(null);
  const originalUrl = sourceKind === 'upload' ? api.uploadUrl(fileName) : api.audioUrl(fileName);

  useEffect(() => {
    alive.current = true;
    let active = true;
    api.remixCapabilities().then((data) => {
      if (active) { setCapabilities(data); setControls(data.defaults ?? {}); }
    }).catch((err) => { if (active) setError(err.message); });
    api.audioPeaks(fileName, undefined, sourceKind).then((data) => {
      if (active) setDuration(data.duration_seconds);
    }).catch((err) => { if (active) setNotice(`Duración no disponible: ${err.message}`); });
    return () => { active = false; alive.current = false; };
  }, [fileName, sourceKind]);

  useEffect(() => {
    if (!advanced) return undefined;
    let active = true;
    Promise.allSettled([api.library(), api.uploads()]).then((results) => {
      if (!active) return;
      setReferences(results.flatMap((result, index) => result.status === 'fulfilled'
        ? (result.value.items ?? []).map((item) => ({ id: `${index === 0 ? 'output' : 'upload'}:${item.name}`, name: item.name, kind: index === 0 ? 'output' : 'upload' })) : [])
        .filter((item) => !(item.name === fileName && item.kind === sourceKind)));
      const errors = results.filter((result) => result.status === 'rejected');
      if (errors.length) setNotice(`Referencias incompletas: ${errors.map((result) => result.reason.message).join(' · ')}`);
    });
    return () => { active = false; };
  }, [advanced, fileName, sourceKind]);

  useEffect(() => {
    let active = true;
    const detect = async () => {
      setAnalysisStatus('Analizando el audio original…');
      try {
        const started = await api.remixAnalyze({ source_name: fileName, source_kind: sourceKind });
        let misses = 0;
        while (active) {
          try {
            const result = await api.remixAnalyzeStatus(started.job_id);
            if (!active) return;
            misses = 0;
            setAnalysisStatus(result.phase ?? result.status);
            if (result.status === 'failed') { setAnalysisError(result.error ?? 'El análisis falló'); return; }
            if (result.status === 'succeeded') {
              setAnalysis(result.result);
              if (!classificationEdited.current) {
                const detected = result.result?.classification ?? 'unknown';
                setClassification(detected); setClassificationOrigin(detected === 'unknown' ? 'unknown' : 'analysis');
              }
              return;
            }
          } catch (err) { if (++misses >= JOB_POLL_MAX_MISSES) throw err; }
          await new Promise((resolve) => setTimeout(resolve, JOB_POLL_INTERVAL_MS));
        }
      } catch (err) { if (active) setAnalysisError(err.message); }
      finally { if (active) setAnalysisStatus(null); }
    };
    void detect();
    return () => { active = false; };
  }, [fileName, sourceKind]);

  const onRange = useCallback((selection) => setRegion({ start: selection.trim_start_s ?? 0, end: selection.trim_end_s }), []);
  const update = (name, value) => setControls((current) => ({ ...current, [name]: value }));
  const bounds = (name) => capabilities?.parameters?.[name];
  const range = (name, label) => {
    const limits = bounds(name);
    if (!limits || controls[name] == null) return null;
    return <label key={name} className="flex items-center gap-3 flex-wrap"><span className="label">{label}</span>
      <input aria-label={label} type="range" min={limits.min} max={limits.max} step={limits.step ?? 'any'} value={controls[name]} disabled={busy}
        onChange={(event) => update(name, Number(event.target.value))} className="flex-1 min-w-[100px]" />
      <span className="mono text-[11px]">{Number(controls[name]).toFixed(2)}</span></label>;
  };
  const poll = async (id, read) => {
    currentJob.current = id;
    let misses = 0;
    while (alive.current) {
      try {
        const incoming = await read(id);
        misses = 0;
        if (alive.current) setJob(incoming);
        if (incoming.status === 'succeeded') return incoming;
        if (incoming.status === 'failed' || incoming.status === 'cancelled') {
          const failure = new Error(incoming.error ?? 'La operación no se completó'); failure.finished = true; throw failure;
        }
      } catch (err) {
        if (err.finished || ++misses >= JOB_POLL_MAX_MISSES) throw err;
        if (alive.current) setNotice(`Sondeo interrumpido: ${err.message}. Reintentando…`);
      }
      await new Promise((resolve) => setTimeout(resolve, JOB_POLL_INTERVAL_MS));
    }
    return null;
  };
  const execute = async (operation) => {
    setBusy(true); setError(null); setNotice(null); setSolo(null); setJob(null);
    try { await operation(); }
    catch (err) { if (alive.current) setError(err.message); }
    finally { currentJob.current = null; if (alive.current) setBusy(false); }
  };
  const separate = () => execute(async () => {
    const started = await api.remixSeparate({ file_name: fileName, source_kind: sourceKind });
    const done = await poll(started.job_id, api.separateJob);
    if (!done || !alive.current) return;
    const actual = done.groups ?? done.result?.groups;
    if (!Array.isArray(actual) || !actual.length) throw new Error('La separación terminó sin grupos disponibles');
    setGroups(actual); setActions(Object.fromEntries(actual.map((group) => [group.id, 'keep'])));
    setNotice('Pistas separadas. Escucha cada grupo y elige su acción.');
  });
  const needsPrompt = scope !== 'groups' || Object.values(actions).includes('transform');
  const chosenReference = needsPrompt ? references.find((item) => item.id === reference) : null;
  const payload = {
    source_name: fileName, source_kind: sourceKind, source_classification: classification, classification_origin: classificationOrigin, prompt: needsPrompt ? prompt.trim() : '', scope,
    output_name: outputName.trim() || null,
    ...(seed !== '' && needsPrompt ? { seed: Number(seed) } : {}),
    ...(bpm !== '' && needsPrompt ? { bpm: Number(bpm) } : {}),
    ...(scope !== 'groups' && vocalMode === 'instrumental' ? { instrumental: true } : {}),
    ...(scope !== 'groups' && vocalMode === 'lyrics' ? { instrumental: false, lyrics: lyrics.trim() } : {}),
    ...(scope === 'region' ? { region_start: Number(region.start), region_end: Number(region.end ?? duration), repaint_mode: controls.repaint_mode, ...(controls.repaint_mode === 'balanced' ? { repaint_strength: controls.repaint_strength } : {}) }
      : needsPrompt ? { cover_strength: controls.cover_strength, cover_noise_strength: controls.cover_noise_strength } : {}),
    ...(scope === 'groups' ? { groups: actions, gains_db: Object.fromEntries(Object.entries(gains).filter(([id]) => actions[id] !== 'remove')) } : {}),
    ...(chosenReference ? { reference_name: chosenReference.name, reference_kind: chosenReference.kind } : {}),
  };
  const run = () => execute(async () => {
    if (needsPrompt && !prompt.trim()) throw new Error('Describe los cambios que quieres hacer');
    if (scope === 'groups' && !groups.length) throw new Error('Separa primero las pistas del original');
    if (scope === 'region' && !(Number(region.end ?? duration) > Number(region.start))) throw new Error('Selecciona un tramo con final posterior al inicio');
    if (needsPrompt && bpm !== '' && (!Number.isFinite(Number(bpm)) || Number(bpm) <= 0)) throw new Error('Escribe un BPM válido');
    if (needsPrompt && scope === 'groups' && Object.values(actions).includes('keep') && bpm !== '') throw new Error('Conservar grupos requiere mantener el tempo del original. Vacía el BPM o transforma esos grupos.');
    if (vocalMode === 'lyrics' && scope !== 'groups' && !lyrics.trim()) throw new Error('Escribe la letra nueva');
    await api.remixPreview(payload);
    const started = await api.remixProject(payload);
    const done = await poll(started.job_id, api.remixAiStatus);
    if (!done || !alive.current) return;
    const result = done.result ?? {};
    const variants = result.variants ?? [result.mix ?? result.base ?? done.output_name].filter(Boolean);
    if (!variants.length) throw new Error('El trabajo terminó sin archivos de audio disponibles');
    setOutputs(variants); setNotice('Remix guardado. Compara las variantes con el original.'); onDone?.(variants[0]);
  });
  const local = (operation) => execute(async () => {
    const result = await operation();
    if (alive.current) { setOutputs([result.file_name]); setNotice(`Guardado: ${result.file_name}`); onDone?.(result.file_name); }
  });
  const voiceBacking = (request) => execute(async () => {
    await api.remixAiPreview(request);
    const started = await api.remixAi(request);
    const done = await poll(started.job_id, api.remixAiStatus);
    if (!done || !alive.current) return;
    const variants = done.result?.variants ?? [done.result?.mix].filter(Boolean);
    if (!variants.length) throw new Error('La operación terminó sin variantes de voz y base disponibles');
    setOutputs(variants); setNotice('Voz original y base nueva guardadas. Escucha y compara las variantes.'); onDone?.(variants[0]);
  });
  const cancel = async () => {
    if (!currentJob.current) return;
    try { await api.cancelJob(currentJob.current); setNotice('Cancelación solicitada. Esperando confirmación.'); }
    catch (err) { setError(err.message); }
  };

  const comparisonTracks = useMemo(() => [{ id: 'original', label: 'ORIGINAL', url: originalUrl, duration },
    ...outputs.map((name, index) => ({ id: name, label: `VARIANTE ${String.fromCharCode(65 + index)} · ${name}`, url: api.audioUrl(name) }))], [originalUrl, duration, outputs]);

  return <div ref={workspace} className="flex flex-col gap-3" data-remix-project onPlayCapture={(event) => {
    workspace.current?.querySelectorAll('audio').forEach((player) => { if (player !== event.target) player.pause(); });
  }}>
    <div className="flex gap-2 items-center flex-wrap"><span className="label">REMIX · {fileName}</span>
      <span className="mono text-[10px] text-[var(--faint)]">ORIGINAL {duration == null ? '—' : `${Number(duration).toFixed(1)} s`}</span></div>
    <AudioComparator tracks={comparisonTracks} interval={scope === 'region' ? region : null} />
    <div className="flex items-center gap-3 flex-wrap">
      <span className="label">AUDIO DETECTADO</span>
      <select aria-label="Clasificación del audio original" value={classification} className={field} disabled={busy}
        onChange={(event) => { classificationEdited.current = true; setClassification(event.target.value); setClassificationOrigin('manual'); }}>
        {(analysis?.categories ?? capabilities?.source_classifications ?? capabilities?.source_categories ?? []).map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}
        {!(analysis?.categories ?? capabilities?.source_classifications ?? capabilities?.source_categories)?.length && <option value="unknown">Sin determinar</option>}
      </select>
      <span className="mono text-[10px] text-[var(--faint)]">{classificationOrigin === 'analysis' ? 'Detección del audio' : classificationOrigin === 'manual' ? 'Elección manual' : 'Sin determinar'}</span>
      {analysisStatus && <span role="status" className="mono text-[10px] text-[var(--faint)]">{analysisStatus}</span>}
      {analysisError && <span className="mono text-[10px] st-err">Detección no disponible: {analysisError}</span>}
    </div>
    {analysis?.description && <details><summary className="label cursor-pointer">EVIDENCIA DEL ANÁLISIS</summary>
      <p className="mono text-[10px] text-[var(--faint)] py-2">{analysis.description}</p></details>}
    <div className="flex gap-2 flex-wrap" role="group" aria-label="Ámbito del remix">
      {(capabilities?.scopes ?? []).map((item) => <button key={item.id} type="button" disabled={busy} aria-pressed={scope === item.id}
        onClick={() => { setScope(item.id); setSolo(null); }} className={`btn h-8 px-3 ${scope === item.id ? 'btn-signal' : 'btn-ghost'}`}>{item.label}</button>)}
      {!capabilities && !error && <span className="label animate-pulse">CARGANDO CAPACIDADES…</span>}
    </div>
    <textarea aria-label="Prompt del remix" value={prompt} disabled={busy || !needsPrompt} onChange={(event) => setPrompt(event.target.value)} rows={3}
      placeholder="Describe qué quieres cambiar y qué quieres conservar en este audio." className={`${field} resize-y w-full`} />
    {needsPrompt ? <PromptTools prompt={prompt} setPrompt={setPrompt} bpm={bpm === '' ? null : Number(bpm)} disabled={busy} />
      : <p className="mono text-[10px] text-[var(--faint)]">Conservar y quitar pistas no genera música. El prompt se utiliza al elegir transformar una pista.</p>}
    {scope === 'region' && <div className="flex flex-col gap-2"><Waveform key={`${sourceKind}:${fileName}`} fileName={fileName} sourceKind={sourceKind} onSelection={onRange} selection={region} disabled={busy} />
      <div className="flex gap-3 flex-wrap">
        <label className="label">DESDE <input aria-label="Inicio del tramo" type="number" min="0" step="any" disabled={busy} value={region.start} onChange={(event) => setRegion((current) => ({ ...current, start: event.target.value }))} className={`${field} w-24`} /> s</label>
        <label className="label">HASTA <input aria-label="Final del tramo" type="number" min="0" step="any" disabled={busy} value={region.end ?? duration ?? ''} onChange={(event) => setRegion((current) => ({ ...current, end: event.target.value }))} className={`${field} w-24`} /> s</label>
      </div></div>}
    {scope === 'groups' && <div className="flex flex-col gap-2">
      {!groups.length && <button type="button" disabled={busy || !capabilities} onClick={() => void separate()} className="btn btn-ghost h-9 px-3 self-start">SEPARAR PISTAS DEL ORIGINAL</button>}
      {groups.map((group) => <div key={group.id} className="flex items-center gap-3 flex-wrap border-b border-[var(--line)] py-2">
        <button type="button" aria-pressed={solo === group.id} onClick={() => setSolo((current) => current === group.id ? null : group.id)} className="btn btn-ghost h-7 px-2">{solo === group.id ? 'CERRAR SOLO' : 'SOLO'}</button>
        <span className="text-[12px] flex-1">{group.label}</span>
        <select aria-label={`Acción de ${group.label}`} disabled={busy} value={actions[group.id] ?? 'keep'} onChange={(event) => setActions((current) => ({ ...current, [group.id]: event.target.value }))} className={field}>
          {(capabilities?.actions ?? []).map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}
        </select>
        {solo === group.id && <audio controls autoPlay src={mediaUrl(group.url, group.file_name)} aria-label={`Escuchar ${group.label}`} className="player w-full" />}
      </div>)}
      <p className="mono text-[10px] text-[var(--faint)]">Grupos estimados. El acompañamiento restante puede reunir sintetizadores, guitarra, piano y efectos.</p>
    </div>}
    {scope !== 'region' && needsPrompt && range('cover_strength', 'FIDELIDAD AL ORIGINAL')}
    {needsPrompt && <label className="flex gap-3 items-center flex-wrap"><span className="label">BPM</span><input aria-label="BPM del remix" type="number" min={bounds('bpm')?.min} max={bounds('bpm')?.max} value={bpm} disabled={busy} placeholder="Mantener original" onChange={(event) => setBpm(event.target.value)} className={`${field} w-44`} /></label>}
    <button type="button" onClick={() => setAdvanced((current) => !current)} className="label text-left hover:text-[var(--acc)]" aria-expanded={advanced}>REFERENCIA Y AVANZADOS {advanced ? '−' : '+'}</button>
    {advanced && <div className="flex flex-col gap-3 border-l border-[var(--line)] pl-3">
      {scope !== 'region' && needsPrompt && range('cover_noise_strength', 'VARIACIÓN DEL AUDIO')}
      {scope === 'region' && <>
        <label className="label">TRANSICIÓN <select aria-label="Modo de edición regional" disabled={busy} className={field} value={controls.repaint_mode ?? ''} onChange={(event) => update('repaint_mode', event.target.value)}>
          {(capabilities?.repaint_modes ?? []).map((item) => <option key={item.id ?? item} value={item.id ?? item}>{item.label ?? item}</option>)}</select></label>
        {controls.repaint_mode === 'balanced' && range('repaint_strength', 'TRANSFORMACIÓN DEL TRAMO')}
        <p className="mono text-[10px] text-[var(--faint)]">El motor calcula la transición a partir del modo; la fuerza de transformación solo se aplica en el modo equilibrado.</p>
        {controls.repaint_mode === 'aggressive' && <p role="status" className="mono text-[10px] st-warn">El modo agresivo puede modificar audio fuera del tramo. Elige conservador o equilibrado para conservar su forma.</p>}
        {capabilities?.limitations?.repaint_normalization && <p className="mono text-[10px] text-[var(--faint)]">{capabilities.limitations.repaint_normalization}</p>}
      </>}
      {needsPrompt && <label className="label">REFERENCIA TÍMBRICA <select aria-label="Referencia tímbrica" value={reference} disabled={busy} onChange={(event) => setReference(event.target.value)} className={`${field} w-full mt-1`}>
        <option value="">Sin referencia adicional</option>{references.map((item) => <option key={item.id} value={item.id}>{item.kind === 'upload' ? 'SUBIDA' : 'BIBLIOTECA'} · {item.name}</option>)}</select></label>
      }
      {scope !== 'groups' && <>
        <label className="label">VOZ <select aria-label="Tratamiento de la voz" value={vocalMode} disabled={busy} onChange={(event) => setVocalMode(event.target.value)} className={field}>
          <option value="source">Según el original y el prompt</option><option value="instrumental">Instrumental solicitado</option><option value="lyrics">Cantar letra nueva</option></select></label>
        {vocalMode === 'lyrics' && <textarea aria-label="Letra nueva del remix" value={lyrics} disabled={busy} onChange={(event) => setLyrics(event.target.value)} placeholder="Letra nueva" rows={4} className={field} />}
        <p className="mono text-[10px] text-[var(--faint)]">Cover resintetiza la voz de forma aproximada. Para conservar la grabación vocal, elige conservar voz por pistas.</p>
      </>}
      {scope === 'groups' && groups.filter((group) => actions[group.id] !== 'remove').map((group) => <label key={group.id} className="label flex items-center gap-2">VOLUMEN {group.label}
        <input aria-label={`Volumen de ${group.label}`} type="number" min={bounds('gain_db')?.min} max={bounds('gain_db')?.max} step={bounds('gain_db')?.step ?? 'any'} value={gains[group.id] ?? 0} disabled={busy} onChange={(event) => setGains((current) => ({ ...current, [group.id]: Number(event.target.value) }))} className={`${field} w-24`} /> dB</label>)}
      <label className="label">NOMBRE <input aria-label="Nombre del remix" value={outputName} disabled={busy} onChange={(event) => setOutputName(event.target.value)} placeholder="Nombre de las variantes" className={`${field} w-full mt-1`} /></label>
      {needsPrompt && <label className="label">SEMILLA <input aria-label="Semilla del remix" type="number" min={bounds('seed')?.min} max={bounds('seed')?.max} step="1" value={seed} disabled={busy} onChange={(event) => setSeed(event.target.value)} placeholder="Aleatoria" className={`${field} w-44`} /></label>}
    </div>}
    <EffectivePreview request={payload} loadPreview={api.remixPreview} />
    <div className="flex gap-3 items-center flex-wrap"><button type="button" onClick={() => void run()} disabled={busy || !capabilities || (needsPrompt && !prompt.trim()) || (scope === 'groups' && !groups.length)} className="btn btn-signal h-10 px-5">
      {busy ? <Loader2 size={13} className="animate-spin" /> : <Sparkles size={13} />} {busy ? 'TRABAJANDO…' : 'REMIX'}</button>
      {busy && currentJob.current && <button type="button" onClick={() => void cancel()} className="btn btn-ghost h-8 px-3">CANCELAR</button>}</div>
    {busy && <div aria-live="polite" className="flex flex-col gap-2"><p className="mono text-[11px] text-[var(--acc)]">{job?.phase ?? 'Enviando operación…'}</p>
      {typeof (job?.progress_ratio ?? job?.engine_progress) === 'number' && <progress className="w-full" max="1" value={job.progress_ratio ?? job.engine_progress} />}
      {(job?.events ?? []).slice(-3).map((event, index) => <p key={`${event.t}-${index}`} className="mono text-[10px] text-[var(--faint)]">{event.text}</p>)}</div>}
    {(job?.effective_parameters || job?.result?.metadata || job?.variant_metadata) && <details><summary className="label cursor-pointer">PARÁMETROS Y SEMILLAS EJECUTADOS</summary>
      <pre className="mono text-[10px] whitespace-pre-wrap break-words py-2">{JSON.stringify({ effective_parameters: job.effective_parameters,
        variants: (job.result?.metadata ?? job.variant_metadata ?? []).map(({ file_name, seed, seed_origin }) => ({ file_name, seed, seed_origin })),
        provenance: job.provenance, classification: job.result?.source_classification, classification_origin: job.result?.classification_origin,
        source_analysis: job.result?.source_analysis ?? job.source_analysis }, null, 2)}</pre>
      {(job.warnings ?? []).map((warning, index) => <p key={index} className="mono text-[10px] st-warn">{typeof warning === 'string' ? warning : JSON.stringify(warning)}</p>)}
    </details>}
    {error && <p role="alert" className="mono text-[11px] st-err flex gap-2 items-center"><AlertTriangle size={13} />{error}</p>}
    {notice && <p role="status" className="mono text-[10px] text-[var(--muted)]">{notice}</p>}
    <VoiceBackingPanel fileName={fileName} sourceKind={sourceKind} duration={duration} capabilities={capabilities} busy={busy} onRun={voiceBacking} />
    <details className="border-t border-[var(--line)] pt-3"><summary className="label cursor-pointer">AJUSTES DE AUDIO · TEMPO, TONO, RECORTE Y LOOP</summary>
      <div className="flex gap-2 flex-wrap mt-3">
        <button type="button" disabled={busy} onClick={() => void local(() => api.setTempo({ file_name: fileName, source_kind: sourceKind, mode: 'half' }))} className="btn btn-ghost h-8 px-3">MEDIO TIEMPO</button>
        <button type="button" disabled={busy} onClick={() => void local(() => api.setTempo({ file_name: fileName, source_kind: sourceKind, mode: 'double' }))} className="btn btn-ghost h-8 px-3">DOBLE TIEMPO</button>
        <button type="button" disabled={busy || !bpm} onClick={() => void local(() => api.setTempo({ file_name: fileName, source_kind: sourceKind, mode: 'bpm', bpm: Number(bpm) }))} className="btn btn-ghost h-8 px-3">APLICAR BPM</button>
        <button type="button" disabled={busy} onClick={() => void local(() => api.makeLoop({ file_name: fileName, source_kind: sourceKind }))} className="btn btn-ghost h-8 px-3">EXPORTAR LOOP</button>
      </div><RemixPanel fileName={fileName} sourceKind={sourceKind} onRun={(params) => local(() => api.remix({ file_name: fileName, source_kind: sourceKind, ...params }))} />
    </details>
  </div>;
}

