import React from 'react';
import Waveform from './Waveform';
import { REPAINT, SECTIONS } from '../remix_sections';

const field = 'px-2 py-1.5 bg-transparent border border-[var(--line)] outline-none focus:border-[var(--acc-line)] text-[12px] min-w-0';

function Fold({ title, why, children, ...rest }) {
  return <details {...rest}>
    <summary className="cursor-pointer">
      <span className="label">{title}</span>
      {why && <span className="ml-3 text-[13px] leading-snug text-[var(--muted)]">{why}</span>}
    </summary>
    {children}
  </details>;
}

export default function RemixRegionEditor({
  fileName, sourceKind, region, setRegion, duration, nudgeStep, busy,
  capabilities, controls, update, range, nudgeRegion, originalUrl,
}) {
  const onRange = (selection) => setRegion({ start: selection.trim_start_s ?? 0, end: selection.trim_end_s });
  const nudgeStepValue = nudgeStep;
  return (
    <div className="flex flex-col gap-2">
      <Waveform key={`${sourceKind}:${fileName}`} fileName={fileName} sourceKind={sourceKind}
        onSelection={onRange} selection={region} disabled={busy} nudgeStep={nudgeStepValue} scales={false} />
      <div className="flex gap-3 flex-wrap">
        <label className="label">DESDE <input aria-label="Inicio del tramo" type="number" min="0"
          step={Number(nudgeStepValue) > 0 ? nudgeStepValue : undefined} disabled={busy}
          value={region.start} onKeyDown={nudgeRegion('start')} onChange={(event) => setRegion((current) => ({ ...current, start: event.target.value }))}
          className={`${field} w-24`} /> s</label>
        <label className="label">HASTA <input aria-label="Final del tramo" type="number" min="0"
          step={Number(nudgeStepValue) > 0 ? nudgeStepValue : undefined} disabled={busy}
          value={region.end ?? duration ?? ''} onKeyDown={nudgeRegion('end')} onChange={(event) => setRegion((current) => ({ ...current, end: event.target.value }))}
          className={`${field} w-24`} /> s</label>
      </div>
      <label className="flex flex-col gap-1 text-[13px] text-[var(--text)]">Transición <select aria-label="Modo de edición regional" disabled={busy}
        className="desk-select" value={controls.repaint_mode ?? ''} onChange={(event) => update('repaint_mode', event.target.value)}>
        {(capabilities?.repaint_modes ?? []).map((item) => {
          const id = item.id ?? item;
          return <option key={id} value={id}>{REPAINT[id]?.label || item.label || id}</option>;
        })}
      </select></label>
      {REPAINT[controls.repaint_mode]?.why && <p className="text-[13px] leading-snug">{REPAINT[controls.repaint_mode].why}</p>}
      {controls.repaint_mode === 'balanced' && range('repaint_strength', 'TRANSFORMACIÓN DEL TRAMO')}
      {Number(region.end ?? duration) > Number(region.start) && <div className="flex flex-col gap-1">
        <span className="label">ESCUCHAR TRAMO</span>
        <audio controls preload="none" src={`${originalUrl}#t=${Number(region.start) || 0},${Number(region.end ?? duration)}`} className="player w-full" />
      </div>}
      {capabilities?.limitations?.repaint_normalization && <Fold title={SECTIONS.limit.title} why={SECTIONS.limit.why}><p className="mono text-[10px] text-[var(--faint)] py-2">{capabilities.limitations.repaint_normalization}</p></Fold>}
    </div>
  );
}
