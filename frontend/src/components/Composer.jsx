import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  Play, Loader2, AlertTriangle, Sparkles,
  Music, Mic2, Dices, Wand2, Layers, Feather, RotateCcw,
} from 'lucide-react';
import { api, actionError, isEnginePollBlip, isTransportBlip, JOB_POLL_INTERVAL_MS, JOB_POLL_MAX_MISSES, TRANSPORT_ERROR_CLEAR_MS } from '../api';
import QualityWizard from './QualityWizard';
import SelectBox from './SelectBox';
import PromptTools from './PromptTools';
import useStylePrompt from '../useStylePrompt';
import EffectivePreview from './EffectivePreview';
import StyleEnglish from './StyleEnglish';
import {
  VOCAL_GENDER, VOCAL_TIMBRE, VOCAL_STYLE, VOCAL_EMOTION, VOCAL_LANGUAGES,
  buildVocalTags, structureLyric, expandLyric, hasLyricStructure,
} from '../vocal';
import { CONVERT_PHASES, deskPhase } from '../desk_phase';
import { glossPrompt } from '../prompt_gloss';
import { ensureModelTerm } from '../glossary_pick';
import { moodClauses, moodTooltip } from '../mood_clauses';
import { CATALOG_GENRES, findGenre } from '../genres';
import { canAttemptEngineOperation, generationWaitMessage } from '../engine_generation';

const UI = {
  minDuration: 10,
  // Mismos valores que generation en el servidor. La pantalla no abre en 1:00
  // y luego salta: /music/config los confirma al llegar.
  defaultDuration: 120,
  maxDurationFallback: 600,
  step: 5,
};

/* Estilos disponibles en el catálogo Musicia. */
const GENRES = CATALOG_GENRES;

const MOODS = [
  { id: 'nocturno', tag: 'Nocturno', text: 'nocturno y oscuro' },
  { id: 'tranquilo', tag: 'Tranquilo', text: 'tranquilo y relajado, tempo lento' },
  { id: 'energico', tag: 'Enérgico', text: 'enérgico y potente, driving e imparable' },
  { id: 'melancolico', tag: 'Melancólico', text: 'melancólico y emotivo' },
  { id: 'cinematico', tag: 'Cinematográfico', text: 'cinematográfico, épico, con capas' },
  // Los cuatro los pide el asistente (QualityWizard): mismos tags para no perderlos.
  { id: 'alegre', tag: 'Alegre', text: 'luminoso y optimista, brillante' },
  { id: 'epico', tag: 'Épico', text: 'épico y grandioso, como un himno' },
  { id: 'oscuro', tag: 'Oscuro', text: 'oscuro y tenso' },
  { id: 'chill', tag: 'Chill', text: 'chill relajado y cálido' },
];

const BPM_PRESETS = [
  { id: 'auto', value: null, tag: 'Auto' },
  { id: '70', value: 70, tag: '70' },
  { id: '90', value: 90, tag: '90' },
  { id: '100', value: 100, tag: '100' },
  { id: '110', value: 110, tag: '110' },
  { id: '128', value: 128, tag: '128' },
  { id: '140', value: 140, tag: '140' },
];

const KEYS = [
  { id: '', tag: 'Auto' },
  { id: 'C major', tag: 'Do M' },
  { id: 'A minor', tag: 'La m' },
  { id: 'D minor', tag: 'Re m' },
  { id: 'E minor', tag: 'Mi m' },
  { id: 'F major', tag: 'Fa M' },
  { id: 'G major', tag: 'Sol M' },
];

const TIME_SIGNATURES = [
  { id: '', tag: 'Auto' },
  { id: '4/4', tag: '4/4' },
  { id: '3/4', tag: '3/4' },
  { id: '6/8', tag: '6/8' },
];

const MODES = [
  { id: 'music', label: 'MÚSICA', icon: Music },
  { id: 'voice', label: 'CANCIÓN CON VOZ', icon: Mic2 },
];

const STATUS = {
  queued: { label: 'EN COLA', cls: 'text-[var(--warn)]' },
  running: { label: 'CREANDO', cls: 'text-[var(--acc)]' },
  succeeded: { label: 'LISTA', cls: 'st-ok' },
  failed: { label: 'ERROR', cls: 'st-err' },
};

const fmt = (s) => `${Math.floor(s / 60)}:${String(Math.round(s % 60)).padStart(2, '0')}`;

export default function Composer({ initialMode = 'music', engine = { checked: false, ok: false } }) {
  const [mode, setMode] = useState(initialMode);
  const [config, setConfig] = useState(null);
  const [prompt, setPrompt] = useState('');
  const [mood, setMood] = useState(null);
  const [bpm, setBpm] = useState(null);
  const [key, setKey] = useState('');
  const [timeSig, setTimeSig] = useState('');
  const [duration, setDuration] = useState(UI.defaultDuration);
  const [seed, setSeed] = useState(''); // vacío = aleatorio (use_random_seed del config)
  const [songName, setSongName] = useState(''); // nombre del MP3; vacío = pista-sin-nombre
  const [job, setJob] = useState(null);
  const [error, setError] = useState(null);
  const [savedName, setSavedName] = useState(null);
  const [cancelling, setCancelling] = useState(false);
  const [wizardOpen, setWizardOpen] = useState(false);
  const [lyrics, setLyrics] = useState(''); // letra para el modo canción con voz
  const [vocal, setVocal] = useState({ gender: '', timbre: '', style: '', emotion: '' });
  const [vocalLang, setVocalLang] = useState('es'); // vocal_language que viaja al motor (A3)
  const [writingLyrics, setWritingLyrics] = useState(false);
  const [lyricsWarning, setLyricsWarning] = useState(null);
  const aliveRef = useRef(true);
  const durationTouched = useRef(false);

  const maxDuration = config?.max_duration_seconds ?? UI.maxDurationFallback;

  useEffect(() => () => { aliveRef.current = false; }, []);

  const onSelectGenre = (id) => {
    const item = findGenre(id);
    prepared.setSelection((current) => ({ ...current, main_style: item?.genre || null,
      influence_styles: current.influence_styles.filter((term) => term !== item?.genre) }));
    if (item?.bpm && (bpm == null || bpm === '')) setBpm(item.bpm);
  };

  useEffect(() => {
    let active = true;
    (async () => {
      const cfg = await api.musicConfig().catch(() => null);
      if (!active || !cfg) return;
      setConfig(cfg);
      const preset = Number(cfg.duration_seconds);
      const cap = Number(cfg.max_duration_seconds);
      if (preset > 0 && !durationTouched.current) {
        setDuration(cap > 0 ? Math.min(preset, cap) : preset);
      }
    })();
    return () => { active = false; };
  }, []);

  /** Lo que se envía es el cuadro más el ánimo elegido, en una sola caption.
      Tranquilo y Chill no meten el tempo si el BPM ya está en su control. */
  const buildDetails = () => {
    let free = prompt.trim();
    // En modo voz, cada descriptor elegido es vocabulario del modelo y entra
    // en la misma caption. No se cuelga una segunda frase.
    if (mode === 'voice') {
      for (const tag of buildVocalTags(vocal).split(',').map((item) => item.trim()).filter(Boolean)) {
        free = ensureModelTerm(free, tag);
      }
    }
    for (const clause of moodClauses(mood, bpm)) {
      free = ensureModelTerm(free, clause);
    }
    return glossPrompt(free);
  };

  /** Prompt final tal y como se enviará (para la vista de transparencia). */
  const prepared = useStylePrompt(buildDetails());
  const finalPrompt = prepared.effectivePrompt;

  /** "Escribir la letra por mí": el LM local propone un borrador editable. */
  /** Quita todas las elecciones de voz y vuelve a AUTO. */
  const resetVocal = () => {
    setVocal({ gender: '', timbre: '', style: '', emotion: '' });
    setVocalLang('es');
  };

  /** Resumen legible de lo elegido (siempre visible, sin abrir desplegables).
      El idioma no cuenta: siempre hay uno ('es'), y si contara nunca se vería AUTO. */
  const vocalSummary = [
    [VOCAL_GENDER, vocal.gender], [VOCAL_TIMBRE, vocal.timbre],
    [VOCAL_STYLE, vocal.style], [VOCAL_EMOTION, vocal.emotion],
  ]
    .map(([list, id]) => list.find((o) => o.id === id)?.label)
    .filter(Boolean)
    .join(' · ');

  const autoWriteLyrics = async () => {
    if (!prepared.ready) { setError(prepared.error || 'Espera a que termine la preparación del prompt.'); return; }
    setError(null);
    setLyricsWarning(null);
    setWritingLyrics(true);
    try {
      const seedPrompt = finalPrompt || prompt.trim() || 'canción con voz cantada';
      const data = await api.writeLyrics({
        prompt: seedPrompt,
        lyrics: lyrics.trim(),
        language: vocalLang,
        duration_seconds: Number(duration),
        bpm: bpm ?? null,
        key_scale: key || null,
      });
      if (data.source === 'tus_frases' || (data.warning && !lyrics.trim())) {
        // El motor no compone: si el usuario escribió frases, se construyen
        // con ellas. Si no escribió nada, solo se avisa (nunca inventamos).
        if (data.source === 'tus_frases') {
          setLyrics(expandLyric(lyrics.trim()));
          setLyricsWarning(data.warning);
        } else {
          setLyricsWarning(data.warning);
        }
      } else {
        setLyrics(structureLyric(data.lyrics || ''));
        setLyricsWarning(data.warning ?? null);

      }
    } catch (e) {
      setError(actionError(e.message));
    } finally {
      setWritingLyrics(false);
    }
  };

  const pollUntilDone = useCallback(async (jobId) => {
    let misses = 0;
    while (aliveRef.current) {
      await new Promise((r) => setTimeout(r, JOB_POLL_INTERVAL_MS));
      if (!aliveRef.current) return null;
      try {
        const status = await api.musicStatus(jobId);
        misses = 0;
        setJob(status);
        if (status.status === 'succeeded' && status.output_name) {
          setSavedName(status.output_name);
          return status;
        }
        if (status.status === 'failed') {
          setError(status.error ?? 'La generación falló en el motor');
          return status;
        }
      } catch (e) {
        // Corte de cliente: la API puede haberse reiniciado. Intenta encontrar
        // el trabajo en la cola antes de rendirse.
        if (isTransportBlip(e.message)) {
          try {
            const found = await api.findJob(jobId);
            if (found) {
              if (found.status === 'failed' &&
                  /Interrumpido|reinici/i.test(found.error ?? '')) {
                const msg = 'La API se reinició y se perdió el trabajo en curso. Vuelve a intentar el remix.';
                setError(msg);
                setJob({ status: 'failed', error: msg });
                return null;
              }
              // El trabajo sigue ahí: reanuda el sondeo.
              misses = 0;
              setJob(found);
              if (found.status === 'succeeded' && found.output_name) {
                setSavedName(found.output_name);
                return found;
              }
              if (found.status === 'failed') {
                setError(found.error ?? 'La generación falló en el motor');
                return found;
              }
              continue;
            }
            // findJob no devolvió nada: la cola se vació al reiniciar la API.
            const msg = 'La API se reinició y el trabajo se perdió. Vuelve a intentar el remix.';
            setError(msg);
            setJob({ status: 'failed', error: msg });
            return null;
          } catch {
            // Si ni siquiera se puede listar la cola, la API sigue caída.
          }
        }
        if (isEnginePollBlip(e.message)) continue;
        misses += 1;
        const gone = /no encontrada/i.test(e.message ?? '');
        if (gone || misses >= JOB_POLL_MAX_MISSES) {
          const message = actionError(e.message);
          if (message) {
            setError(message);
            setJob({ status: 'failed' });
          }
          return null;
        }
      }
    }
    return null;
  }, []);

  const generationRequest = (caption, seedValue, nameOverride = undefined) => {
    const conVoz = mode === 'voice';
    return {
      prompt: caption,
      instrumental: !conVoz,
      // La estructura se añade solo con la acción explícita ESTRUCTURAR LETRA.
      lyrics: conVoz ? lyrics.trim() : null,
      duration_seconds: Number(duration),
      bpm: bpm ?? null,
      key_scale: key || null,
      time_signature: timeSig || null,
      // vocal_language via explícito: antes viajaba siempre "en" (bug A3).
      language: conVoz ? vocalLang : null,
      seed: seedValue,
      // Nombre elegido por el usuario; vacío = "pista-sin-nombre" numerado.
      output_name: (nameOverride ?? songName).trim() ? (nameOverride ?? songName).trim() : null,
    };
  };

  const launchGeneration = async (caption, seedValue, nameOverride = undefined) => {
    const request = generationRequest(caption, seedValue, nameOverride);
    // Rechaza conflictos antes de crear el trabajo o ocupar la GPU.
    await api.generationPreview(request);
    const created = await api.generateMusic(request);
    return { created };
  };

  const generate = async () => {
    setError(null);
    if (!prepared.ready) { setError(prepared.error || 'Espera a que termine la preparación del prompt.'); return; }
    if (!finalPrompt) {
      setError('Elige un género o escribe una descripción');
      return;
    }
    if (mode === 'voice' && lyrics.trim().length === 0) {
      setError('Escribe la letra para la canción con voz');
      return;
    }
    setSavedName(null);
    setJob({ status: 'queued', progress: '' });
    const seedValue = seed.trim() === '' ? null : Number(seed);
    while (aliveRef.current) {
      try {
        const { created } = await launchGeneration(finalPrompt, seedValue);
        if (!aliveRef.current) return;
        setJob({ status: 'queued', progress: '', job_id: created.job_id });
        void pollUntilDone(created.job_id);
        return;
      } catch (e) {
        if (!isTransportBlip(e.message)) {
          setError(actionError(e.message));
          setJob({ status: 'failed' });
          return;
        }
        await new Promise((resolve) => setTimeout(resolve, TRANSPORT_ERROR_CLEAR_MS));
      }
    }
  };

  /** Variaciones A/B. La segunda espera: en esta GPU no caben dos a la vez. */
  const generateVariations = async () => {
    setError(null);
    if (!prepared.ready) { setError(prepared.error || 'Espera a que termine la preparación del prompt.'); return; }
    if (!finalPrompt) {
      setError('Elige un género o escribe una descripción');
      return;
    }
    if (mode === 'voice' && lyrics.trim().length === 0) {
      setError('Escribe la letra para la canción con voz');
      return;
    }
    const s1 = Math.floor(Math.random() * 1_000_000);
    let s2 = Math.floor(Math.random() * 1_000_000);
    if (s2 === s1) s2 = (s1 + 1) % 1_000_000;
    setSavedName(null);
    const launchWhenBack = async (seedValue, phase) => {
      while (aliveRef.current) {
        try {
          setJob({ status: 'queued', phase });
          const created = await launchGeneration(finalPrompt, seedValue);
          if (!aliveRef.current) return null;
          setJob({ status: 'queued', phase, job_id: created.created.job_id });
          return created;
        } catch (e) {
          if (!isTransportBlip(e.message)) throw e;
          await new Promise((resolve) => setTimeout(resolve, TRANSPORT_ERROR_CLEAR_MS));
        }
      }
      return null;
    };
    try {
      const first = await launchWhenBack(s1, 'Variación A en cola');
      if (!first) return;
      const doneA = await pollUntilDone(first.created.job_id);
      if (!aliveRef.current || doneA?.status !== 'succeeded') return;
      const second = await launchWhenBack(s2, 'Variación B en cola');
      if (!second) return;
      await pollUntilDone(second.created.job_id);
    } catch (e) {
      const message = actionError(e.message);
      if (message) {
        setError(message);
        setJob({ status: 'failed' });
      }
    }
  };

  /** Aplica la especificación del asistente de calidad a los selectores. */
  const applyWizard = (spec) => {
    setWizardOpen(false);
    const elegido = findGenre(spec.genre);
    if (elegido) prepared.setSelection((current) => ({ ...current, main_style: elegido.genre, influence_styles: current.influence_styles.filter((term) => term !== elegido.genre) }));
    if (spec.bpm) setBpm(spec.bpm);
    if (spec.key_scale) setKey(spec.key_scale);
    if (spec.duration) {
      durationTouched.current = true;
      setDuration(Math.min(spec.duration, maxDuration));
    }
    const m = MOODS.find((x) => x.tag === spec.mood || x.id === spec.mood);
    if (m) setMood(m.id);
  };

  const stopGeneration = async () => {
    if (!job?.job_id || cancelling) return;
    setCancelling(true);
    try {
      await api.cancelJob(job.job_id);
    } catch (e) {
      setError(actionError(e.message));
    } finally {
      setCancelling(false);
    }
  };

  const busy = job?.status === 'queued' || job?.status === 'running';
  const canGenerate = canAttemptEngineOperation(engine) && !busy && prepared.ready && finalPrompt.length > 1
    && (mode === 'music' || lyrics.trim().length > 0);
  const statusInfo = job ? STATUS[job.status] : null;
  const stepIdx = busy ? (job?.status === 'running' ? 1 : 0) : (job?.status === 'succeeded' ? 3 : -1);

  /** Reloj en vivo: el contador corre cada segundo entre polls. */
  useEffect(() => {
    if (!busy) return undefined;
    const t = setInterval(() => {
      setJob((cur) => (cur ? { ...cur, elapsed_seconds: (cur.elapsed_seconds ?? 0) + 1 } : cur));
    }, 1000);
    return () => clearInterval(t);
  }, [busy]);

  const createConverting = CONVERT_PHASES.includes(deskPhase(job?.phase, ''));

  return (
    <div className="min-h-full w-full flex flex-col px-6 py-6 gap-6 xl:px-10">
      {/* ============ CONSOLA ============ */}
      <section className="flex-1 min-w-0 flex flex-col gap-6">
        {/* Modo: música / voz + asistente de calidad */}
        <div className="flex items-center gap-2 flex-wrap">
          {MODES.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              onClick={() => setMode(id)}
              className={`btn px-4 h-9 btn-ghost ${mode === id ? '!border-[var(--acc-line)] !text-[var(--text)]' : ''}`}
            >
              <Icon size={14} /> {label}
            </button>
          ))}
          <button onClick={() => setWizardOpen(true)} className="btn btn-ghost px-4 h-9">
            <Wand2 size={13} /> ASISTENTE
          </button>
          {engine.checked && !engine.ok && (
            <span className={`ml-auto label ${engine.idle || engine.starting || engine.stopping ? 'text-[var(--muted)]' : 'st-err'}`}>
              {engine.idle
                ? 'MOTOR EN REPOSO · SE INICIARÁ AL GENERAR'
                : engine.stopping
                  ? 'DETENIENDO EL MOTOR · ESPERA'
                  : engine.starting
                  ? 'CONECTANDO CON EL MODELO · ESPERA'
                  : engine.error
                    ? 'ERROR DEL MOTOR · GENERAR PARA REINTENTAR'
                    : 'MOTOR APAGADO'}
            </span>
          )}
        </div>

        {/* Una línea de desplegables. Las filas de chips llenaban la ventana. */}
        <div className="flex items-center gap-2 flex-wrap">
          <SelectBox label="PRINCIPAL" placeholder="SIN ELEGIR"
            options={GENRES.map(({ id, label }) => ({ id, label }))}
            value={GENRES.find((item) => item.genre === prepared.selection.main_style)?.id ?? ''} onChange={onSelectGenre} />
          <SelectBox label="MOOD" placeholder="AUTO"
            options={MOODS.map(({ id, tag }) => ({ id, label: tag, title: moodTooltip(id) }))}
            value={mood ?? ''} onChange={(id) => setMood(id || null)} />
          <SelectBox label="BPM" placeholder="AUTO"
            options={BPM_PRESETS.filter((p) => p.value != null).map(({ value, tag }) => ({ id: String(value), label: tag }))}
            value={bpm == null ? '' : String(bpm)} onChange={(id) => setBpm(id ? Number(id) : null)} />
          <SelectBox label="TONO" placeholder="AUTO"
            options={KEYS.filter((k) => k.id).map(({ id, tag }) => ({ id, label: tag }))}
            value={key} onChange={setKey} />
          <SelectBox label="COMPÁS" placeholder="AUTO"
            options={TIME_SIGNATURES.filter((t) => t.id).map(({ id, tag }) => ({ id, label: tag }))}
            value={timeSig} onChange={setTimeSig} />
        </div>

        {/* Prompt libre + duración + seed */}
        <div className="flex flex-col gap-3">
          <textarea
            aria-label="Prompt de crear"
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            placeholder="Tus detalles y restricciones. Elige el principal y los matices en sus controles."
            className="bg-transparent outline-none resize-none text-[17px] leading-relaxed text-zinc-100 placeholder:text-[var(--faint)] min-h-[110px] font-medium border-l-2 border-[var(--line-strong)] pl-5 py-1.5 focus:border-[var(--acc-line)] transition-colors"
          />
          <PromptTools prompt={prompt} setPrompt={setPrompt} prepared={prepared} disabled={busy} />
          {prepared.ready && <StyleEnglish text={finalPrompt} />}
          {prepared.ready && <EffectivePreview request={generationRequest(finalPrompt, seed.trim() === '' ? null : Number(seed))} loadPreview={api.generationPreview} title="VER LO QUE SE ENVÍA" />}
          {mode === 'voice' && (
            <div className="flex flex-col gap-3 border border-[var(--line)] p-5">
              {/* Una sola línea con todo el control de voz; cada grupo se despliega al pulsar. */}
              <div className="flex items-center gap-2 flex-wrap">
                <span className="label shrink-0">VOZ CANTADA</span>
                <SelectBox label="VOZ" options={VOCAL_GENDER} value={vocal.gender}
                  onChange={(v) => setVocal({ ...vocal, gender: v })} />
                <SelectBox label="TIMBRE" options={VOCAL_TIMBRE} value={vocal.timbre}
                  onChange={(v) => setVocal({ ...vocal, timbre: v })} />
                <SelectBox label="CANTADO" options={VOCAL_STYLE} value={vocal.style}
                  onChange={(v) => setVocal({ ...vocal, style: v })} />
                <SelectBox label="EMOCIÓN" options={VOCAL_EMOTION} value={vocal.emotion}
                  onChange={(v) => setVocal({ ...vocal, emotion: v })} />
                <SelectBox label="IDIOMA" options={VOCAL_LANGUAGES} value={vocalLang}
                  onChange={setVocalLang} />
                <button onClick={resetVocal} className="btn btn-ghost h-8 px-2.5"
                  title="Quitar todas las elecciones de voz">
                  <RotateCcw size={12} />
                </button>
              </div>

              {/* Resumen: siempre se ve qué has elegido (sin abrir nada). */}
              <div className="flex items-center gap-3 flex-wrap">
                <span className="label shrink-0">ELIGIDO</span>
                <span className={`mono text-[11px] ${vocalSummary ? 'text-[var(--acc)]' : 'text-[var(--faint)]'}`}>
                  {vocalSummary || 'AUTO'}
                </span>
              </div>

              <div className="flex flex-col gap-2">
                <div className="flex items-center justify-between gap-4 flex-wrap">
                  <span className="label">LETRA</span>
                  <button onClick={() => setLyrics(structureLyric(lyrics))} disabled={!lyrics.trim() || hasLyricStructure(lyrics)}
                    className="btn btn-ghost h-8 px-3" title="Añadir [Intro], [Verse], [Chorus] y [Outro] a tu letra">
                    ESTRUCTURAR LETRA
                  </button>
                  <button onClick={autoWriteLyrics} disabled={writingLyrics || !prepared.ready}
                    title="Construye la canción a partir de las frases que hayas escrito; el motor intenta ampliarlas"
                    className="btn btn-ghost h-8 px-3">
                    {writingLyrics ? <><Loader2 size={12} className="animate-spin" /> ESPERANDO AL MODELO (hasta 11 min)…</>
                      : <><Feather size={12} /> ESCRIBIRLA POR MÍ</>}
                  </button>
                </div>

                <textarea
                  value={lyrics}
                  onChange={(e) => { setLyrics(e.target.value); if (lyricsWarning) setLyricsWarning(null); }}
                  placeholder="Letra que se canta. ESTRUCTURAR LETRA añade marcas si lo eliges."
                  className="bg-transparent outline-none resize-none text-[15px] leading-relaxed text-zinc-100 placeholder:text-[var(--faint)] min-h-[96px] font-medium border-l-2 border-[var(--acc-line)] pl-5 py-1.5"
                />

                {lyricsWarning && <p className="mono text-[10px] text-[var(--warn)]">{lyricsWarning}</p>}
              </div>
            </div>
          )}
          <div className="flex items-center gap-4 flex-wrap">
            <span className="label shrink-0">NOMBRE DE LA CANCIÓN</span>
            <input type="text" value={songName} onChange={(e) => setSongName(e.target.value)}
              placeholder="sin nombre (se guardará como pista-sin-nombre)"
              className="flex-1 min-w-[260px] px-4 py-3 text-[15px] font-semibold bg-transparent outline-none border border-[var(--line-strong)] focus:border-[var(--acc-line)] transition-colors" />
          </div>
          <div className="flex items-center gap-4 flex-wrap">
            <div className="flex items-center gap-3 flex-1 min-w-0">
              <span className="label shrink-0">DURACIÓN</span>
              <input type="range" min={UI.minDuration} max={maxDuration} step={UI.step}
                value={duration} onChange={(e) => { durationTouched.current = true; setDuration(Number(e.target.value)); }}
                className="flex-1 min-w-0" aria-label="Duración" />
              <span className="num min-w-[4.5rem] text-right">{fmt(duration)}</span>
            </div>
            <div className="flex items-center gap-2.5 shrink-0">
              <span className="label">SEMILLA</span>
              <input type="text" value={seed}
                onChange={(e) => setSeed(e.target.value.replace(/[^0-9]/g, ''))}
                placeholder="auto" className="w-24 px-3 py-2 text-center text-[13px]" />
              <button onClick={() => setSeed(String(Math.floor(Math.random() * 1e6)))}
                className="btn btn-ghost h-11 w-11 p-0" title="Semilla aleatoria">
                <Dices size={16} />
              </button>
            </div>
            <button onClick={generate} disabled={!canGenerate} className="btn btn-signal px-9 h-12 shrink-0 text-[14px]">
              {busy ? <><Loader2 size={14} className="animate-spin" /> CREANDO…</>
                : <><Play size={13} fill="currentColor" /> GENERAR</>}
            </button>
            <button onClick={generateVariations} disabled={!canGenerate} title="Misma idea, dos semillas. La segunda empieza cuando termina la primera."
              className="btn btn-ghost px-4 h-10 shrink-0">
              <Layers size={13} /> VARIAR
            </button>
          </div>
        </div>

        {/* Estado del job: línea fina, sin caja */}
        {(busy || error || job?.status === 'failed') && (
          <div className="flex flex-col gap-2.5 py-4 border-y border-[var(--line)]">
            <div className="flex items-center gap-4">
              {busy && (generationWaitMessage(job, engine)
                ? <Loader2 size={14} className="shrink-0 text-[var(--acc)] animate-spin" aria-label="Esperando conexión con el motor" />
                : <div className="eq shrink-0"><span /><span /><span /><span /><span /><span /></div>)}
              {job?.status === 'failed' && <AlertTriangle size={16} className="st-err shrink-0" />}
              <span className={`mono text-[11px] tracking-[0.1em] shrink-0 ${statusInfo?.cls ?? ''}`}>{statusInfo?.label}</span>
              {busy && (
                <span className="num text-[15px] shrink-0">
                  {fmt(Math.floor(job?.elapsed_seconds ?? 0))}
                </span>
              )}
              {error && <span className="mono text-[10.5px] st-err truncate flex-1">{error}</span>}
              {busy && (
                <div className="steps shrink-0 ml-auto">
                  {[0, 1, 2].map((i) => <span key={i} className={`step ${stepIdx >= i ? 'done' : ''}`} />)}
                  <span className="mono text-[9px] text-[var(--faint)] ml-2">COLA→SÍNTESIS→RENDER</span>
                </div>
              )}
              {busy && job?.job_id && (
                <button type="button" onClick={() => void stopGeneration()} disabled={cancelling}
                  title="Para esta generación. Si el motor estaba trabajando se reinicia (recargar el modelo tarda minutos)."
                  className="mono text-[9px] px-1.5 py-0.5 shrink-0 border border-[var(--line)] text-[var(--faint)] hover:!border-[rgba(255,92,92,0.5)] hover:!text-red-300">
                  {cancelling ? 'PARANDO…' : 'PARAR'}
                </button>
              )}
            </div>
            {busy && (
              <div className="flex flex-col gap-2 pl-1">
                {createConverting
                  ? <progress className="w-full" />
                  : <div className="vu w-full" style={{ height: 8 }}>
                    <i style={{ width: `${Math.round((Number(job?.progress_ratio) || 0) * 100)}%` }} />
                  </div>}
                <p className="text-[13px] text-zinc-300">
                  {generationWaitMessage(job, engine) ?? job?.phase ?? 'Trabajando en el motor…'}
                  {!createConverting && job?.progress_ratio > 0 && (
                    <span className="num ml-3">{Math.round(job.progress_ratio * 100)}%</span>
                  )}
                </p>
                <p className="mono text-[10px] text-[var(--faint)] leading-relaxed">
                  Normalmente tarda 1-3 min con el modelo cargado (la primera vez, 5-6 min: descarga y carga del modelo).
                </p>
                {job?.events?.length > 0 && (
                  <div className="mono text-[9.5px] text-[var(--faint)] leading-relaxed">
                    {job.events.slice(-3).map((ev, i, arr) => (
                      <p key={`${ev.t}-${i}`} className={i === arr.length - 1 ? 'text-[var(--muted)]' : ''}>
                        +{Math.floor(ev.t / 60)}:{String(Math.round(ev.t % 60)).padStart(2, '0')} · {ev.text}
                      </p>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {savedName && !busy && (
          <p className="mono text-[11px] tracking-[0.12em] text-[var(--acc)]">Lista. Está en BIBLIOTECA.</p>
        )}

        {/* Motor caído */}
        {engine.checked && !engine.ok && !engine.idle && !engine.starting && !engine.stopping && (
          <div className="flex items-start gap-3 py-4 border-y border-[rgba(255,92,92,0.35)]">
            <AlertTriangle size={16} className="st-err mt-0.5 shrink-0" />
            <div>
              <p className="text-[13px] font-bold text-red-300">Motor local no activo</p>
              <p className="text-[12.5px] text-[var(--muted)] mt-1 leading-relaxed">
                Ejecuta <code className="mono text-[var(--acc)] text-[11.5px]">scripts\open_musicia.ps1</code> para arrancar todo.
              </p>
            </div>
          </div>
        )}

      </section>

      {wizardOpen && (
        <QualityWizard onClose={() => setWizardOpen(false)} onApply={applyWizard} />
      )}
    </div>
  );
}
