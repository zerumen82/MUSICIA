import React from 'react';
import { defaultSequenceSteps, sequenceCostText, sequenceEnabledCount, sequenceIntervalLabel, sequencePreviewStep, sequenceStepStatus } from '../remix_sequence';

const field = 'px-2 py-1.5 bg-transparent border border-[var(--line)] outline-none focus:border-[var(--acc-line)] text-[12px] min-w-0';

/** Solo se ofrecen los focos que el backend ejecuta de verdad. */
const FOCUS_LABEL = { todo: 'Todo el tramo' };

/** El nombre legible de un foco pendiente: lo pone el catálogo de grupos. */
const groupLabel = (capabilities, focus) => {
  const group = (capabilities?.groups ?? []).find((item) => item.id === focus);
  return group?.label ?? focus;
};

/**
 * La rejilla de pasos de la secuencia (spec/02 [R20.A]).
 *
 * Una columna por paso: encendido, número, tramo que le toca (el servidor lo
 * reparte), foco, texto y estado real del trabajo. Un paso apagado conserva el
 * material original de ese tramo.
 */
export default function RemixSequence({ steps, onSteps, capabilities, preview, prepared, sent, job, busy = false }) {
  const sequence = capabilities?.sequence ?? {};
  const focuses = Array.isArray(sequence.focuses) ? sequence.focuses : [];
  const maxSteps = Number(sequence.max_steps) || 0;
  const placeholder = capabilities?.scopes?.find((item) => item.id === 'sequence')?.placeholder
    ?? 'Qué debe sonar en cada paso.';
  const enabled = sequenceEnabledCount(steps);

  const update = (index, patch) => onSteps(steps.map((step) => (step.index === index ? { ...step, ...patch } : step)));
  const add = () => {
    if (!maxSteps || steps.length >= maxSteps) return;
    onSteps([...steps, { ...defaultSequenceSteps(1)[0], index: steps.length }]);
  };
  const remove = () => {
    if (steps.length <= 1) return;
    onSteps(steps.slice(0, -1).map((step, position) => ({ ...step, index: position })));
  };

  return <div className="flex flex-col gap-3" data-remix-sequence>
    <div className="grid gap-2 grid-cols-[repeat(auto-fill,minmax(170px,1fr))]">
      {steps.map((step) => {
        const status = sequenceStepStatus(job, step.index);
        const previewStep = sequencePreviewStep(preview, step.index);
        const interval = sequenceIntervalLabel(previewStep?.start, previewStep?.end);
        return <div key={step.index} className="flex flex-col gap-2 border border-[var(--line)] rounded p-2 min-w-0" data-sequence-step={step.index}>
          <div className="flex items-center gap-2">
            <button type="button" aria-pressed={step.enabled} aria-label={`Encender o apagar el paso ${step.index + 1}`}
              disabled={busy} onClick={() => update(step.index, { enabled: !step.enabled })}
              className={`btn h-9 px-3 ${step.enabled ? 'btn-signal' : 'btn-ghost'}`} data-sequence-toggle={step.index}>
              {step.enabled ? 'ON' : 'OFF'}
            </button>
            <span className="label">PASO {step.index + 1}</span>
          </div>
          <span className="mono text-[10px] text-[var(--faint)]" data-sequence-interval={step.index}>{interval ?? 'tramo sin calcular'}</span>
          <select aria-label={`Foco del paso ${step.index + 1}`} className="desk-select" value={step.focus} disabled={busy || focuses.length < 2}
            onChange={(event) => update(step.index, { focus: event.target.value })} data-sequence-focus={step.index}>
            {focuses.map((focus) => <option key={focus} value={focus}>{FOCUS_LABEL[focus] ?? focus}</option>)}
          </select>
          <textarea aria-label={`Texto del paso ${step.index + 1}`} value={step.prompt} rows={3} disabled={busy} placeholder={placeholder}
            onChange={(event) => update(step.index, { prompt: event.target.value })} className={`${field} w-full resize-y`} data-sequence-prompt={step.index} />
          <span className="mono text-[10px]" data-sequence-status={step.index}>{status.text}</span>
          {status.warning && <p className="mono text-[10px] text-[var(--warn)]">{status.warning}</p>}
        </div>;
      })}
    </div>
    <div className="flex items-center gap-3 flex-wrap">
      <button type="button" disabled={busy || !maxSteps || steps.length >= maxSteps} onClick={add} className="btn btn-ghost h-8 px-3">AÑADIR PASO</button>
      <button type="button" disabled={busy || steps.length <= 1} onClick={remove} className="btn btn-ghost h-8 px-3">QUITAR PASO</button>
      <span className="mono text-[10px] text-[var(--faint)]">{steps.length} de {maxSteps || '—'} pasos</span>
    </div>
    {focuses.length === 0 && <p className="text-[13px] text-[var(--muted)]">El servidor no declara los focos de la secuencia: no se puede montar la rejilla.</p>}
    {Array.isArray(sequence.focuses_pending) && sequence.focuses_pending.length > 0 && (
      <p className="text-[13px] text-[var(--muted)]">El foco por pista ({sequence.focuses_pending.map((focus) => groupLabel(capabilities, focus)).join(', ')}) todavía no está implementado: ahora cada paso rehace el tramo entero.</p>)}
    <p className="text-[13px] text-[var(--muted)]" data-sequence-cost>{sequenceCostText(enabled)}</p>
    <p className="text-[13px] text-[var(--muted)]">Un paso apagado conserva el material original de ese tramo. El orden lo pone la línea de tiempo, no el texto.</p>
    {preview?.sequence && !preview.sequence.bar_aligned && (
      <p className="text-[13px] text-[var(--warn)]" data-sequence-tempo>No se midió un tempo fiable: los cortes de los pasos pueden no caer en el golpe.</p>)}
    <details className="border border-[var(--line)] rounded p-2">
      <summary className="label cursor-pointer">TEXTO EFECTIVO DE CADA PASO</summary>
      <div className="flex flex-col gap-2 py-2">
        {steps.filter((step) => step.enabled).map((step) => {
          const status = prepared?.[step.index];
          const text = sent?.[step.index];
          return <div key={step.index} className="flex flex-col gap-1">
            <span className="label">PASO {step.index + 1}</span>
            <pre className="mono text-[10px] whitespace-pre-wrap break-words" data-sequence-effective={step.index}>
              {text == null ? 'PREPARANDO…' : (text || 'SIN TEXTO')}
            </pre>
            {status?.error && <p className="mono text-[10px] st-err">{status.error}</p>}
          </div>;
        })}
        {!steps.some((step) => step.enabled) && <p className="mono text-[10px] text-[var(--faint)]">Enciende un paso para ver el texto que se envía.</p>}
      </div>
    </details>
  </div>;
}
