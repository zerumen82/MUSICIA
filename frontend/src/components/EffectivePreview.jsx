import React, { useEffect, useState } from 'react';
import { PROMPT_PREVIEW_DEBOUNCE_MS } from '../api';

/** Consulta el mismo preparador que usa la ejecución; nunca inventa defaults. */
export default function EffectivePreview({ request, loadPreview, title = 'PARÁMETROS DEL MOTOR' }) {
  const [open, setOpen] = useState(false);
  const [answer, setAnswer] = useState(null);
  const encoded = JSON.stringify(request);
  useEffect(() => {
    if (!open) return undefined;
    let active = true;
    const timer = setTimeout(async () => {
      try {
        const result = await loadPreview(JSON.parse(encoded));
        if (active) setAnswer({ key: encoded, result });
      } catch (error) {
        if (active) setAnswer({ key: encoded, error: error.message });
      }
    }, PROMPT_PREVIEW_DEBOUNCE_MS);
    return () => { active = false; clearTimeout(timer); };
  }, [open, encoded, loadPreview]);
  const current = answer?.key === encoded ? answer : null;
  return <details onToggle={(event) => setOpen(event.currentTarget.open)} data-effective-preview>
    <summary className="label cursor-pointer">{title}</summary>
    {open && <div className="flex flex-col gap-2 py-2">
      {!current && <p role="status" className="mono text-[10px]">CONSULTANDO PARÁMETROS…</p>}
      {current?.error && <p role="alert" className="mono text-[11px] st-err">{current.error}</p>}
      {current?.result && <>
        <pre className="mono text-[10px] whitespace-pre-wrap break-words" data-engine-parameters>{JSON.stringify(current.result.effective_parameters, null, 2)}</pre>
        {current.result.operations && <details><summary className="label cursor-pointer">OPERACIONES DE AUDIO</summary><pre className="mono text-[10px] whitespace-pre-wrap break-words" data-audio-operations>{JSON.stringify(current.result.operations, null, 2)}</pre></details>}
        {current.result.provenance && <details><summary className="label cursor-pointer">PROCEDENCIA</summary><pre className="mono text-[10px] whitespace-pre-wrap break-words">{JSON.stringify(current.result.provenance, null, 2)}</pre></details>}
        {(current.result.warnings ?? []).map((warning, index) => <p key={index} className="mono text-[10px] text-[var(--warn)]">{typeof warning === 'string' ? warning : JSON.stringify(warning)}</p>)}
        {current.result.pending_material?.length > 0 && <p className="mono text-[10px] text-[var(--faint)]">Material derivado pendiente: {JSON.stringify(current.result.pending_material)}</p>}
      </>}
    </div>}
  </details>;
}
