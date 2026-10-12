import React, { useState } from 'react';
import RemixActions from './RemixActions';

/** Compatibilidad de apertura: todas las versiones trabajan sobre el original. */
export default function RemixIAPanel({ fileName, sourceKind = null, onDone, createBacking = false, onLaunch, generating = false, jobNote = null }) {
  const [prompt, setPrompt] = useState('');
  const [name, setName] = useState('');
  const [error, setError] = useState(null);
  const launch = async () => {
    setError(null);
    try { await onLaunch({ prompt: prompt.trim(), name: name.trim() || null, source_kind: sourceKind }); }
    catch (err) { setError(err.message); }
  };
  if (!createBacking) return <RemixActions fileName={fileName} sourceKind={sourceKind} onDone={onDone} />;
  return <div className="flex flex-col gap-3 border-t border-[var(--line)] pt-3">
    <span className="label">CREAR ACOMPAÑAMIENTO NUEVO</span>
    <p className="mono text-[10px] text-[var(--faint)]">Genera una pieza instrumental nueva de la duración del audio. Puedes combinarla con tu grabación en MEZCLA.</p>
    <textarea aria-label="Prompt del acompañamiento" value={prompt} onChange={(event) => setPrompt(event.target.value)} rows={3} placeholder="Describe el acompañamiento que quieres crear" className="px-3 py-2 bg-transparent border border-[var(--line)] text-[13px]" />
    <input aria-label="Nombre del acompañamiento" value={name} onChange={(event) => setName(event.target.value)} placeholder="Nombre opcional" className="px-3 py-2 bg-transparent border border-[var(--line)] text-[13px]" />
    <details><summary className="label cursor-pointer">ENVÍO EFECTIVO</summary><p className="mono text-[10px] whitespace-pre-wrap">{prompt.trim()}</p></details>
    <button type="button" disabled={generating || !prompt.trim()} onClick={() => void launch()} className="btn btn-signal h-10 px-4 self-start">{generating ? 'LANZANDO…' : 'CREAR ACOMPAÑAMIENTO'}</button>
    {jobNote && <p role="status" className="mono text-[10px] st-ok">{jobNote}</p>}
    {error && <p role="alert" className="mono text-[10px] st-err">{error}</p>}
  </div>;
}
