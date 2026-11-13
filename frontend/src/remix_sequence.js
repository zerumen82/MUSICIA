/**
 * Secuencia de pasos del remix (spec/02 [R20.A]).
 *
 * Lógica pura, sin React: la rejilla de la mesa y las pruebas usan las mismas
 * reglas. El servidor reparte los pasos en el tiempo (el cliente no manda
 * intervalos) y valida lo mismo que se valida aquí, pero en español y antes
 * de enviar.
 */
import { patternPayload } from './remix_pattern.js';

/** Foco que rehace el tramo entero. Es el único que el motor ejecuta hoy. */
export const SEQUENCE_FOCUS_TODO = 'todo';

/** Pasos nuevos: apagados y sin texto (un paso apagado conserva el original). */
export function defaultSequenceSteps(count) {
  const total = Number(count);
  const steps = Number.isFinite(total) ? Math.max(0, Math.floor(total)) : 0;
  return Array.from({ length: steps }, (_, index) => ({
    index,
    enabled: false,
    focus: SEQUENCE_FOCUS_TODO,
    prompt: '',
    patternEnabled: false,
  }));
}

/** La lista que viaja al backend: solo lo que el contrato acepta. */
export function sequencePayloadSteps(steps) {
  return (steps ?? []).map((step, position) => {
    const pattern = step?.enabled && step?.patternEnabled === true ? patternPayload(step.pattern) : null;
    return {
      index: Number.isInteger(Number(step?.index)) ? Number(step.index) : position,
      enabled: Boolean(step?.enabled),
      focus: String(step?.focus || SEQUENCE_FOCUS_TODO),
      prompt: String(step?.prompt ?? ''),
      // Ocultar el editor no activa nada: solo viaja un patrón optado y con golpes.
      ...(pattern ? { pattern } : {}),
    };
  });
}

/** Cuántos pasos van a llamar al motor. */
export function sequenceEnabledCount(steps) {
  return sequencePayloadSteps(steps).filter((step) => step.enabled).length;
}

/** Las mismas reglas que el servidor, comprobadas antes de enviar. */
export function sequenceValidation(steps, options = {}) {
  const list = sequencePayloadSteps(steps);
  const maxSteps = Number(options.maxSteps);
  if (!list.length) return { error: 'La secuencia necesita al menos un paso.' };
  if (Number.isFinite(maxSteps) && maxSteps > 0 && list.length > maxSteps) {
    return { error: `La secuencia admite hasta ${maxSteps} pasos.` };
  }
  const active = list.filter((step) => step.enabled);
  if (!active.length) return { error: 'Enciende al menos un paso de la secuencia.' };
  const withoutText = active.find((step) => !step.prompt.trim());
  if (withoutText) {
    return { error: `El paso ${withoutText.index + 1} necesita su texto: sin él no hay nada que rehacer.` };
  }
  return { error: null };
}

/** El coste real y declarado: un paso encendido es una llamada al motor. */
export function sequenceCostText(count) {
  const steps = Math.max(0, Math.floor(Number(count) || 0));
  if (!steps) return 'Ningún paso encendido: no se llama al motor.';
  const calls = steps === 1 ? '1 paso es 1 generación' : `${steps} pasos son ${steps} generaciones`;
  return `Cada paso encendido es una llamada al motor: ${calls} en la GPU. Puedes parar en cualquier paso y quedarte con lo hecho.`;
}

const STEP_STATUS = {
  pending: 'PENDIENTE',
  running: 'EN MARCHA',
  done: 'HECHO',
  kept: 'SIN TOCAR',
};

/** El estado real de un paso, leído del trabajo que está corriendo. */
export function sequenceStepStatus(job, index) {
  const steps = Array.isArray(job?.steps) ? job.steps : [];
  const found = steps.find((step) => Number(step?.index) === Number(index));
  if (!found) return { status: 'idle', text: 'SIN EMPEZAR', warning: null, check: null };
  const status = String(found.status ?? 'pending');
  return {
    status,
    text: STEP_STATUS[status] ?? STEP_STATUS.pending,
    warning: found.warning ? String(found.warning) : null,
    // La verificación de la rejilla: qué golpes han caído donde se marcaron.
    check: found.pattern_check ?? null,
  };
}

/** El tramo del paso en mm:ss. El reparto es del servidor, no del cliente. */
export function sequenceIntervalLabel(start, end) {
  const from = Number(start);
  const to = Number(end);
  if (!Number.isFinite(from) || !Number.isFinite(to)) return null;
  return `${clock(from)}–${clock(to)}`;
}

function clock(seconds) {
  const total = Math.max(0, Math.round(Number(seconds) || 0));
  return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, '0')}`;
}

/** El tramo de un paso según la vista previa que Calculó el servidor. */
export function sequencePreviewStep(preview, index) {
  const steps = preview?.sequence?.steps ?? preview?.steps ?? [];
  if (!Array.isArray(steps)) return null;
  return steps.find((step) => Number(step?.index) === Number(index)) ?? null;
}

/** Si algún paso falló al prepararse: el mensaje del preparador. */
export function sequencePreparationError(steps, prepared) {
  for (const step of sequencePayloadSteps(steps).filter((item) => item.enabled)) {
    const status = prepared?.[step.index];
    if (status?.error) return `El paso ${step.index + 1}: ${status.error}`;
  }
  return null;
}

/** Si algún paso con texto todavía se está preparando. */
export function sequenceStepsPending(steps, prepared) {
  return sequencePayloadSteps(steps).filter((item) => item.enabled).some((step) => {
    if (!step.prompt.trim()) return false;
    const status = prepared?.[step.index];
    return !(status?.ready && status?.effectivePrompt);
  });
}

/** Una respuesta solo puede describir la petición completa que la originó. */
export function sequencePreviewState(key, answer) {
  const current = key && answer?.key === key ? answer : null;
  const result = current?.result ?? null;
  return {
    result,
    error: current?.error ?? null,
    ready: Boolean(key && result),
    pending: Boolean(key && !current),
  };
}
