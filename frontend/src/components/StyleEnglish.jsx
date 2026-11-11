import React, { useEffect, useState } from 'react';
import { api, isTransportBlip, PROMPT_PREVIEW_DEBOUNCE_MS, TRANSPORT_ERROR_CLEAR_MS } from '../api';

/** Muestra el texto efectivo del servidor, sin reescribir los detalles editables. */
export default function StyleEnglish({ text, empty = '', request = null, why = '' }) {
  const trimmed = (text || '').trim();
  const encoded = request == null ? null : JSON.stringify(request);
  const key = encoded ?? trimmed;
  const [state, setState] = useState(null);
  useEffect(() => {
    if (!key) return undefined;
    let active = true;
    const timer = setTimeout(async () => {
      while (active) {
        try {
          const result = encoded == null
            ? await api.styleEnglish(trimmed)
            : await api.remixPreview(JSON.parse(encoded));
          const prompt = encoded == null ? result.prompt : result.effective_prompt;
          if (typeof prompt !== 'string') throw new Error('El servidor no devolvió el prompt efectivo.');
          if (active) setState({ key, prompt });
          return;
        } catch (error) {
          if (!active) return;
          if (!isTransportBlip(error.message)) { setState({ key, error: error.message }); return; }
          await new Promise((resolve) => setTimeout(resolve, TRANSPORT_ERROR_CLEAR_MS));
        }
      }
    }, PROMPT_PREVIEW_DEBOUNCE_MS);
    return () => { active = false; clearTimeout(timer); };
  }, [key, encoded, trimmed]);
  if (!key) {
    return empty
      ? <p className="text-[13px] text-[var(--text)]" data-track-phrase aria-label="Frase que se envía">{empty}</p>
      : null;
  }
  const current = state?.key === key ? state : null;
  const shown = !current ? 'Consultando el prompt efectivo…' : (current.error || current.prompt);
  if (encoded != null) return <div className="flex flex-col gap-2 border border-[var(--line)] rounded p-3 mb-2" role={current?.error ? 'alert' : 'status'}>
    <span className="label block text-[11px] uppercase tracking-wider">LEÍDO · Lo que recibirá el modelo</span>
    <pre className="mono text-[10px] whitespace-pre-wrap break-words p-2 bg-[var(--panel)] border border-[var(--line)] rounded" data-effective-prompt aria-label="Frase que se envía">{shown}</pre>
    {why && <p className="text-[11px] text-[var(--faint)] leading-snug">{why}</p>}
  </div>;
  return <p className="text-[13px] text-[var(--text)]" data-track-phrase data-effective-prompt aria-label="Frase que se envía" role={current?.error ? 'alert' : 'status'}>
    <span className="text-[var(--muted)]">Se envía: </span>{shown}
  </p>;
}
