import React, { useRef, useState } from 'react';
import { PATTERN_LABELS, emptyPattern, patternCellTarget, patternHits, patternSummary, togglePatternCell } from '../remix_pattern';

const TEXT = {
  title: 'PATRÓN DE BATERÍA', clear: 'VACIAR',
  missing: 'El servidor todavía no declara la resolución y los instrumentos del patrón.',
  rhythm: 'La intención se repite en cada compás. El modelo recibe instrucciones de texto y puede no respetar los golpes marcados.',
  conflict: 'Conserva tu texto de estilo y revisa que no pida un ritmo contrario al patrón.',
  measurement: 'Solo se mide el BOMBO. Caja, charles y platillo son intención declarada, no medida.',
  keyboard: 'Flechas para recorrer las celdas; Espacio o Intro para marcar un golpe.',
};
const cell = 'h-8 w-8 shrink-0 border border-[var(--line)] text-[10px] leading-none p-0 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-[var(--acc)]';
const cellOn = 'bg-[var(--acc-line)] text-black border-[var(--acc-line)]';

/** Wide optional editor. Its server-declared grid never invents a resolution. */
export default function SequencePattern({ pattern, onChange, capabilities, disabled = false, check = null, checkLabel = null }) {
  const declared = capabilities?.groups_pattern ?? capabilities?.sequence?.pattern ?? {};
  const canonical = Array.isArray(declared.instruments) ? declared.instruments : [];
  const legacy = (Array.isArray(declared.legacy_instruments) ? declared.legacy_instruments : [])
    .filter((instrument) => pattern?.[instrument]?.some(Boolean));
  const instruments = [...new Set([...canonical, ...legacy])];
  const steps = Number(declared.steps);
  const configured = instruments.length > 0 && Number.isInteger(steps) && steps > 0;
  const empty = emptyPattern(instruments, configured ? steps : 0);
  const rows = { ...pattern, ...Object.fromEntries(instruments.map((instrument) => [
    instrument, Array.isArray(pattern?.[instrument]) ? pattern[instrument] : empty[instrument],
  ])) };
  const [focused, setFocused] = useState({ row: 0, column: 0 });
  const buttons = useRef(new Map());
  const label = (instrument) => declared.labels?.[instrument] ?? PATTERN_LABELS[instrument] ?? instrument;
  const hits = patternHits(rows);
  const move = (event, row, column) => {
    const next = patternCellTarget(event.key, row, column, instruments.length, steps, event.ctrlKey || event.metaKey);
    if (!next || disabled) return;
    event.preventDefault();
    setFocused(next);
    buttons.current.get(instruments[next.row] + '-' + next.column)?.focus();
  };
  const activeRow = Math.min(focused.row, Math.max(0, instruments.length - 1));
  const activeColumn = Math.min(focused.column, configured ? steps - 1 : 0);
  const missingByBar = new Map();
  for (const event of check?.missed_events ?? []) {
    const current = missingByBar.get(event.bar) ?? [];
    current.push(event.step);
    missingByBar.set(event.bar, current);
  }

  return <div className="flex flex-col gap-3 min-w-0" data-sequence-pattern>
    <div className="flex items-center gap-2 flex-wrap">
      <span className="label">{TEXT.title}{configured ? ' · ' + steps + ' PASOS' : ''}</span>
      <span className="mono text-[10px] text-[var(--faint)]">{patternSummary(rows)}</span>
      <button type="button" className="btn btn-ghost h-8 px-3" disabled={disabled || !configured || !hits}
        onClick={() => onChange(emptyPattern(instruments, steps))} data-pattern-clear>{TEXT.clear}</button>
    </div>
    {!configured && <p role="status" className="text-[12px] text-[var(--muted)]">{TEXT.missing}</p>}
    {configured && <div className="max-w-full overflow-x-auto pb-2" role="group" aria-label="Instrumentos y golpes del patrón">
      <div className="flex gap-1 min-w-max mb-1" aria-hidden="true">
        <span className="w-20 shrink-0" />
        {Array.from({ length: steps }, (_, index) => <span key={index} className="w-8 text-center mono text-[10px] text-[var(--muted)]">{index + 1}</span>)}
      </div>
      <div className="flex flex-col gap-2 min-w-max">
        {instruments.map((instrument, rowIndex) => <div key={instrument} className="flex items-center gap-1" data-pattern-row={instrument}>
          <span className="mono text-[10px] text-[var(--faint)] w-20 shrink-0">{label(instrument)}</span>
          {Array.from({ length: steps }, (_, index) => {
            const on = Boolean(rows[instrument]?.[index]);
            return <button key={index} type="button" aria-pressed={on}
              aria-label={label(instrument) + ' en el paso ' + (index + 1)}
              ref={(node) => { const key = instrument + '-' + index; if (node) buttons.current.set(key, node); else buttons.current.delete(key); }}
              tabIndex={rowIndex === activeRow && index === activeColumn ? 0 : -1}
              onFocus={() => setFocused({ row: rowIndex, column: index })}
              onKeyDown={(event) => move(event, rowIndex, index)}
              className={cell + ' ' + (on ? cellOn : 'bg-transparent text-[var(--muted)]')}
              disabled={disabled}
              onClick={() => onChange(togglePatternCell(rows, instrument, index))}
              data-pattern-cell={instrument + '-' + (index + 1)}>{on ? '●' : '·'}</button>;
          })}
        </div>)}
      </div>
    </div>}
    <p className="text-[12px] text-[var(--muted)]">{TEXT.keyboard}</p>
    <p className="text-[12px] text-[var(--muted)]">{TEXT.rhythm} {TEXT.conflict}</p>
    <p className="text-[12px] text-[var(--muted)]">{TEXT.measurement}</p>
    {checkLabel && <p className="text-[12px]" data-pattern-check>{checkLabel}</p>}
    {check?.measured && check.measurement_stage === 'final_output' && <p className="mono text-[10px] text-[var(--muted)]">Medido sobre el audio final.</p>}
    {check?.measured && (check.extra_onsets_s ?? []).length > 0 && <p className="text-[12px] text-[var(--muted)]">Ataques detectados fuera de las marcas de bombo: {check.extra_onsets_s.length}.</p>}
    {missingByBar.size > 0 && <details>
      <summary className="label cursor-pointer">VER GOLPES DE BOMBO QUE FALTARON</summary>
      <ul className="max-h-48 overflow-y-auto py-2 text-[12px] text-[var(--muted)]">
        {[...missingByBar].map(([bar, missed]) => <li key={bar}>Compás {bar}: pasos {missed.join(', ')}.</li>)}
      </ul>
    </details>}
  </div>;
}
