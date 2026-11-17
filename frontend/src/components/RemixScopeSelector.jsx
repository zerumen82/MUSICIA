import React from 'react';
import { ACTIONS } from '../remix_sections';

export default function RemixScopeSelector({
  fileName, duration, action, setAction, setSolo, capabilities, busy, grooveBusy, error, scopeWhy,
}) {
  return (
    <>
      <div className="flex flex-col gap-2">
        <p className="text-[13px] text-[var(--muted)]">{fileName}{duration == null ? '' : ` · ${Number(duration).toFixed(1)} s`}</p>
        <label className="flex flex-col gap-1">
          <span className="text-[13px] text-[var(--text)]">Qué hacer</span>
          <select aria-label="Qué hacer" className="desk-select" disabled={busy || grooveBusy || !capabilities}
            value={action} onChange={(event) => { setAction(event.target.value); if (setSolo) setSolo(null); }}>
            {ACTIONS.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}
          </select>
        </label>
        {!capabilities && !error && <span className="text-[13px] text-[var(--muted)]">Cargando opciones…</span>}
      </div>
      {scopeWhy && <p className="text-[13px] leading-snug">{scopeWhy}</p>}
    </>
  );
}
