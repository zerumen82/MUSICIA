import React from 'react';
import SequencePattern from './SequencePattern';

export default function RemixDrumPattern({
  groupPatternEditor, setGroupPatternEditor, groupPatternEnabled, setGroupPatternEnabled,
  groupPatterns, setGroupPatterns, capabilities, busy, patternSummary,
}) {
  return (
    <div className="flex flex-col gap-2 border border-[var(--line)] rounded p-2" data-group-pattern="drums">
      <button type="button" aria-expanded={groupPatternEditor === 'drums'}
        disabled={busy} onClick={() => setGroupPatternEditor(groupPatternEditor === 'drums' ? null : 'drums')}
        className={`btn btn-ghost min-h-8 px-2 self-start ${groupPatternEnabled.drums ? '!border-[var(--acc-line)] !text-[var(--acc)]' : ''}`} data-group-pattern-toggle="drums">
        {groupPatternEnabled.drums ? 'EDITAR PATRÓN' : 'PATRÓN DE BATERÍA (OCULTO)'}
      </button>
      {!groupPatternEnabled.drums && <span className="mono text-[10px] text-[var(--faint)]" data-group-pattern-hint="drums">Oculto y desactivado: no se envía nada hasta abrirlo, marcarlo y activarlo.</span>}
      {groupPatternEnabled.drums && <>
        <span className="mono text-[10px] text-[var(--acc)]" data-group-pattern-active="drums">PATRÓN ACTIVO · {patternSummary(groupPatterns.drums ?? {})}</span>
        <button type="button" disabled={busy} onClick={() => setGroupPatternEnabled('drums', false)}
          className="btn btn-ghost min-h-8 px-2 self-start" data-group-pattern-deactivate="drums">DESACTIVAR PATRÓN</button>
      </>}
      {groupPatternEditor === 'drums' && <section id="group-pattern-editor-drums" tabIndex={-1}
        className="flex flex-col gap-3 border border-[var(--line-strong)] rounded p-3 min-w-0" data-group-pattern-editor="drums">
        <label className="flex items-center gap-2 text-[13px]">
          <input type="checkbox" aria-label="Usar patrón en esta pista" checked={Boolean(groupPatternEnabled.drums)} disabled={busy}
            onChange={(event) => setGroupPatternEnabled('drums', event.target.checked)} />
          Usar patrón en esta pista
        </label>
        <SequencePattern key="drums" pattern={groupPatterns.drums ?? {}} capabilities={capabilities}
          disabled={busy || !groupPatternEnabled.drums}
          onChange={(pattern) => setGroupPatterns((current) => ({ ...current, drums: pattern }))} />
      </section>}
    </div>
  );
}
