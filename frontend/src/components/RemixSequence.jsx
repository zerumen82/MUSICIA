import React, { useEffect, useRef, useState } from 'react';
import { defaultSequenceSteps, sequenceCostText, sequenceEnabledCount, sequenceIntervalLabel, sequencePreviewStep, sequenceStepStatus } from '../remix_sequence';
import { patternCheckLabel, patternSummary } from '../remix_pattern';
import SequencePattern from './SequencePattern';

const field = 'px-2 py-1.5 bg-transparent border border-[var(--line)] outline-none focus:border-[var(--acc-line)] text-[12px] min-w-0';
const FOCUS_LABEL = { todo: 'Todo el tramo' };
const TEXT = {
  pattern: 'PATRÓN (OPCIONAL)', edit: 'EDITAR PATRÓN', active: 'PATRÓN ACTIVO',
  prepared: 'PATRÓN PREPARADO · PASO APAGADO', deactivate: 'DESACTIVAR PATRÓN',
  preparing: 'PREPARANDO VISTA…', noCaption: 'SIN TEXTO',
};
const groupLabel = (capabilities, focus) => capabilities?.groups?.find((item) => item.id === focus)?.label ?? focus;

/** Sections remain compact. One optional wide pattern editor opens on demand. */
export default function RemixSequence({ steps, onSteps, capabilities, preview, previewReady = false, previewPending = false, prepared, job, busy = false }) {
  const sequence = capabilities?.sequence ?? {};
  const focuses = Array.isArray(sequence.focuses) ? sequence.focuses : [];
  const maxSteps = Number(sequence.max_steps) || 0;
  const placeholder = capabilities?.scopes?.find((item) => item.id === 'sequence')?.placeholder ?? 'Qué debe sonar en cada paso.';
  const enabled = sequenceEnabledCount(steps);
  const [editingIndex, setEditingIndex] = useState(null);
  const patternEditor = useRef(null);
  const patternButtons = useRef(new Map());
  const editing = steps.find((step) => step.index === editingIndex) ?? null;
  const editingStatus = editing ? sequenceStepStatus(job, editing.index) : null;
  // El caption solo se enseña si la respuesta es la de las entradas actuales;
  // los tramos vienen del reparto, que no depende del texto.
  const actualPreview = previewReady ? preview : null;
  const update = (index, patch) => onSteps(steps.map((step) => (step.index === index ? { ...step, ...patch } : step)));
  useEffect(() => {
    if (editingIndex == null) return;
    patternEditor.current?.focus();
    patternEditor.current?.scrollIntoView({ block: 'nearest' });
  }, [editingIndex]);
  const closeEditor = () => {
    const button = patternButtons.current.get(editingIndex);
    setEditingIndex(null);
    button?.focus();
  };
  const add = () => {
    if (maxSteps && steps.length < maxSteps) onSteps([...steps, { ...defaultSequenceSteps(1)[0], index: steps.length }]);
  };
  const remove = () => {
    if (steps.length <= 1) return;
    if (editingIndex === steps.length - 1) setEditingIndex(null);
    onSteps(steps.slice(0, -1).map((step, index) => ({ ...step, index })));
  };

  return <div className="flex flex-col gap-3 min-w-0" data-remix-sequence>
    <div className="grid gap-2 grid-cols-[repeat(auto-fill,minmax(170px,1fr))]">
      {steps.map((step) => {
        const status = sequenceStepStatus(job, step.index);
        const previewStep = sequencePreviewStep(preview, step.index);
        const interval = sequenceIntervalLabel(previewStep?.start, previewStep?.end);
        const checkLabel = patternCheckLabel(status.check);
        return <div key={step.index} className="flex flex-col gap-2 border border-[var(--line)] rounded p-2 min-w-0" data-sequence-step={step.index}>
          <div className="flex items-center gap-2 flex-wrap">
            <button type="button" aria-pressed={step.enabled} aria-label={'Encender o apagar el paso ' + (step.index + 1)}
              disabled={busy} onClick={() => update(step.index, { enabled: !step.enabled })}
              className={'btn h-9 px-3 ' + (step.enabled ? 'btn-signal' : 'btn-ghost')} data-sequence-toggle={step.index}>{step.enabled ? 'ON' : 'OFF'}</button>
            <span className="label">PASO {step.index + 1}</span>
          </div>
          <span className="mono text-[10px] text-[var(--faint)]" data-sequence-interval={step.index}>{interval ?? (previewPending ? 'calculando tramo…' : 'tramo sin calcular')}</span>
          <select aria-label={'Foco del paso ' + (step.index + 1)} className="desk-select" value={step.focus} disabled={busy || focuses.length < 2}
            onChange={(event) => update(step.index, { focus: event.target.value })} data-sequence-focus={step.index}>
            {focuses.map((focus) => <option key={focus} value={focus}>{FOCUS_LABEL[focus] ?? focus}</option>)}
          </select>
          <textarea aria-label={'Texto del paso ' + (step.index + 1)} value={step.prompt} rows={3} disabled={busy} placeholder={placeholder}
            onChange={(event) => update(step.index, { prompt: event.target.value })} className={field + ' w-full resize-y'} data-sequence-prompt={step.index} />
          <button type="button" aria-expanded={editingIndex === step.index}
            aria-controls="sequence-pattern-editor" aria-label={'Editar patrón opcional del paso ' + (step.index + 1)}
            ref={(node) => { if (node) patternButtons.current.set(step.index, node); else patternButtons.current.delete(step.index); }}
            disabled={busy} onClick={() => editingIndex === step.index ? closeEditor() : setEditingIndex(step.index)}
            className="btn btn-ghost min-h-8 px-2 self-start" data-sequence-pattern-toggle={step.index}>
            {step.patternEnabled ? TEXT.edit : TEXT.pattern}
          </button>
          {step.patternEnabled && <>
            <span className="mono text-[10px] text-[var(--acc)]" data-sequence-pattern-active={step.index}>{step.enabled ? TEXT.active : TEXT.prepared} · {patternSummary(step.pattern)}</span>
            <button type="button" aria-label={'Desactivar patrón del paso ' + (step.index + 1)} disabled={busy}
              onClick={() => update(step.index, { patternEnabled: false })} className="btn btn-ghost min-h-8 px-2 self-start">{TEXT.deactivate}</button>
          </>}
          <span className="mono text-[10px]" data-sequence-status={step.index}>{status.text}</span>
          {status.warning && <p className="mono text-[10px] text-[var(--warn)]">{status.warning}</p>}
          {checkLabel && <p className="text-[11px]" data-pattern-check-summary={step.index}>{checkLabel}</p>}
        </div>;
      })}
    </div>
    {editing && <section id="sequence-pattern-editor" ref={patternEditor} tabIndex={-1}
      aria-label={'Editor de patrón del paso ' + (editing.index + 1)} className="flex flex-col gap-3 border border-[var(--line-strong)] rounded p-3 min-w-0"
      onKeyDown={(event) => { if (event.key === 'Escape') { event.preventDefault(); event.stopPropagation(); closeEditor(); } }} data-sequence-pattern-editor={editing.index}>
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <span className="label">PATRÓN OPCIONAL · PASO {editing.index + 1}</span>
        <button type="button" onClick={closeEditor} className="btn btn-ghost h-8 px-3" aria-label="Cerrar editor del patrón">CERRAR EDITOR</button>
      </div>
      <label className="flex items-center gap-2 text-[13px]">
        <input type="checkbox" aria-label={'Usar patrón en el paso ' + (editing.index + 1)} checked={Boolean(editing.patternEnabled)} disabled={busy}
          onChange={(event) => update(editing.index, { patternEnabled: event.target.checked })} />
        Usar patrón en este paso
      </label>
      <p className="text-[12px] text-[var(--muted)]">Desactivado no envía ninguna marca y conserva tu edición. Cerrar este editor no desactiva un patrón que hayas activado.</p>
      {!editing.enabled && <p className="text-[12px] text-[var(--muted)]">El paso está apagado: su patrón no se ejecutará.</p>}
      {editing.patternEnabled && <p className="text-[12px] text-[var(--muted)]">Un patrón vacío no añade instrucciones de batería.</p>}
      <SequencePattern key={editing.index} pattern={editing.pattern} capabilities={capabilities}
        disabled={busy || !editing.patternEnabled} onChange={(pattern) => update(editing.index, { pattern })}
        check={editingStatus?.check} checkLabel={patternCheckLabel(editingStatus?.check)} />
    </section>}
    <div className="flex items-center gap-3 flex-wrap">
      <button type="button" disabled={busy || !maxSteps || steps.length >= maxSteps} onClick={add} className="btn btn-ghost h-8 px-3">AÑADIR PASO</button>
      <button type="button" disabled={busy || steps.length <= 1} onClick={remove} className="btn btn-ghost h-8 px-3">QUITAR PASO</button>
      <span className="mono text-[10px] text-[var(--faint)]">{steps.length} de {maxSteps || '—'} pasos</span>
    </div>
    {focuses.length === 0 && <p className="text-[13px] text-[var(--muted)]">El servidor no declara los focos de la secuencia: no se puede montar la rejilla.</p>}
    {Array.isArray(sequence.focuses_pending) && sequence.focuses_pending.length > 0 && <p className="text-[13px] text-[var(--muted)]">El foco por pista ({sequence.focuses_pending.map((focus) => groupLabel(capabilities, focus)).join(', ')}) todavía no está implementado: ahora cada paso rehace el tramo entero.</p>}
    <p className="text-[13px] text-[var(--muted)]" data-sequence-cost>{sequenceCostText(enabled)}</p>
    <p className="text-[13px] text-[var(--muted)]">Un paso apagado conserva el material original de ese tramo. El orden lo pone la línea de tiempo, no el texto.</p>
    <details className="border border-[var(--line)] rounded p-2">
      <summary className="label cursor-pointer">TEXTO EFECTIVO DE CADA PASO</summary>
      <div className="flex flex-col gap-2 py-2">
        {steps.filter((step) => step.enabled).map((step) => {
          const status = prepared?.[step.index];
          const text = sequencePreviewStep(actualPreview, step.index)?.effective_prompt;
          return <div key={step.index} className="flex flex-col gap-1">
            <span className="label">PASO {step.index + 1}</span>
            <pre className="mono text-[10px] whitespace-pre-wrap break-words" data-sequence-effective={step.index}>{text == null ? TEXT.preparing : (text || TEXT.noCaption)}</pre>
            {status?.error && <p className="mono text-[10px] st-err">{status.error}</p>}
          </div>;
        })}
        {!steps.some((step) => step.enabled) && <p className="mono text-[10px] text-[var(--faint)]">Enciende un paso para ver el texto que se envía.</p>}
      </div>
    </details>
  </div>;
}
