import React, { useEffect, useState } from 'react';
import RemixActions from './RemixActions';
import { api } from '../api';
import PromptTools from './PromptTools';
import EffectivePreview from './EffectivePreview';

/** Compatibilidad de apertura: todas las versiones trabajan sobre el original. */
export default function RemixIAPanel({ fileName, sourceKind = null, sourceDuration = null, onDone, createBacking = false, onLaunch, generating = false, jobNote = null }) {
  const [prompt, setPrompt] = useState('');
  const [name, setName] = useState('');
  const [error, setError] = useState(null);
  const [config, setConfig] = useState(null);
  const [bpm, setBpm] = useState('');
  const [duration, setDuration] = useState('');
  const [seed, setSeed] = useState('');
  const [key, setKey] = useState('');
  const [timeSignature, setTimeSignature] = useState('');
  useEffect(() => {
    if (!createBacking) return undefined;
    let active = true;
    api.musicConfig().then((data) => { if (active) setConfig(data); })
      .catch((err) => { if (active) setError(err.message); });
    return () => { active = false; };
  }, [createBacking]);
  const defaultDuration = config && sourceDuration > 0 ? Math.min(sourceDuration, config.max_duration_seconds) : config?.duration_seconds;
  const request = {
    prompt: prompt.trim(), instrumental: true, task_type: 'text2music',
    duration_seconds: duration === '' ? defaultDuration : Number(duration),
    bpm: bpm === '' ? null : Number(bpm), key_scale: key.trim() || null,
    time_signature: timeSignature || null, seed: seed === '' ? null : Number(seed),
    output_name: name.trim() || null,
  };
  const launch = async () => {
    setError(null);
    try {
      await api.generationPreview(request);
      await onLaunch(request);
    }
    catch (err) { setError(err.message); }
  };
  if (!createBacking) return <RemixActions fileName={fileName} sourceKind={sourceKind} onDone={onDone} />;
  return <div className="flex flex-col gap-3 border-t border-[var(--line)] pt-3">
    <span className="label">CREAR ACOMPAÑAMIENTO NUEVO</span>
    <p className="mono text-[10px] text-[var(--faint)]">Genera una pieza instrumental nueva. Duración inicial: {defaultDuration ?? '…'} s. Puedes combinarla con tu grabación en MEZCLA.</p>
    <textarea aria-label="Prompt del acompañamiento" disabled={generating} value={prompt} onChange={(event) => setPrompt(event.target.value)} rows={3} placeholder="Describe el acompañamiento que quieres crear" className="px-3 py-2 bg-transparent border border-[var(--line)] text-[13px]" />
    <PromptTools prompt={prompt} setPrompt={setPrompt} bpm={request.bpm} disabled={generating} />
    <div className="flex gap-3 flex-wrap">
      <label className="label">BPM <input aria-label="BPM del acompañamiento" type="number" min="1" value={bpm} disabled={generating} onChange={(event) => setBpm(event.target.value)} placeholder="Auto" className="w-24 px-2 py-1" /></label>
      <label className="label">DURACIÓN <input aria-label="Duración del acompañamiento" type="number" min="1" max={config?.max_duration_seconds} value={duration} disabled={generating} onChange={(event) => setDuration(event.target.value)} placeholder={String(defaultDuration ?? '')} className="w-24 px-2 py-1" /> s</label>
      <label className="label">SEMILLA <input aria-label="Semilla del acompañamiento" type="number" min="0" step="1" value={seed} disabled={generating} onChange={(event) => setSeed(event.target.value)} placeholder="Aleatoria" className="w-28 px-2 py-1" /></label>
    </div>
    <details><summary className="label cursor-pointer">TONO Y COMPÁS</summary><div className="flex gap-3 flex-wrap pt-2">
      <label className="label">TONO <input aria-label="Tono del acompañamiento" value={key} disabled={generating} onChange={(event) => setKey(event.target.value)} placeholder="Auto · C major / A minor" className="w-48 px-2 py-1" /></label>
      <label className="label">COMPÁS <select aria-label="Compás del acompañamiento" value={timeSignature} disabled={generating} onChange={(event) => setTimeSignature(event.target.value)} className="px-2 py-1"><option value="">Auto</option>{['4/4', '3/4', '6/8'].map((value) => <option key={value} value={value}>{value}</option>)}</select></label>
    </div></details>
    <input aria-label="Nombre del acompañamiento" value={name} disabled={generating} onChange={(event) => setName(event.target.value)} placeholder="Nombre opcional" className="px-3 py-2 bg-transparent border border-[var(--line)] text-[13px]" />
    <EffectivePreview request={request} loadPreview={api.generationPreview} title="ENVÍO EFECTIVO" />
    <button type="button" disabled={generating || !config || !prompt.trim()} onClick={() => void launch()} className="btn btn-signal h-10 px-4 self-start">{generating ? 'LANZANDO…' : 'CREAR ACOMPAÑAMIENTO'}</button>
    {jobNote && <p role="status" className="mono text-[10px] st-ok">{jobNote}</p>}
    {error && <p role="alert" className="mono text-[10px] st-err">{error}</p>}
  </div>;
}
