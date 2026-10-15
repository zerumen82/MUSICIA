import React, { useState } from 'react';
import { api } from '../api';
import { SECTIONS } from '../remix_sections';
import PromptTools from './PromptTools';
import EffectivePreview from './EffectivePreview';

const field = 'px-2 py-1.5 bg-transparent border border-[var(--line)] outline-none focus:border-[var(--acc-line)] text-[12px] min-w-0';
const SECONDS_PER_MINUTE = 60;

/** Restores the original vocal recording + a newly composed instrumental. */
export default function VoiceBackingPanel({ fileName, sourceKind, duration, capabilities, busy, onRun }) {
  const [prompt, setPrompt] = useState('');
  const [minutes, setMinutes] = useState('');
  const [bpm, setBpm] = useState('');
  const [seed, setSeed] = useState('');
  const [name, setName] = useState('');
  const request = {
    file_name: fileName, source_kind: sourceKind, mode: 'voz', prompt: prompt.trim(),
    output_name: name.trim() || null,
    ...(minutes !== '' ? { duration_seconds: Number(minutes) * SECONDS_PER_MINUTE } : {}),
    ...(bpm !== '' ? { bpm: Number(bpm) } : {}),
    ...(seed !== '' ? { seed: Number(seed) } : {}),
  };
  return <div className="flex flex-col gap-3" data-voice-backing>
      <textarea aria-label="Prompt de la base con voz original" rows={3} value={prompt} disabled={busy} onChange={(event) => setPrompt(event.target.value)} placeholder="Describe la nueva música para acompañar la voz original" className={field} />
      <PromptTools prompt={prompt} setPrompt={setPrompt} bpm={bpm === '' ? null : Number(bpm)} onBpm={(value) => setBpm(value == null || value === '' ? '' : String(value))} disabled={busy} />
      <div className="flex gap-3 flex-wrap">
        <label className="label">MINUTOS <input aria-label="Minutos de la base con voz original" type="number" step="any" min="0" disabled={busy} value={minutes} onChange={(event) => setMinutes(event.target.value)} placeholder={duration ? (duration / SECONDS_PER_MINUTE).toFixed(2) : 'Duración original'} className={`${field} w-36`} /></label>
        <label className="label">BPM <input aria-label="BPM de la base con voz original" type="number" min={capabilities?.parameters?.bpm?.min} max={capabilities?.parameters?.bpm?.max} value={bpm} disabled={busy} onChange={(event) => setBpm(event.target.value)} placeholder="Tempo original" className={`${field} w-36`} /></label>
        <label className="label">SEMILLA <input aria-label="Semilla de la base con voz original" type="number" min={capabilities?.parameters?.seed?.min} max={capabilities?.parameters?.seed?.max} step="1" value={seed} disabled={busy} onChange={(event) => setSeed(event.target.value)} placeholder="Aleatoria" className={`${field} w-36`} /></label>
      </div>
      <label className="label">NOMBRE <input aria-label="Nombre de la base con voz original" value={name} disabled={busy} onChange={(event) => setName(event.target.value)} placeholder="Nombre de las variantes" className={`${field} w-full mt-1`} /></label>
      <EffectivePreview request={request} loadPreview={api.remixAiPreview} why={SECTIONS.engine.why} />
      <button type="button" onClick={() => void onRun(request)} disabled={busy || !capabilities || !prompt.trim()} className="btn btn-signal h-10 px-4 self-start">CONSERVAR VOZ Y CREAR BASE</button>
  </div>;
}
