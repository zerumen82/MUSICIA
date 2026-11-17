import React from 'react';

export default function RemixStemPicker({
  groupIds, groupLabel, stemFiles, setStemFiles, references, quantize, setQuantize, busy,
}) {
  return (
    <div className="flex flex-col gap-2 border border-[var(--line)] rounded p-2">
      {groupIds.map((gid) => (
        <label key={gid} className="flex items-center gap-2 text-[13px]">{groupLabel(gid)}
          <select className="desk-select" value={stemFiles[gid]?.id ?? ''} disabled={busy}
            onChange={(e) => { const item = references.find((r) => r.id === e.target.value); setStemFiles((prev) => ({ ...prev, [gid]: item ? { name: item.name, kind: item.kind, id: item.id } : null })); }}>
            <option value="">— sin stem —</option>
            {references.map((r) => <option key={r.id} value={r.id}>{r.name} ({r.kind})</option>)}
          </select>
        </label>
      ))}
      <label className="flex items-center gap-2 text-[13px]"><input type="checkbox" checked={quantize} onChange={(e) => setQuantize(e.target.checked)} disabled={busy} /> Cuantizar stems al BPM objetivo</label>
    </div>
  );
}
