import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { AlertTriangle, Loader2, Sparkles } from 'lucide-react';
import { api, actionError, API_BASE_URL, isEnginePollBlip, isTransportBlip, JOB_POLL_INTERVAL_MS, JOB_POLL_MAX_MISSES, staleTransportError, TRANSPORT_ERROR_CLEAR_MS, PROMPT_PREVIEW_DEBOUNCE_MS } from '../api';
import { ANALYSIS_FALLBACK, deskPhase, movingPercent } from '../desk_phase';
import { ACTIONS, ADJUST_SUBMITTING, CONVERTING, REMIX_SUBMITTING, REPAINT, SEPARATION_SUBMITTING, SCOPE_WHY, SECTIONS, VOICE_SUBMITTING, actionWhy, remixBusyLine } from '../remix_sections';
import useStylePrompt, { usePreparedStylePrompts } from '../useStylePrompt';
import { applyTrackAction, effectiveTrackSelection, emptyStyleSelection, emptyTouchedRoles, stylePromptRequest } from '../style_prompt';
import { arrowDirection, nudgeInterval } from '../timeline_nudge';
import { measuredRemixBpm, remixGroupsNeedStyle, remixMinimumDurationLabel, remixNaturalDuration, remixTimelineFields, repeatBoundsFromWave } from '../remix_timeline';
import { defaultSequenceSteps, sequencePayloadSteps, sequencePreparationError, sequencePreviewState, sequenceStepsPending, sequenceValidation } from '../remix_sequence';
import { patternPayload, patternSummary } from '../remix_pattern';
import { MATERIAL_ENTRY_NOTE, materialOriginLabel } from '../remix_material';
import RemixPanel from './RemixPanel';
import Waveform from './Waveform';
import PromptTools from './PromptTools';
import EffectivePreview from './EffectivePreview';
import StyleEnglish from './StyleEnglish';
import AudioComparator from './AudioComparator';
import RemixSequence from './RemixSequence';
import SequencePattern from './SequencePattern';
import VoiceBackingPanel from './VoiceBackingPanel';

const field = 'px-2 py-1.5 bg-transparent border border-[var(--line)] outline-none focus:border-[var(--acc-line)] text-[12px] min-w-0';
const mediaUrl = (url, name) => url ? new URL(url, API_BASE_URL).href : api.audioUrl(name);
const SEQUENCE_STYLE_PLACEHOLDER = 'Estilo común a todos los pasos (opcional).';
const TEMPO_TEXT = {
  full: 'Cada variante se mide y se ajusta al BPM pedido con DSP local, sin cambiar el tono. Si la medición es incierta, el remix mostrará el error.',
  region: 'En un tramo, el BPM orienta al motor; el audio generado puede tener otro tempo.',
  pendingDuration: 'La duración natural al BPM pedido se conocerá después de generar y ajustar cada variante. Una duración menor se rechazará indicando su mínimo.',
  repetition: 'El recorte se repite hasta alcanzar la duración pedida. Si el reloj de tempo está verificado, las uniones se alinean al pulso; sin reloj se usan fundidos con un aviso de tempo sin garantizar.',
  duration: 'Vacío conserva la duración natural. Si pides más, se repite material real de la base con transiciones. Con recorte se repite ese intervalo; sin recorte, la canción entera.',
  crop: 'Señala el intervalo en la onda o escribe los segundos. Vacío repite la canción entera.',
};

function Fold({ title, why, children, ...rest }) {
  return <details {...rest}>
    <summary className="cursor-pointer">
      <span className="label">{title}</span>
      {why && <span className="ml-3 text-[13px] leading-snug text-[var(--muted)]">{why}</span>}
    </summary>
    {children}
  </details>;
}

export default function RemixWorkspace({ fileName, onDone, initialAction = '', ficha = null, sourceKind = null }) {
  const [capabilities, setCapabilities] = useState(null);
  const [action, setAction] = useState(initialAction === 'tramo' ? 'region' : 'full');
  const remixing = action === 'full' || action === 'region' || action === 'groups' || action === 'sequence';
  const scope = remixing ? action : 'full';
  const sourceKey = JSON.stringify([sourceKind, fileName]);
  const [prompt, setPrompt] = useState('');
  const [controls, setControls] = useState({});
  const [bpm, setBpm] = useState('');
  const [sourceTempo, setSourceTempo] = useState(null);
  const [grooveReading, setGrooveReading] = useState(null);
  const [measuringSource, setMeasuringSource] = useState(null);
  const [durationMinutes, setDurationMinutes] = useState('');
  const [durationSeconds, setDurationSeconds] = useState('');
  const [repeatStart, setRepeatStart] = useState('');
  const [repeatEnd, setRepeatEnd] = useState('');
  const [lyrics, setLyrics] = useState('');
  const [vocalMode, setVocalMode] = useState('source');
  const [outputName, setOutputName] = useState('');
  const [seed, setSeed] = useState('');
  const [advancedGuidance, setAdvancedGuidance] = useState('');
  const [advancedSteps, setAdvancedSteps] = useState('');
  const [advancedUseFormat, setAdvancedUseFormat] = useState(false);
  const [advancedBatch, setAdvancedBatch] = useState('');
  const [region, setRegion] = useState({ start: 0, end: null });
  const [duration, setDuration] = useState(ficha?.duration_seconds ?? null);
  const [groups, setGroups] = useState([]);
  const [actions, setActions] = useState({});
  const [trackText, setTrackText] = useState({});
  const [trackSelections, setTrackSelections] = useState({});
  // Qué papeles ha tocado el usuario en cada pista: lo demás se hereda.
  const [trackSelectionRoles, setTrackSelectionRoles] = useState({});
  // Secuencia de pasos (spec/02 [R20.A]): el estado va con la fuente, así que
  // al cambiar de archivo los pasos vuelven a los que declara el servidor.
  const [sequenceState, setSequenceState] = useState({ sourceKey: null, steps: null });
  const [groupPatternState, setGroupPatternState] = useState({ sourceKey: null, patterns: {}, enabled: {}, editor: null });
  const groupPatternSource = groupPatternState.sourceKey === sourceKey;
  const groupPatterns = groupPatternSource ? groupPatternState.patterns : {};
  const groupPatternEnabled = groupPatternSource ? groupPatternState.enabled : {};
  const groupPatternEditor = groupPatternSource ? groupPatternState.editor : null;
  const setGroupPatterns = (next) => setGroupPatternState((current) => {
    const base = current.sourceKey === sourceKey ? current : { sourceKey, patterns: {}, enabled: {}, editor: null };
    return { ...base, sourceKey, patterns: typeof next === 'function' ? next(base.patterns) : next };
  });
  const setGroupPatternEnabled = (group, value) => setGroupPatternState((current) => {
    const base = current.sourceKey === sourceKey ? current : { sourceKey, patterns: {}, enabled: {}, editor: null };
    return { ...base, sourceKey, enabled: { ...base.enabled, [group]: value } };
  });
  const setGroupPatternEditor = (value) => setGroupPatternState((current) => {
    const base = current.sourceKey === sourceKey ? current : { sourceKey, patterns: {}, enabled: {}, editor: null };
    return { ...base, sourceKey, editor: value };
  });
  const [sequencePreview, setSequencePreview] = useState(null);
  const [sequencePreviewError, setSequencePreviewError] = useState(null);
  const defaultStepsCount = Number(capabilities?.sequence?.default_steps) || 0;
  const defaultSequence = useMemo(() => defaultSequenceSteps(defaultStepsCount), [defaultStepsCount]);
  const sequenceSteps = sequenceState.sourceKey === sourceKey && sequenceState.steps
    ? sequenceState.steps
    : defaultSequence;
  const setSequenceSteps = (next) => setSequenceState({
    sourceKey,
    steps: typeof next === 'function' ? next(sequenceSteps) : next,
  });
  const exclusionSource = scope === 'groups'
    ? [prompt, ...groups.filter((group) => actions[group.id] === 'transform').map((group) => trackText[group.id] ?? '')].filter(Boolean).join(' ')
    : scope === 'sequence'
      ? sequenceSteps.map((step) => step.prompt ?? '').filter(Boolean).join(' ')
      : null;
  const prepared = useStylePrompt(prompt, exclusionSource);
  // Cada paso pasa por el mismo preparador común que el prompt general
  // (glosario, exclusiones y matices). El estilo común lo lleva el prompt
  // general, que se antepone al texto de cada paso.
  const sequenceInputs = useMemo(() => Object.fromEntries(sequenceSteps.map((step) => [
    `paso-${step.index}`,
    stylePromptRequest(scope === 'sequence' ? (step.prompt ?? '') : '', emptyStyleSelection(), null),
  ])), [sequenceSteps, scope]);
  const preparedSequence = usePreparedStylePrompts(sequenceInputs);
  const preparedSequenceByIndex = useMemo(() => Object.fromEntries(
    sequenceSteps.map((step) => [step.index, preparedSequence[`paso-${step.index}`]])), [sequenceSteps, preparedSequence]);
  const sequenceStepTexts = useMemo(() => Object.fromEntries(sequenceSteps.map((step) => {
    const own = preparedSequenceByIndex[step.index]?.effectivePrompt ?? '';
    return [step.index, [prepared.effectivePrompt, own].filter(Boolean).join('\n')];
  })), [sequenceSteps, preparedSequenceByIndex, prepared.effectivePrompt]);
  // Lo que se envía de verdad por paso: el estilo común delante del texto del
  // paso. Mientras el texto del paso se prepara, no se enseña nada en falso.
  const sequenceSentTexts = useMemo(() => Object.fromEntries(sequenceSteps.map((step) => {
    const status = preparedSequenceByIndex[step.index];
    const own = status?.effectivePrompt ?? '';
    const written = Boolean((step.prompt ?? '').trim());
    const value = (!written || status?.ready) ? [prepared.effectivePrompt, own].filter(Boolean).join('\n') : null;
    return [step.index, value];
  })), [sequenceSteps, preparedSequenceByIndex, prepared.effectivePrompt]);
  // La pista hereda del prompt general PAPEL POR PAPEL (principal, matices y
  // ficha): lo que el usuario no toca sigue viniendo del general; lo que toca
  // pasa a ser de la pista. Así su texto va en su línea, con su papel, y no
  // pegado a la descripción global.
  const trackRoles = (groupId) => trackSelectionRoles[groupId] ?? emptyTouchedRoles();
  const trackSelection = (groupId) => effectiveTrackSelection(
    trackSelections[groupId] ?? emptyStyleSelection(), trackRoles(groupId), prepared.selection);
  const preparedTracks = usePreparedStylePrompts(Object.fromEntries(groups.filter((group) => actions[group.id] === 'transform').map((group) => [group.id, stylePromptRequest(trackText[group.id] ?? '', trackSelection(group.id), exclusionSource)])));
  const [gains, setGains] = useState({});
  const [solo, setSolo] = useState(null);
  const [reference, setReference] = useState('');
  const [references, setReferences] = useState([]);
  const [advanced, setAdvanced] = useState(false);
  const [busy, setBusy] = useState(false);
  const [pendingMessage, setPendingMessage] = useState(REMIX_SUBMITTING);
  const [job, setJob] = useState(null);
  const [outputs, setOutputs] = useState([]);
  const [error, setError] = useState(null);
  const [notice, setNotice] = useState(null);
  const [analysis, setAnalysis] = useState(null);
  const [classification, setClassification] = useState('unknown');
  const [classificationOrigin, setClassificationOrigin] = useState('unknown');
  const [analysisStatus, setAnalysisStatus] = useState(null);
  const [analysisError, setAnalysisError] = useState(null);
  const currentJob = useRef(null);
  const alive = useRef(true);
  const classificationEdited = useRef(false);
  const workspace = useRef(null);
  const currentSourceKey = useRef(sourceKey);
  currentSourceKey.current = sourceKey;
  const measurementRequest = useRef(0);
  const sourceBpm = sourceTempo?.sourceKey === sourceKey ? sourceTempo.value : '';
  const sourceBpmOrigin = sourceTempo?.sourceKey === sourceKey ? sourceTempo.origin : 'measurement';
  const groove = grooveReading?.sourceKey === sourceKey ? grooveReading.groove : null;
  const grooveError = grooveReading?.sourceKey === sourceKey ? grooveReading.error : null;
  const grooveBusy = measuringSource === sourceKey;
  const originalUrl = sourceKind === 'upload' ? api.uploadUrl(fileName) : api.audioUrl(fileName);

  useEffect(() => {
    alive.current = true;
    let active = true;
    const loadCapabilities = async () => {
      while (active) {
        try {
          const data = await api.remixCapabilities();
          if (active) {
            setCapabilities(data);
            setControls(data.defaults ?? {});
            const d = data.defaults ?? {};
            setAdvancedGuidance(String(d.guidance_scale ?? ''));
            setAdvancedSteps(String(d.inference_steps ?? ''));
            setAdvancedUseFormat(Boolean(d.use_format));
            setAdvancedBatch(String(d.batch_size ?? ''));
          }
          return;
        } catch (err) {
          if (!active) return;
          if (!isTransportBlip(err.message)) { setError(err.message); return; }
          await new Promise((resolve) => setTimeout(resolve, TRANSPORT_ERROR_CLEAR_MS));
        }
      }
    };
    const loadDuration = async () => {
      while (active) {
        try {
          const data = await api.audioPeaks(fileName, undefined, sourceKind);
          if (active) setDuration(data.duration_seconds);
          return;
        } catch (err) {
          if (!active) return;
          if (!isTransportBlip(err.message)) { setNotice(`Duración no disponible: ${err.message}`); return; }
          await new Promise((resolve) => setTimeout(resolve, TRANSPORT_ERROR_CLEAR_MS));
        }
      }
    };
    void loadCapabilities();
    void loadDuration();
    return () => { active = false; alive.current = false; };
  }, [fileName, sourceKind]);

  useEffect(() => {
    if (!isTransportBlip(error)) return undefined;
    let active = true;
    const clearIfBack = async () => {
      const health = await api.engineHealth();
      if (active) setError((current) => (staleTransportError(current, health?.api === 'ok') ? null : current));
    };
    const timer = setInterval(() => { void clearIfBack(); }, TRANSPORT_ERROR_CLEAR_MS);
    void clearIfBack();
    return () => { active = false; clearInterval(timer); };
  }, [error]);

  const measureSourceTempo = useCallback(async () => {
    const request = ++measurementRequest.current;
    setMeasuringSource(sourceKey);
    const current = () => alive.current && currentSourceKey.current === sourceKey
      && measurementRequest.current === request;
    try {
      while (current()) {
        try {
          const measured = await api.groove(fileName, sourceKind);
          if (!current()) return;
          setGrooveReading({ sourceKey, groove: measured, error: null });
          const valid = measuredRemixBpm(measured, capabilities);
          setSourceTempo((previous) => previous?.sourceKey === sourceKey && previous.origin === 'manual' && previous.value !== ''
            ? previous : { sourceKey, value: valid == null ? '' : String(valid), origin: 'measurement' });
          return;
        } catch (err) {
          if (!current()) return;
          if (!isTransportBlip(err.message)) {
            setGrooveReading({ sourceKey, groove: null, error: err.message });
            setSourceTempo((previous) => previous?.sourceKey === sourceKey && previous.origin === 'manual' && previous.value !== ''
              ? previous : { sourceKey, value: '', origin: 'measurement' });
            return;
          }
          // La medición sigue ocupada durante la espera: el efecto de por pistas no se relanza en bucle.
          await new Promise((resolve) => setTimeout(resolve, TRANSPORT_ERROR_CLEAR_MS));
        }
      }
    } finally {
      if (current()) setMeasuringSource(null);
    }
  }, [fileName, sourceKind, sourceKey, capabilities]);

  useEffect(() => {
    if (scope === 'groups' && bpm !== '' && capabilities && !busy && !grooveBusy
      && grooveReading?.sourceKey !== sourceKey) void measureSourceTempo();
  }, [scope, bpm, capabilities, busy, grooveBusy, grooveReading, sourceKey, measureSourceTempo]);

  useEffect(() => {
    if (!advanced) return undefined;
    let active = true;
    const loadReferences = async () => {
      while (active) {
        const results = await Promise.allSettled([api.library(), api.uploads()]);
        if (!active) return;
        setReferences(results.flatMap((result, index) => result.status === 'fulfilled'
          ? (result.value.items ?? []).map((item) => ({ id: `${index === 0 ? 'output' : 'upload'}:${item.name}`, name: item.name, kind: index === 0 ? 'output' : 'upload' })) : [])
          .filter((item) => !(item.name === fileName && item.kind === sourceKind)));
        const rejected = results.filter((result) => result.status === 'rejected');
        const real = rejected.map((result) => result.reason?.message).filter((message) => message && !isTransportBlip(message));
        if (real.length) { setNotice(`Referencias incompletas: ${real.join(' · ')}`); return; }
        if (!rejected.length) return;
        await new Promise((resolve) => setTimeout(resolve, TRANSPORT_ERROR_CLEAR_MS));
      }
    };
    void loadReferences();
    return () => { active = false; };
  }, [advanced, fileName, sourceKind]);

  useEffect(() => {
    if (!advanced) return undefined;
    let active = true;
    const detect = async () => {
      while (active) {
        setAnalysisStatus(ANALYSIS_FALLBACK);
        try {
          const started = await api.remixAnalyze({ source_name: fileName, source_kind: sourceKind });
          let misses = 0;
          while (active) {
            try {
              const result = await api.remixAnalyzeStatus(started.job_id);
              if (!active) return;
              misses = 0;
              setAnalysisStatus(deskPhase(result.phase, ANALYSIS_FALLBACK));
              if (result.status === 'failed') { setAnalysisError(result.error ?? 'El análisis falló'); return; }
              if (result.status === 'succeeded') {
                setAnalysis(result.result);
                if (!classificationEdited.current) {
                  const detected = result.result?.classification ?? 'unknown';
                  setClassification(detected); setClassificationOrigin(detected === 'unknown' ? 'unknown' : 'analysis');
                }
                return;
              }
            } catch (err) {
              if (!active) return;
              if (isTransportBlip(err.message)) {
                await new Promise((resolve) => setTimeout(resolve, TRANSPORT_ERROR_CLEAR_MS));
                continue;
              }
              if (++misses >= JOB_POLL_MAX_MISSES) throw err;
            }
            await new Promise((resolve) => setTimeout(resolve, JOB_POLL_INTERVAL_MS));
          }
          return;
        } catch (err) {
          if (!active) return;
          if (!isTransportBlip(err.message)) { setAnalysisError(err.message); return; }
          await new Promise((resolve) => setTimeout(resolve, TRANSPORT_ERROR_CLEAR_MS));
        }
      }
    };
    void detect().finally(() => { if (active) setAnalysisStatus(null); });
    return () => { active = false; setAnalysisStatus(null); };
  }, [advanced, fileName, sourceKind]);

  // La secuencia pide al servidor la división de la canción: los tramos y si
  // caen en compases completos los calcula él (spec/02 [R20.A]). La clave
  // identifica la respuesta por TODAS las entradas efectivas: el reparto
  // (pasos y BPM) y el caption (texto preparado, patrón y estilo común).
  // Así una respuesta anterior no se enseña como si fuera la actual
  // (logs/state-review-20261112/reviewer.md, R1).
  const sequenceRepartitionKey = useMemo(() => JSON.stringify({
    steps: sequenceSteps.map((step) => ({
      index: step.index, enabled: step.enabled, focus: step.focus,
    })),
    sourceBpm: sourceBpm || '',
  }), [sequenceSteps, sourceBpm]);
  const sequenceCaptionKey = useMemo(() => JSON.stringify({
    repartition: sequenceRepartitionKey,
    style: prepared.effectivePrompt || '',
    steps: sequenceSteps.map((step) => ({
      index: step.index,
      // El texto PREPARADO es el que se envía: mientras se prepara no hay
      // caption que enseñar (vacío ≠ el texto que se está escribiendo).
      text: sequenceSentTexts[step.index] ?? '',
      pattern: step.enabled && step.patternEnabled === true ? patternPayload(step.pattern) : null,
    })),
  }), [sequenceRepartitionKey, prepared.effectivePrompt, sequenceSteps, sequenceSentTexts]);
  const sequencePreviewRequest = useMemo(() => ({
    source_name: fileName, source_kind: sourceKind, scope: 'sequence',
    // Viaja el texto PREPARADO, el mismo que se envía: el caption que
    // devuelve el servidor es entonces el que recibirá el motor.
    steps: sequencePayloadSteps(sequenceSteps.map((step) => ({
      ...step, prompt: sequenceSentTexts[step.index] ?? step.prompt ?? '',
    }))),
    // Solo viaja el BPM **revisado a mano**: si el valor viene de la medición
    // automática lo mide el servidor, y así la ficha declara bien su origen.
    ...(sourceBpm !== '' && sourceBpmOrigin === 'manual' ? { source_bpm: Number(sourceBpm) } : {}),
  }), [fileName, sourceKind, sequenceSteps, sequenceSentTexts, sourceBpm, sourceBpmOrigin]);
  const latestSequenceRequest = useRef(null);
  useEffect(() => { latestSequenceRequest.current = sequencePreviewRequest; }, [sequencePreviewRequest]);
  useEffect(() => {
    if (scope !== 'sequence' || !capabilities) return undefined;
    let active = true;
    const timer = setTimeout(async () => {
      const request = latestSequenceRequest.current;
      if (!request) return;
      const problem = sequenceValidation(request.steps, { maxSteps: Number(capabilities?.sequence?.max_steps) || 0 }).error;
      if (problem) { if (active) { setSequencePreview(null); setSequencePreviewError(null); } return; }
      while (active) {
        try {
          const result = await api.remixPreview(request);
          if (active) {
            setSequencePreview({ key: sequenceCaptionKey, repartitionKey: sequenceRepartitionKey, result });
            setSequencePreviewError(null);
          }
          return;
        } catch (err) {
          if (!active) return;
          if (!isTransportBlip(err.message)) { setSequencePreviewError(err.message); return; }
          await new Promise((resolve) => setTimeout(resolve, TRANSPORT_ERROR_CLEAR_MS));
        }
      }
    }, PROMPT_PREVIEW_DEBOUNCE_MS);
    return () => { active = false; clearTimeout(timer); };
  }, [scope, capabilities, sequenceCaptionKey, sequenceRepartitionKey]);
  // La respuesta solo describe la petición que la originó: si cambiaron el
  // texto, el patrón o el estilo común, el caption anterior no se enseña.
  const sequencePreviewAnswer = sequencePreviewState(sequenceCaptionKey, sequencePreview);
  // Mientras el texto de un paso se prepara no hay caption que enseñar: el
  // que se pintaría no sería el que se envía.
  const sequenceCaptionReady = sequenceSteps
    .filter((step) => step.enabled)
    .every((step) => sequenceSentTexts[step.index] != null);

  const onRange = useCallback((selection) => setRegion({ start: selection.trim_start_s ?? 0, end: selection.trim_end_s }), []);
  const onRepeatRange = useCallback((selection) => {
    const bounds = repeatBoundsFromWave(selection);
    setRepeatStart(bounds.start);
    setRepeatEnd(bounds.end);
  }, []);
  const update = (name, value) => setControls((current) => ({ ...current, [name]: value }));
  const bounds = (name) => capabilities?.parameters?.[name];
  const range = (name, label) => {
    const limits = bounds(name);
    if (!limits || controls[name] == null) return null;
    return <label key={name} className="flex items-center gap-3 flex-wrap"><span className="label">{label}</span>
      <input aria-label={label} type="range" min={limits.min} max={limits.max} step={limits.step ?? 'any'} value={controls[name]} disabled={busy}
        onChange={(event) => update(name, Number(event.target.value))} className="flex-1 min-w-[100px]" />
      <span className="mono text-[11px]">{Number(controls[name]).toFixed(2)}</span></label>;
  };
  const poll = async (id, read) => {
    currentJob.current = id;
    let misses = 0;
    while (alive.current) {
      try {
        const incoming = await read(id);
        misses = 0;
        if (alive.current) setJob(incoming);
        if (incoming.status === 'succeeded') return incoming;
        if (incoming.status === 'failed' || incoming.status === 'cancelled') {
          const failure = new Error(incoming.error ?? 'La operación no se completó'); failure.finished = true; throw failure;
        }
      } catch (err) {
        if (err.finished) throw err;
        // Un trabajo ya lanzado se sigue sondeando. El corte no se escribe en el aviso.
        if (isTransportBlip(err.message)) {
          // La API puede haberse reiniciado: busca el trabajo antes de rendirse.
          try {
            const found = await api.findJob(id);
            if (found) {
              misses = 0;
              if (alive.current) setJob(found);
              if (found.status === 'succeeded') return found;
              if (found.status === 'failed') {
                const failure = new Error(found.error ?? 'La operación no se completó');
                failure.finished = true;
                throw failure;
              }
              continue;
            }
          } catch {
            // La API sigue caída.
          }
        }
        if (!isEnginePollBlip(err.message)) {
          if (++misses >= JOB_POLL_MAX_MISSES) throw err;
          if (alive.current) setNotice(`Sondeo interrumpido: ${err.message}. Reintentando…`);
        }
      }
      await new Promise((resolve) => setTimeout(resolve, JOB_POLL_INTERVAL_MS));
    }
    return null;
  };
  const execute = async (operation, waitingMessage = REMIX_SUBMITTING) => {
    setBusy(true); setPendingMessage(waitingMessage); setError(null); setNotice(null); setSolo(null); setJob(null);
    try { await operation(); }
    catch (err) { if (alive.current) setError(actionError(err.message)); }
    finally { currentJob.current = null; if (alive.current) { setBusy(false); setPendingMessage(REMIX_SUBMITTING); } }
  };
  const separate = () => execute(async () => {
    const started = await api.remixSeparate({ file_name: fileName, source_kind: sourceKind });
    const done = await poll(started.job_id, api.separateJob);
    if (!done || !alive.current) return;
    const actual = done.groups ?? done.result?.groups;
    if (!Array.isArray(actual) || !actual.length) throw new Error('La separación terminó sin grupos disponibles');
    setGroups(actual); setActions(Object.fromEntries(actual.map((group) => [group.id, 'keep'])));
    setNotice('Pistas separadas. Escucha cada grupo y elige su acción.');
  }, SEPARATION_SUBMITTING);
  const sequenceValidationError = scope === 'sequence'
    ? sequenceValidation(sequenceSteps, { maxSteps: Number(capabilities?.sequence?.max_steps) || 0 }).error
    : null;
  // El BPM revisado a mano reparte los pasos: se comprueba aquí, no en el servidor.
  const sequenceBpmLimits = bounds('source_bpm') ?? bounds('bpm');
  const sequenceBpmError = scope === 'sequence' && sourceBpm !== ''
    && (!Number.isFinite(Number(sourceBpm))
      || (sequenceBpmLimits?.min != null && Number(sourceBpm) < sequenceBpmLimits.min)
      || (sequenceBpmLimits?.max != null && Number(sourceBpm) > sequenceBpmLimits.max))
    ? 'El BPM original revisado tiene que ser un número dentro de los límites indicados.' : null;
  const sequencePreparationNote = scope === 'sequence' ? sequencePreparationError(sequenceSteps, preparedSequenceByIndex) : null;
  const sequencePending = scope === 'sequence' && sequenceStepsPending(sequenceSteps, preparedSequenceByIndex);
  const promptsReady = prepared.ready && !sequencePending && (scope !== 'groups' || Object.values(preparedTracks).every((item) => item.ready));
  const sentPrompt = scope === 'groups'
    ? [prepared.effectivePrompt, ...groups.filter((group) => actions[group.id] === 'transform').map((group) => preparedTracks[group.id]?.effectivePrompt || '')].filter(Boolean).join('\n')
    : prepared.effectivePrompt;
  const timelineSourceBpm = sourceBpm || measuredRemixBpm(groove, capabilities) || '';
  const naturalDuration = remixNaturalDuration({ scope, sourceDuration: duration, targetBpm: bpm, sourceBpm: timelineSourceBpm });
  const timeline = remixTimelineFields({ scope, targetBpm: bpm, sourceBpm: timelineSourceBpm, sourceBpmOrigin: sourceBpm ? sourceBpmOrigin : 'measurement', minutes: durationMinutes, seconds: durationSeconds,
    repeatStart, repeatEnd, transition: '', sourceDuration: duration, capabilities });
  const transformsGroups = scope === 'groups' && Object.values(actions).includes('transform');
  const needsStyle = scope !== 'groups' || remixGroupsNeedStyle({ transforms: transformsGroups });
  const needsCover = scope !== 'groups' || transformsGroups;
  const bpmError = bpm !== '' && (!Number.isFinite(Number(bpm)) || !Number.isInteger(Number(bpm)) || Number(bpm) <= 0
    || (bounds('bpm')?.min != null && Number(bpm) < bounds('bpm').min)
    || (bounds('bpm')?.max != null && Number(bpm) > bounds('bpm').max)) ? 'Escribe un BPM entero dentro de los límites indicados.' : null;
  const advancedError = needsStyle && [
    ['guidance_scale', advancedGuidance, false],
    ['inference_steps', advancedSteps, true],
    ['batch_size', advancedBatch, true],
  ].some(([key, value, integer]) => value !== '' && (
    !Number.isFinite(Number(value)) || (integer && !Number.isInteger(Number(value)))
    || (bounds(key)?.min != null && Number(value) < bounds(key).min)
    || (bounds(key)?.max != null && Number(value) > bounds(key).max)
  )) ? 'Revisa los parámetros avanzados: pasos y lote deben ser enteros positivos; guidance debe ser finito y no negativo, dentro de los límites indicados.' : null;
  const requestError = bpmError || timeline.error || advancedError || sequenceValidationError || sequenceBpmError;
  const hasTargetDuration = durationMinutes !== '' || durationSeconds !== '';
  const chosenReference = needsCover ? references.find((item) => item.id === reference) : null;
  const payload = {
    source_name: fileName, source_kind: sourceKind, source_classification: classification, classification_origin: classificationOrigin, prompt: needsStyle ? sentPrompt : '', scope,
    output_name: outputName.trim() || null,
    ...(seed !== '' && needsStyle ? { seed: Number(seed) } : {}),
    ...(scope !== 'sequence' && bpm !== '' ? { bpm: Number(bpm) } : {}),
    ...timeline.fields,
    ...(scope !== 'groups' && vocalMode === 'instrumental' ? { instrumental: true } : {}),
    ...(scope !== 'groups' && vocalMode === 'lyrics' ? { instrumental: false, lyrics: lyrics.trim() } : {}),
    ...(scope === 'region' ? { region_start: Number(region.start), region_end: Number(region.end ?? duration), repaint_mode: controls.repaint_mode, ...(controls.repaint_mode === 'balanced' ? { repaint_strength: controls.repaint_strength } : {}) }
      : scope === 'sequence' ? {} : needsCover ? { cover_strength: controls.cover_strength, cover_noise_strength: controls.cover_noise_strength } : {}),
    ...(scope === 'groups' ? { groups: actions, gains_db: Object.fromEntries(Object.entries(gains).filter(([id]) => actions[id] !== 'remove')) } : {}),
    ...(scope === 'groups' && groupPatternEnabled.drums && patternPayload(groupPatterns.drums)
      ? { patterns: { drums: patternPayload(groupPatterns.drums) } } : {}),
    // La secuencia manda orden e intención: el servidor reparte los tramos.
    ...(scope === 'sequence' ? { steps: sequencePayloadSteps(sequenceSteps.map((step) => ({ ...step, prompt: sequenceStepTexts[step.index] ?? '' }))) } : {}),
    // El BPM revisado a mano es el tempo con el que el servidor reparte los pasos.
    ...(scope === 'sequence' && sourceBpm !== '' && sourceBpmOrigin === 'manual' ? { source_bpm: Number(sourceBpm) } : {}),
    ...(chosenReference ? { reference_name: chosenReference.name, reference_kind: chosenReference.kind } : {}),
    ...(needsStyle && advancedGuidance !== '' ? { guidance_scale: Number(advancedGuidance) } : {}),
    ...(needsStyle && advancedSteps !== '' ? { inference_steps: Number(advancedSteps) } : {}),
    ...(needsStyle ? { use_format: advancedUseFormat } : {}),
    ...(needsStyle && advancedBatch !== '' && scope !== 'sequence' ? { batch_size: Number(advancedBatch) } : {}),
  };
  const run = () => execute(async () => {
    if (needsStyle && !promptsReady) throw new Error('Espera a que todos los prompts estén preparados.');
    if (needsStyle && !sentPrompt && scope !== 'sequence') throw new Error('Describe los cambios que quieres hacer');
    if (scope === 'sequence') {
      if (sequenceValidationError) throw new Error(sequenceValidationError);
      if (sequencePreparationNote) throw new Error(sequencePreparationNote);
      if (sequencePending) throw new Error('Espera a que los textos de los pasos estén preparados.');
    }
    if (scope === 'groups' && !groups.length) throw new Error('Separa primero las pistas del original');
    if (scope === 'region' && !(Number(region.end ?? duration) > Number(region.start))) throw new Error('Selecciona un tramo con final posterior al inicio');
    if (grooveBusy) throw new Error('Espera a que termine la medición del BPM original.');
    if (requestError) throw new Error(requestError);
    if (vocalMode === 'lyrics' && scope !== 'groups' && !lyrics.trim()) throw new Error('Escribe la letra nueva');
    await api.remixPreview(payload);
    const started = await api.remixProject(payload);
    const done = await poll(started.job_id, api.remixAiStatus);
    if (!done || !alive.current) return;
    const result = done.result ?? {};
    const variants = result.variants ?? [result.mix ?? result.base ?? done.output_name].filter(Boolean);
    if (!variants.length) throw new Error('El trabajo terminó sin archivos de audio disponibles');
    setOutputs(variants); setNotice('Remix guardado. Compara las variantes con el original.'); onDone?.(variants[0]);
  });
  const local = (operation) => execute(async () => {
    const result = await operation();
    if (alive.current) { setOutputs([result.file_name]); setNotice(`Guardado: ${result.file_name}`); onDone?.(result.file_name); }
  }, ADJUST_SUBMITTING);
  const voiceBacking = (request) => execute(async () => {
    await api.remixAiPreview(request);
    const started = await api.remixAi(request);
    const done = await poll(started.job_id, api.remixAiStatus);
    if (!done || !alive.current) return;
    const variants = done.result?.variants ?? [done.result?.mix].filter(Boolean);
    if (!variants.length) throw new Error('La operación terminó sin variantes de voz y base disponibles');
    setOutputs(variants); setNotice('Voz original y base nueva guardadas. Escucha y compara las variantes.'); onDone?.(variants[0]);
  }, VOICE_SUBMITTING);
  const cancel = async () => {
    if (!currentJob.current) return;
    try { await api.cancelJob(currentJob.current); setNotice('Cancelación solicitada. Esperando confirmación.'); }
    catch (err) { setError(actionError(err.message)); }
  };
  const stopSequence = async () => {
    if (!currentJob.current) return;
    try { await api.remixProjectStop(currentJob.current); setNotice('Parada pedida: se entrega lo hecho hasta el paso actual.'); }
    catch (err) { setError(actionError(err.message)); }
  };

  const nudgeStep = capabilities?.parameters?.timeline_nudge_seconds?.step;
  const nudgeRegion = (edge) => (event) => {
    const direction = arrowDirection(event.key);
    if (!direction || busy || !duration) return;
    event.preventDefault();
    const next = nudgeInterval({
      start: Number(region.start) || 0,
      end: region.end === '' || region.end == null ? null : Number(region.end),
      duration,
      edge,
      direction,
      step: nudgeStep,
    });
    if (next) setRegion({ start: next.start, end: next.end });
  };
  const activeScope = (capabilities?.scopes ?? []).find((item) => item.id === scope);
  const scopeWhy = remixing ? (activeScope?.why || SCOPE_WHY[scope]) : actionWhy(action);
  const phase = deskPhase(job?.phase, '');
  const ratio = job?.progress_ratio;
  const spoken = remixBusyLine(phase, action, ratio, !!job, pendingMessage);
  const busyLine = spoken || job?.error || 'La operación no se completó';
  const percent = movingPercent(phase, ratio);
  // El BPM original se revisa igual en «por pistas» y en la secuencia: el
  // control, la medición y la ficha de origen son los mismos; solo cambian la
  // etiqueta accesible y la frase que dice qué hacer con el valor.
  const sourceTempoControls = ({ label, uncertain }) => <>
    <div className="flex items-center gap-3 flex-wrap">
      <label className="label">BPM ORIGINAL <input aria-label={label} type="number" min={(bounds('source_bpm') ?? bounds('bpm'))?.min} max={(bounds('source_bpm') ?? bounds('bpm'))?.max} step="any" value={sourceBpm} disabled={busy} placeholder="Detección automática" onChange={(event) => setSourceTempo({ sourceKey, value: event.target.value, origin: 'manual' })} className={`${field} w-44`} /></label>
      <button type="button" disabled={busy || grooveBusy || !capabilities} onClick={() => void measureSourceTempo()} className="btn btn-ghost h-8 px-3">{grooveBusy ? 'MIDIENDO…' : 'MEDIR BPM ORIGINAL'}</button>
    </div>
    {grooveBusy && <p role="status" className="text-[13px] text-[var(--muted)]">Midiendo el tempo del original con DSP local…</p>}
    {groove && <p className="text-[13px] text-[var(--muted)]" data-source-tempo-measurement>{Number(groove.bpm) > 0 ? `Medido: ${Number(groove.bpm).toFixed(1)} BPM.` : 'No se pudo determinar el tempo.'} {Number.isFinite(Number(groove.confidence)) ? `Confianza: ${(Number(groove.confidence) * 100).toFixed(0)}%. ` : ''}{measuredRemixBpm(groove, capabilities) != null ? 'Puedes corregirlo en BPM ORIGINAL.' : uncertain}</p>}
    {grooveError && <p role="alert" className="text-[13px] st-err">Medición del BPM original: {grooveError}</p>}
    {sourceBpm !== '' && <p className="mono text-[10px] text-[var(--faint)]">{sourceBpmOrigin === 'manual' ? 'BPM original revisado manualmente.' : 'BPM original precargado de la medición automática.'}</p>}
  </>;
  const comparisonTracks = useMemo(() => [{ id: 'original', label: 'ORIGINAL', url: originalUrl, duration },
    ...outputs.map((name, index) => ({ id: name, label: `VARIANTE ${String.fromCharCode(65 + index)} · ${name}`, url: api.audioUrl(name) }))], [originalUrl, duration, outputs]);

  return <div ref={workspace} className="flex flex-col gap-3" data-remix-project onPlayCapture={(event) => {
    workspace.current?.querySelectorAll('audio').forEach((player) => { if (player !== event.target) player.pause(); });
  }}>
    <div className="flex flex-col gap-2">
      <p className="text-[13px] text-[var(--muted)]">{fileName}{duration == null ? '' : ` · ${Number(duration).toFixed(1)} s`}</p>
      <label className="flex flex-col gap-1">
        <span className="text-[13px] text-[var(--text)]">Qué hacer</span>
        <select aria-label="Qué hacer" className="desk-select" disabled={busy || grooveBusy || !capabilities} value={action} onChange={(event) => { setAction(event.target.value); setSolo(null); }}>
          {ACTIONS.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}
        </select>
      </label>
      {!capabilities && !error && <span className="text-[13px] text-[var(--muted)]">Cargando opciones…</span>}
    </div>
    {scopeWhy && <p className="text-[13px] leading-snug">{scopeWhy}</p>}
    {remixing && <p className="text-[13px] leading-snug text-[var(--muted)]" data-material-origin-note>{MATERIAL_ENTRY_NOTE}</p>}
    {remixing && scope === 'region' && <div className="flex flex-col gap-2"><Waveform key={`${sourceKind}:${fileName}`} fileName={fileName} sourceKind={sourceKind} onSelection={onRange} selection={region} disabled={busy} nudgeStep={nudgeStep} scales={false} />
      <div className="flex gap-3 flex-wrap">
        <label className="label">DESDE <input aria-label="Inicio del tramo" type="number" min="0" step={Number(nudgeStep) > 0 ? nudgeStep : undefined} disabled={busy} value={region.start} onKeyDown={nudgeRegion('start')} onChange={(event) => setRegion((current) => ({ ...current, start: event.target.value }))} className={`${field} w-24`} /> s</label>
        <label className="label">HASTA <input aria-label="Final del tramo" type="number" min="0" step={Number(nudgeStep) > 0 ? nudgeStep : undefined} disabled={busy} value={region.end ?? duration ?? ''} onKeyDown={nudgeRegion('end')} onChange={(event) => setRegion((current) => ({ ...current, end: event.target.value }))} className={`${field} w-24`} /> s</label>
      </div>
      <label className="flex flex-col gap-1 text-[13px] text-[var(--text)]">Transición <select aria-label="Modo de edición regional" disabled={busy} className="desk-select" value={controls.repaint_mode ?? ''} onChange={(event) => update('repaint_mode', event.target.value)}>
        {(capabilities?.repaint_modes ?? []).map((item) => {
          const id = item.id ?? item;
          return <option key={id} value={id}>{REPAINT[id]?.label || item.label || id}</option>;
        })}</select></label>
      {REPAINT[controls.repaint_mode]?.why && <p className="text-[13px] leading-snug">{REPAINT[controls.repaint_mode].why}</p>}
      {controls.repaint_mode === 'balanced' && range('repaint_strength', 'TRANSFORMACIÓN DEL TRAMO')}
      {capabilities?.limitations?.repaint_normalization && <Fold title={SECTIONS.limit.title} why={SECTIONS.limit.why}><p className="mono text-[10px] text-[var(--faint)] py-2">{capabilities.limitations.repaint_normalization}</p></Fold>}
    </div>}
    {remixing && scope === 'groups' && <div className="flex flex-col gap-2">
      {!groups.length && <button type="button" disabled={busy || grooveBusy || !capabilities || !!analysisStatus} onClick={() => void separate()} className="btn btn-signal h-10 px-4 self-start">SEPARAR PISTAS DEL ORIGINAL</button>}
      {analysisStatus && !groups.length && <p role="status" className="text-[13px]">{analysisStatus} La separación espera a que termine.</p>}
      {groups.map((group) => <div key={group.id} className="stem-row border-b border-[var(--line)] py-2">
        <span className="text-[14px] text-[var(--text)]">{group.label}</span>
        <select aria-label={`Acción de ${group.label}`} disabled={busy} value={actions[group.id] ?? 'keep'} onChange={(event) => setActions((current) => ({ ...current, [group.id]: event.target.value }))} className="desk-select">
          {(capabilities?.actions ?? []).map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}
        </select>
        <button type="button" disabled={busy} aria-pressed={solo === group.id} onClick={() => setSolo((current) => current === group.id ? null : group.id)} className="btn btn-ghost h-8 px-2">{solo === group.id ? 'CERRAR SOLO' : 'SOLO'}</button>
        {actions[group.id] === 'transform' && <fieldset disabled={busy} className="flex flex-col gap-2 border-0 p-0 min-w-0" style={{ gridColumn: '1 / -1' }}>
          <textarea aria-label={`Texto de ${group.label}`} value={trackText[group.id] ?? ''} placeholder="Qué cambia en esta pista" onChange={(event) => setTrackText((current) => ({ ...current, [group.id]: event.target.value }))} rows={2} className={`${field} w-full resize-y`} />
          <PromptTools prompt={trackText[group.id] ?? ''}
            setPrompt={(next) => setTrackText((current) => ({ ...current, [group.id]: typeof next === 'function' ? next(current[group.id] ?? '') : next }))}
            prepared={{ ...preparedTracks[group.id], selection: trackSelection(group.id),
              setSelection: (next) => {
                // La acción parte de lo que el usuario VE (la selección
                // efectiva) y solo deja de heredarse el papel que cambia.
                const step = applyTrackAction(
                  trackSelections[group.id] ?? emptyStyleSelection(),
                  trackRoles(group.id),
                  prepared.selection,
                  next,
                );
                setTrackSelections((current) => ({ ...current, [group.id]: step.own }));
                setTrackSelectionRoles((current) => ({ ...current, [group.id]: step.touched }));
              } }} disabled={busy} />
          {group.id === 'drums' && <div className="flex flex-col gap-2 border border-[var(--line)] rounded p-2" data-group-pattern="drums">
            <button type="button" aria-expanded={groupPatternEditor === 'drums'}
              disabled={busy} onClick={() => setGroupPatternEditor(groupPatternEditor === 'drums' ? null : 'drums')}
              className="btn btn-ghost min-h-8 px-2 self-start" data-group-pattern-toggle="drums">
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
          </div>}
        </fieldset>}
        {solo === group.id && <audio controls autoPlay src={mediaUrl(group.url, group.file_name)} aria-label={`Escuchar ${group.label}`} className="player w-full" style={{ gridColumn: '1 / -1' }} />}
      </div>)}
      {remixing && needsStyle && promptsReady && !requestError && scope === 'groups' && <StyleEnglish request={payload}
        why="El modelo recibe un solo texto: el prompt general más una línea por cada pista en «transformar». Se muestra el texto efectivo del servidor. Las pistas no se tratan por separado." />}
      <p className="text-[13px] text-[var(--muted)]">Cada pista hereda el estilo general; si eliges otro en la pista, manda ese. El texto de una pista se suma (vacía no añade nada). El acompañamiento puede juntar varios instrumentos.</p>
    </div>}
    {remixing && scope === 'sequence' && <p className="text-[13px] text-[var(--muted)]">El estilo de aquí se aplica a todos los pasos: viaja delante del texto de cada paso. El motor no lo recibe solo, sino dentro de cada paso.</p>}
    {remixing && needsStyle && <textarea aria-label="Prompt del remix" value={prompt} disabled={busy} onChange={(event) => setPrompt(event.target.value)} rows={3}
      placeholder={scope === 'sequence' ? SEQUENCE_STYLE_PLACEHOLDER : (activeScope?.placeholder || 'Qué quieres cambiar.')} className={`${field} resize-y w-full`} />}
    {remixing && scope === 'groups' && groups.length > 0 && !needsStyle && <p className="text-[13px] text-[var(--muted)]">Conservar y quitar no usan texto. Pon una pista en transformar para describir el cambio.</p>}
    {remixing && needsStyle && <PromptTools prompt={prompt} setPrompt={setPrompt} prepared={prepared} disabled={busy} />}
    {remixing && scope === 'sequence' && <div className="flex flex-col gap-2">
      <RemixSequence steps={sequenceSteps} onSteps={setSequenceSteps} capabilities={capabilities}
        preview={sequencePreview?.repartitionKey === sequenceRepartitionKey ? sequencePreview.result : null}
        previewReady={sequencePreviewAnswer.ready && sequenceCaptionReady} previewPending={sequencePreviewAnswer.pending}
        prepared={preparedSequenceByIndex} sent={sequenceSentTexts} job={job} busy={busy} />
      {sequencePreviewError && <p role="alert" className="mono text-[11px] st-err">No se pudo calcular la división de la canción: {sequencePreviewError}</p>}
      {sequencePreparationNote && <p role="alert" className="mono text-[11px] st-err">{sequencePreparationNote}</p>}
      {sequencePending && <p role="status" className="mono text-[10px] text-[var(--muted)]">PREPARANDO LOS TEXTOS DE LOS PASOS…</p>}
      {sequenceValidationError && <p role="alert" className="text-[13px] st-err">{sequenceValidationError}</p>}
    </div>}
    {remixing && needsStyle && promptsReady && !requestError && scope !== 'groups' && scope !== 'sequence' && <StyleEnglish request={payload}
      why="Se muestra el texto efectivo del servidor, con la misma petición que se usa al generar. Los parámetros avanzados modifican cómo lo procesa el motor." />}
    {remixing && scope !== 'region' && scope !== 'sequence' && needsCover && range('cover_strength', 'FIDELIDAD AL ORIGINAL')}
    {remixing && scope !== 'sequence' && <label className="flex gap-3 items-center flex-wrap"><span className="label">{scope === 'groups' ? 'BPM COMÚN' : 'BPM'}</span><input aria-label="BPM del remix" type="number" min={bounds('bpm')?.min} max={bounds('bpm')?.max} step="1" value={bpm} disabled={busy} placeholder="Mantener original" onChange={(event) => setBpm(event.target.value)} className={`${field} w-44`} /></label>}
    {remixing && scope === 'sequence' && <div className="flex flex-col gap-2">
      <p className="text-[13px] text-[var(--muted)]">El tempo lo mide el servidor sobre el original: los cortes caen en compases completos. Si la medición no es fiable, indica el BPM original revisado.</p>
      {sourceTempoControls({ label: 'BPM original de la secuencia', uncertain: 'Medición incierta o fuera de límites: indica el BPM original para repartir los pasos.' })}
    </div>}
    {remixing && scope === 'full' && bpm !== '' && <p className="text-[13px] text-[var(--muted)]">{TEMPO_TEXT.full}</p>}
    {remixing && scope === 'region' && <p className="text-[13px] text-[var(--muted)]">{TEMPO_TEXT.region}</p>}
    {remixing && scope === 'groups' && bpm !== '' && <div className="flex flex-col gap-2">
      <p className="text-[13px] text-[var(--muted)]">Todas las pistas cambian de tempo juntas, sin cambiar el tono. Las grabaciones conservadas también se procesan.</p>
      {sourceTempoControls({ label: 'BPM original de las pistas', uncertain: 'Medición incierta o fuera de límites: indica el BPM original para cambiar el tempo.' })}
    </div>}
    {remixing && scope !== 'region' && scope !== 'sequence' && <div className="flex flex-col gap-2" data-remix-duration>
      <div className="flex items-center gap-2 flex-wrap">
        <span className="label">DURACIÓN</span>
        <label className="flex items-center gap-1"><input aria-label="Minutos del remix" type="number" min="0" step="1" value={durationMinutes} disabled={busy} placeholder="min" onChange={(event) => setDurationMinutes(event.target.value)} className={`${field} w-20`} /><span className="text-[12px] text-[var(--muted)]">min</span></label>
        <span aria-hidden="true">:</span>
        <label className="flex items-center gap-1"><input aria-label="Segundos del remix" type="number" min="0" max="59" step="any" value={durationSeconds} disabled={busy} placeholder="seg" onChange={(event) => setDurationSeconds(event.target.value)} className={`${field} w-20`} /><span className="text-[12px] text-[var(--muted)]">s</span></label>
      </div>
      <p className="text-[13px] text-[var(--muted)]">{TEMPO_TEXT.duration}</p>
      {scope === 'groups' && naturalDuration != null && <p className="text-[13px] text-[var(--muted)]" data-remix-minimum-duration>Duración mínima al tempo elegido: {remixMinimumDurationLabel(naturalDuration)}.</p>}
      {scope === 'full' && bpm !== '' && <p className="text-[13px] text-[var(--muted)]">{TEMPO_TEXT.pendingDuration}</p>}
      {hasTargetDuration && <Fold title="RECORTE" why={TEMPO_TEXT.crop}>
        <div className="flex flex-col gap-2 py-2">
          <Waveform key={`repeat:${sourceKind}:${fileName}`} fileName={fileName} sourceKind={sourceKind} onSelection={onRepeatRange} selection={{ start: repeatStart === '' ? 0 : Number(repeatStart) || 0, end: repeatEnd === '' ? null : Number(repeatEnd) }} disabled={busy} nudgeStep={nudgeStep} scales={false} />
          <div className="flex items-center gap-3 flex-wrap">
            <label className="label">DESDE <input aria-label="Inicio del recorte" type="number" min="0" max={duration ?? undefined} step="any" value={repeatStart} disabled={busy} placeholder="Inicio del original" onChange={(event) => setRepeatStart(event.target.value)} className={`${field} w-36`} /> s</label>
            <label className="label">HASTA <input aria-label="Final del recorte" type="number" min="0" max={duration ?? undefined} step="any" value={repeatEnd} disabled={busy} placeholder="Final del original" onChange={(event) => setRepeatEnd(event.target.value)} className={`${field} w-36`} /> s</label>
          </div>
          <p className="text-[13px] text-[var(--muted)]">Los tiempos del recorte se refieren al original. Ese intervalo se repite las veces necesarias hasta alcanzar la duración pedida.</p>
          {bpm !== '' && <p className="text-[13px] text-[var(--muted)]" data-remix-repeat-clock>{TEMPO_TEXT.repetition}</p>}
        </div>
      </Fold>}
    </div>}
    {remixing && requestError && <p role="alert" className="text-[13px] st-err">{requestError}</p>}
    {remixing && analysisStatus && (scope !== 'groups' || groups.length > 0) && <p role="status" className="text-[13px]">{analysisStatus}</p>}
    {remixing && (scope !== 'groups' || groups.length > 0) && <div className="flex gap-3 items-end flex-wrap">
      <label className="flex flex-col gap-1 text-[13px] text-[var(--text)] min-w-[240px] flex-1">Nombre del remix
        <input aria-label="Nombre del remix" value={outputName} disabled={busy} onChange={(event) => setOutputName(event.target.value)}
          placeholder={fileName ? `${fileName.replace(/\.[^.]+$/, '')}-remix` : 'Nombre de las variantes'} className={field} />
      </label>
      <button type="button" onClick={() => void run()} disabled={busy || grooveBusy || !!requestError || !!analysisStatus || !capabilities || (needsStyle && (!promptsReady || (!sentPrompt && scope !== 'sequence')))} className="btn btn-signal h-10 px-5">
      {busy ? <Loader2 size={13} className="animate-spin" /> : <Sparkles size={13} />} {busy ? 'TRABAJANDO…' : 'REMIX'}</button></div>}
    {action === 'voice' && <VoiceBackingPanel fileName={fileName} sourceKind={sourceKind} duration={duration} capabilities={capabilities} busy={busy} onRun={voiceBacking} />}
    {action === 'adjust' && <div className="flex flex-col gap-3">
      <div className="flex gap-2 flex-wrap">
        <button type="button" disabled={busy} onClick={() => void local(() => api.setTempo({ file_name: fileName, source_kind: sourceKind, mode: 'half' }))} className="btn btn-ghost h-8 px-3">MEDIO TIEMPO</button>
        <button type="button" disabled={busy} onClick={() => void local(() => api.setTempo({ file_name: fileName, source_kind: sourceKind, mode: 'double' }))} className="btn btn-ghost h-8 px-3">DOBLE TIEMPO</button>
        <label className="label">BPM <input aria-label="BPM del ajuste" type="number" min={bounds('bpm')?.min} max={bounds('bpm')?.max} value={bpm} disabled={busy} placeholder="Tempo" onChange={(event) => setBpm(event.target.value)} className={`${field} w-24`} /></label>
        <button type="button" disabled={busy || !bpm} onClick={() => void local(() => api.setTempo({ file_name: fileName, source_kind: sourceKind, mode: 'bpm', bpm: Number(bpm) }))} className="btn btn-ghost h-8 px-3">APLICAR BPM</button>
        <button type="button" disabled={busy} onClick={() => void local(() => api.makeLoop({ file_name: fileName, source_kind: sourceKind }))} className="btn btn-ghost h-8 px-3">EXPORTAR LOOP</button>
      </div>
      <RemixPanel fileName={fileName} sourceKind={sourceKind} nudgeStep={nudgeStep} busy={busy} onRun={(params) => local(() => api.remix({ file_name: fileName, source_kind: sourceKind, ...params }))} />
    </div>}
    {busy && <div role="status" aria-live="polite" className="flex items-center gap-3">
      <Loader2 size={14} className="animate-spin shrink-0" aria-hidden="true" />
      <p className="text-[13px]">{busyLine}</p>
      {percent != null && <>
        <progress className="flex-1 min-w-[120px]" max="1" value={ratio} />
        <span className="num text-[13px]">{percent}%</span>
      </>}
      {percent == null && busyLine === CONVERTING && <progress className="flex-1 min-w-[120px]" />}
      {currentJob.current && scope === 'sequence' && <button type="button" onClick={() => void stopSequence()} className="btn btn-signal h-8 px-3">PARAR SECUENCIA</button>}
      {currentJob.current && <button type="button" onClick={() => void cancel()} className="btn btn-ghost h-8 px-3">CANCELAR</button>}
    </div>}
    {(error || (!spoken && job?.error)) && <p role="alert" className="mono text-[11px] st-err flex gap-2 items-center"><AlertTriangle size={13} />{error || job.error}</p>}
    {notice && <p role="status" className="mono text-[10px] text-[var(--muted)]">{notice}</p>}
    {remixing && <Fold title={SECTIONS.advanced.title} why="Timbre, voz, semilla, parámetros del motor y lo detectado en el archivo." onToggle={(event) => setAdvanced(event.currentTarget.open)}>
      <div className="flex flex-col gap-3 border-l border-[var(--line)] pl-3 py-2">
      {needsStyle && <fieldset disabled={busy} className="flex flex-col gap-2 border-0 p-0 min-w-0">
        <legend className="label">PARÁMETROS DEL MOTOR · VACÍO = CONFIGURACIÓN</legend>
        <div className="flex gap-3 flex-wrap">
          <label className="flex flex-col gap-1">
            <span className="label text-[11px]">Guidance scale</span>
            <input aria-label="Guidance del remix" type="number" min={bounds('guidance_scale')?.min} max={bounds('guidance_scale')?.max} step={bounds('guidance_scale')?.step ?? 'any'} value={advancedGuidance} onChange={(e) => setAdvancedGuidance(e.target.value)} className={`${field} w-24`} />
          </label>
          <label className="flex flex-col gap-1">
            <span className="label text-[11px]">Pasos de difusión</span>
            <input aria-label="Pasos del remix" type="number" min={bounds('inference_steps')?.min} max={bounds('inference_steps')?.max} step="1" value={advancedSteps} onChange={(e) => setAdvancedSteps(e.target.value)} className={`${field} w-24`} />
          </label>
          <label className="flex items-end gap-2">
            <input aria-label="Reescribir prompt con LM" type="checkbox" checked={advancedUseFormat} onChange={() => setAdvancedUseFormat((c) => !c)} />
            <span className="label text-[11px]">use_format (LM reescribe el prompt)</span>
          </label>
          {scope !== 'sequence' && <label className="flex flex-col gap-1">
            <span className="label text-[11px]">Lote (batch)</span>
            <input aria-label="Lote del remix" type="number" min={bounds('batch_size')?.min} max={bounds('batch_size')?.max} step="1" value={advancedBatch} onChange={(e) => setAdvancedBatch(e.target.value)} className={`${field} w-24`} />
          </label>}
        </div>
        {scope === 'sequence' && <p className="mono text-[10px] text-[var(--faint)]">Cada paso genera una variante: el lote es 1.</p>}
      </fieldset>}
      <div className="flex items-center gap-3 flex-wrap">
        <label className="label">EL ARCHIVO SUENA A</label>
        <select aria-label="Clasificación del audio original" value={classification} className="desk-select" disabled={busy}
          onChange={(event) => { classificationEdited.current = true; setClassification(event.target.value); setClassificationOrigin('manual'); }}>
          {(analysis?.categories ?? capabilities?.source_classifications ?? capabilities?.source_categories ?? []).map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}
          {!(analysis?.categories ?? capabilities?.source_classifications ?? capabilities?.source_categories)?.length && <option value="unknown">Sin determinar</option>}
        </select>
        <span className="mono text-[10px] text-[var(--faint)]">{classificationOrigin === 'analysis' ? 'Detección del audio' : classificationOrigin === 'manual' ? 'Elección manual' : 'Sin determinar'}</span>
      </div>
      {analysis?.description && <p className="mono text-[10px] text-[var(--faint)]">{analysis.description}</p>}
      {analysisError && <p className="mono text-[10px] st-err">Detección no disponible: {analysisError}</p>}
      {scope !== 'region' && scope !== 'sequence' && needsCover && range('cover_noise_strength', 'VARIACIÓN DEL AUDIO')}
      {needsCover && <label className="flex flex-col gap-1 text-[13px] text-[var(--text)]">Referencia tímbrica <select aria-label="Referencia tímbrica" value={reference} disabled={busy} onChange={(event) => setReference(event.target.value)} className="desk-select">
        <option value="">Sin referencia adicional</option>{references.map((item) => <option key={item.id} value={item.id}>{item.kind === 'upload' ? 'SUBIDA' : 'BIBLIOTECA'} · {item.name}</option>)}</select></label>
      }
      {scope !== 'groups' && <>
        <label className="flex flex-col gap-1 text-[13px] text-[var(--text)]">Voz <select aria-label="Tratamiento de la voz" value={vocalMode} disabled={busy} onChange={(event) => setVocalMode(event.target.value)} className="desk-select">
          <option value="source">Según el original y el prompt</option><option value="instrumental">Instrumental solicitado</option><option value="lyrics">Cantar letra nueva</option></select></label>
        {vocalMode === 'lyrics' && <textarea aria-label="Letra nueva del remix" value={lyrics} disabled={busy} onChange={(event) => setLyrics(event.target.value)} placeholder="Letra nueva" rows={4} className={field} />}
      </>}
      {scope === 'groups' && groups.filter((group) => actions[group.id] !== 'remove').map((group) => <label key={group.id} className="label flex items-center gap-2">VOLUMEN {group.label}
        <input aria-label={`Volumen de ${group.label}`} type="number" min={bounds('gain_db')?.min} max={bounds('gain_db')?.max} step={bounds('gain_db')?.step ?? 'any'} value={gains[group.id] ?? 0} disabled={busy} onChange={(event) => setGains((current) => ({ ...current, [group.id]: Number(event.target.value) }))} className={`${field} w-24`} /> dB</label>)}
      {needsStyle && <label className="label">SEMILLA <input aria-label="Semilla del remix" type="number" min={bounds('seed')?.min} max={bounds('seed')?.max} step="1" value={seed} disabled={busy} onChange={(event) => setSeed(event.target.value)} placeholder="Aleatoria" className={`${field} w-44`} /></label>}
      </div>
    </Fold>}
    {remixing && (!needsStyle || promptsReady) && !requestError && !grooveBusy && (scope !== 'groups' || groups.length > 0) && <EffectivePreview request={payload} loadPreview={api.remixPreview} why={SECTIONS.engine.why} />}
    {remixing && (job?.effective_parameters || job?.result?.metadata || job?.variant_metadata) && <Fold title={SECTIONS.executed.title} why={SECTIONS.executed.why}>
      {scope === 'sequence' && <p className="mono text-[10px] text-[var(--faint)]">Estos son los parámetros del último paso ejecutado: cada paso es una llamada propia al motor.</p>}
      <pre className="mono text-[10px] whitespace-pre-wrap break-words py-2">{JSON.stringify({ effective_parameters: job.effective_parameters,
        material_origin: job.result?.material_origin ?? null,
        steps: job.result?.steps ?? job.steps ?? null,
        variants: (job.result?.metadata ?? job.variant_metadata ?? []).map(({ file_name, seed, seed_origin, timeline, arrangement }) => ({ file_name, seed, seed_origin, timeline, arrangement })),
        provenance: job.provenance, classification: job.result?.source_classification, classification_origin: job.result?.classification_origin,
        source_analysis: job.result?.source_analysis ?? job.source_analysis }, null, 2)}</pre>
      {(job.warnings ?? []).map((warning, index) => <p key={index} className="mono text-[10px] st-warn">{typeof warning === 'string' ? warning : JSON.stringify(warning)}</p>)}
    </Fold>}
    {outputs.length > 0 && <div className="flex flex-col gap-2">
      <p className="text-[13px]">Resultado, al lado del original.</p>
      {materialOriginLabel(job?.result?.material_origin) && <p className="text-[13px] text-[var(--muted)]" data-material-origin>{materialOriginLabel(job?.result?.material_origin)}</p>}
      <AudioComparator tracks={comparisonTracks} interval={scope === 'region' ? region : null} nudgeStep={nudgeStep} />
    </div>}
  </div>;
}
