import React from 'react';
import PromptGuide from './PromptGuide';
import PromptTools from './PromptTools';
import RemixDrumPattern from './RemixDrumPattern';

export default function RemixGroupRow({ group, ctx }) {
  const {
    actions, setActions, solo, setSolo, busy, mediaUrl, capabilities,
    groupPatternEditor, setGroupPatternEditor, groupPatternEnabled, setGroupPatternEnabled,
    groupPatterns, setGroupPatterns, patternSummary,
  } = ctx;

  return (
    <div key={group.id} className="stem-row border-b border-[var(--line)] py-2">
      <span className="text-[14px] text-[var(--text)]">{group.label}</span>
      <select aria-label={`Acción de ${group.label}`} disabled={busy} value={actions[group.id] ?? 'keep'}
        onChange={(event) => setActions((current) => ({ ...current, [group.id]: event.target.value }))} className="desk-select">
        {(capabilities?.actions ?? []).map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}
      </select>
      <button type="button" disabled={busy} aria-pressed={solo === group.id}
        onClick={() => setSolo((current) => current === group.id ? null : group.id)} className="btn btn-ghost h-8 px-2">
        {solo === group.id ? 'CERRAR SOLO' : 'SOLO'}
      </button>
      {actions[group.id] === 'transform' && <fieldset disabled={busy} className="flex flex-col gap-2 border-0 p-0 min-w-0" style={{ gridColumn: '1 / -1' }}>
        <div className="text-[12px] text-[var(--muted)] px-1">
          Esta pista hereda el prompt general (no hay prompt propio por pista).
        </div>
        {group.id === 'drums' && <RemixDrumPattern groupPatternEditor={groupPatternEditor} setGroupPatternEditor={setGroupPatternEditor}
          groupPatternEnabled={groupPatternEnabled} setGroupPatternEnabled={setGroupPatternEnabled}
          groupPatterns={groupPatterns} setGroupPatterns={setGroupPatterns} capabilities={capabilities} busy={busy} patternSummary={patternSummary} />}
      </fieldset>}
      {solo === group.id && <audio controls autoPlay src={mediaUrl(group.url, group.file_name)} aria-label={`Escuchar ${group.label}`} className="player w-full" style={{ gridColumn: '1 / -1' }} />}
    </div>
  );
}
