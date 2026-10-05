import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  Play, Loader2, AlertTriangle, Download, Trash2, Music4, Sparkles,
  Music, Mic2, Dices, Wand2, WandSparkles, Layers, Feather, RotateCcw,
} from 'lucide-react';
import { api, isEnginePollBlip, JOB_POLL_INTERVAL_MS, JOB_POLL_MAX_MISSES } from '../api';
import QualityWizard from './QualityWizard';
import JobsPanel from './JobsPanel';
import SelectBox from './SelectBox';
import {
  VOCAL_GENDER, VOCAL_TIMBRE, VOCAL_STYLE, VOCAL_EMOTION, VOCAL_LANGUAGES,
  buildVocalTags, structureLyric, expandLyric, hasLyricStructure,
} from '../vocal';

const UI = {
  minDuration: 10,
  // Mismos valores que generation en el servidor. La pantalla no abre en 1:00
  // y luego salta: /music/config los confirma al llegar.
  defaultDuration: 120,
  maxDurationFallback: 600,
  step: 5,
  historyKey: 'musica.historial',
  maxHistory: 30,
};

/* Opciones reales que el backend acepta (MusicGenRequest): nada inventado. */
const GENRES = [
  { id: 'techno', tag: 'Techno', style: 'techno oscuro con bombo seco y sintetizadores graves' },
  { id: 'lofi', tag: 'Lo-fi', style: 'lo-fi hip hop relajado con piano suave y vinilo de fondo' },
  { id: 'synthwave', tag: 'Synthwave', style: 'synthwave nocturno con bajo analógico y arpegios retro' },
  { id: 'epic', tag: 'Épica', style: 'música orquestal épica con cuerdas y percusión cinematográfica' },
  { id: 'jazz', tag: 'Jazz', style: 'jazz café smooth con saxofón cálido y contrabajo' },
  { id: 'ambient', tag: 'Ambient', style: 'ambient etéreo con pads largos y texturas espaciales' },
  // Los tres los pide el asistente (QualityWizard): mismos tags para no perderlos.
  { id: 'orquestal', tag: 'Orquestal', style: 'orquestal con cuerdas y percusión' },
  { id: 'acustico', tag: 'Acústico', style: 'acústico con guitarras y folk' },
  { id: 'electronica', tag: 'Electrónica', style: 'electrónica moderna con bajos profundos' },
];

const MOODS = [
  { id: 'nocturno', tag: 'Nocturno', text: 'ambiente nocturno' },
  { id: 'tranquilo', tag: 'Tranquilo', text: 'ritmo tranquilo y relajado' },
  { id: 'energico', tag: 'Enérgico', text: 'energía creciente y ritmo marcado' },
  { id: 'melancolico', tag: 'Melancólico', text: 'melancólico y emotivo' },
  { id: 'cinematico', tag: 'Cinematográfico', text: 'tensión cinematográfica creciente' },
  // Los cuatro los pide el asistente (QualityWizard): mismos tags para no perderlos.
  { id: 'alegre', tag: 'Alegre', text: 'luminoso y optimista' },
  { id: 'epico', tag: 'Épico', text: 'épico y grandioso' },
  { id: 'oscuro', tag: 'Oscuro', text: 'oscuro y tenso' },
  { id: 'chill', tag: 'Chill', text: 'relajado y cálido' },
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

const loadHistory = () => {
  try { return JSON.parse(localStorage.getItem(UI.historyKey) ?? '[]'); }
  catch { return []; }
};

export default function Composer({ initialMode = 'music', engine = { checked: false, ok: false } }) {
  const [mode, setMode] = useState(initialMode);
  const [config, setConfig] = useState(null);
  const [prompt, setPrompt] = useState('');
  const [genre, setGenre] = useState(null);
  const [mood, setMood] = useState(null);
  const [bpm, setBpm] = useState(null);
  const [key, setKey] = useState('');
  const [duration, setDuration] = useState(UI.defaultDuration);
  const [seed, setSeed] = useState(''); // vacío = aleatorio (use_random_seed del config)
  const [songName, setSongName] = useState(''); // nombre del MP3; vacío = pista-sin-nombre
  const [job, setJob] = useState(null);
  const [error, setError] = useState(null);
  const [history, setHistory] = useState(loadHistory);
  const [playing, setPlaying] = useState(null);
  const [wizardOpen, setWizardOpen] = useState(false);
  const [enhancing, setEnhancing] = useState(false);
  const [enhanceInfo, setEnhanceInfo] = useState(null); // {original, enhanced, additions}
  const [lyrics, setLyrics] = useState(''); // letra para el modo canción con voz
  const [vocal, setVocal] = useState({ gender: '', timbre: '', style: '', emotion: '' });
  const [vocalLang, setVocalLang] = useState('es'); // vocal_language que viaja al motor (A3)
  const [writingLyrics, setWritingLyrics] = useState(false);
  const [lyricsWarning, setLyricsWarning] = useState(null);
  const [showLyricPreview, setShowLyricPreview] = useState(false);
  const aliveRef = useRef(true);
  const durationTouched = useRef(false);

  const maxDuration = config?.max_duration_seconds ?? UI.maxDurationFallback;

  useEffect(() => () => { aliveRef.current = false; }, []);

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

  const remember = useCallback((entry) => {
    setHistory((prev) => {
      const next = [{ ...entry, id: `${Date.now()}` }, ...prev].slice(0, UI.maxHistory);
      localStorage.setItem(UI.historyKey, JSON.stringify(next));
      return next;
    });
  }, []);

  /** Compone el prompt final: estilo del género + mood + texto libre + voz. */
  const buildPrompt = () => {
    const parts = [];
    const g = GENRES.find((x) => x.id === genre);
    if (g) parts.push(g.style);
    const m = MOODS.find((x) => x.id === mood);
    if (m) parts.push(m.text);
    const free = prompt.trim();
    if (free) parts.push(free);
    // En modo voz, los descriptores elegidos forman parte del prompt (A3).
    if (mode === 'voice') {
      const voiceTags = buildVocalTags(vocal);
      if (voiceTags) parts.push(voiceTags);
    }
    return parts.join(', ');
  };

  /** Prompt final tal y como se enviará (para la vista de transparencia). */
  const finalPrompt = buildPrompt();

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
    setError(null);
    setLyricsWarning(null);
    setWritingLyrics(true);
    try {
      const seedPrompt = buildPrompt() || prompt.trim() || 'canción con voz cantada';
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
        setEnhanceInfo({
          original: seedPrompt,
          enhanced: data.caption ?? seedPrompt,
          additions: [data.bpm ? `${data.bpm} bpm` : null, data.key_scale, data.vocal_language].filter(Boolean),
        });
      }
    } catch (e) {
      setError(e.message);
    } finally {
      setWritingLyrics(false);
    }
  };

  const pollUntilDone = useCallback(async (jobId, meta) => {
    let misses = 0;
    while (aliveRef.current) {
      await new Promise((r) => setTimeout(r, JOB_POLL_INTERVAL_MS));
      if (!aliveRef.current) return null;
      try {
        const status = await api.musicStatus(jobId);
        misses = 0;
        setJob(status);
        if (status.status === 'succeeded' && status.output_name) {
          setPlaying(api.audioUrl(status.output_name));
          remember({
            title: meta.title.slice(0, 60),
            prompt: meta.prompt,
            duration: status.duration_seconds ?? meta.duration,
            outputName: status.output_name,
            createdAt: new Date().toISOString(),
          });
          return status;
        }
        if (status.status === 'failed') {
          // Un trabajo marcado failed ya terminó. Seguir sondeando lo dejaba
          // girando para siempre cuando el texto del error parecía un corte.
          setError(status.error ?? 'La generación falló en el motor');
          return status;
        }
      } catch (e) {
        if (isEnginePollBlip(e.message)) continue;
        misses += 1;
        const gone = /no encontrada/i.test(e.message ?? '');
        if (gone || misses >= JOB_POLL_MAX_MISSES) {
          setError(e.message);
          setJob({ status: 'failed' });
          return null;
        }
      }
    }
    return null;
  }, [remember]);

  const launchGeneration = async (finalPrompt, seedValue, nameOverride = undefined) => {
    const meta = { prompt: finalPrompt, title: finalPrompt, duration: Number(duration) };
    const conVoz = mode === 'voice';
    const created = await api.generateMusic({
      prompt: finalPrompt,
      instrumental: !conVoz,
      // La letra sin marcas de estructura hace que el motor cante poco (A3).
      lyrics: conVoz ? structureLyric(lyrics.trim()) : null,
      duration_seconds: meta.duration,
      bpm: bpm ?? null,
      key_scale: key || null,
      // vocal_language via explícito: antes viajaba siempre "en" (bug A3).
      language: conVoz ? vocalLang : null,
      seed: seedValue,
      // Nombre elegido por el usuario; vacío = "pista-sin-nombre" numerado.
      output_name: (nameOverride ?? songName).trim() ? (nameOverride ?? songName).trim() : null,
    });
    return { created, meta };
  };

  const generate = async () => {
    setError(null);
    const finalPrompt = buildPrompt();
    if (!finalPrompt) {
      setError('Elige un género o escribe una descripción');
      return;
    }
    if (mode === 'voice' && lyrics.trim().length === 0) {
      setError('Escribe la letra para la canción con voz');
      return;
    }
    setJob({ status: 'queued', progress: '' });
    try {
      const seedValue = seed.trim() === '' ? null : Number(seed);
      const { created, meta } = await launchGeneration(finalPrompt, seedValue);
      aliveRef.current = true;
      void pollUntilDone(created.job_id, meta);
    } catch (e) {
      setError(e.message);
      setJob({ status: 'failed' });
    }
  };

  /** Variaciones A/B. La segunda espera: en esta GPU no caben dos a la vez. */
  const generateVariations = async () => {
    setError(null);
    const finalPrompt = buildPrompt();
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
    try {
      aliveRef.current = true;
      setJob({ status: 'queued', phase: 'Variación A en cola' });
      const first = await launchGeneration(finalPrompt, s1);
      const doneA = await pollUntilDone(first.created.job_id, first.meta);
      if (!aliveRef.current || doneA?.status !== 'succeeded') return;
      setJob({ status: 'queued', phase: 'Variación B en cola' });
      const second = await launchGeneration(finalPrompt, s2);
      await pollUntilDone(second.created.job_id, second.meta);
    } catch (e) {
      setError(e.message);
      setJob({ status: 'failed' });
    }
  };

  const clearHistory = () => {
    localStorage.removeItem(UI.historyKey);
    setHistory([]);
  };

  /** Añade el BPM elegido. No reescribe la frase ni mete el género del desplegable. */
  const enhancePrompt = async () => {
    const base = prompt.trim();
    if (base.length < 3) {
      setError('Escribe el prompt antes de mejorarlo');
      return;
    }
    setError(null);
    setEnhancing(true);
    try {
      const res = await api.enhancePrompt({ prompt: base, bpm: bpm ?? null });
      setPrompt(res.enhanced);
      setEnhanceInfo(res);
    } catch (e) {
      setError(e.message);
    } finally {
      setEnhancing(false);
    }
  };

  /** Aplica la especificación del asistente de calidad a los selectores. */
  const applyWizard = (spec) => {
    setWizardOpen(false);
    setPrompt(spec.prompt);
    if (spec.bpm) setBpm(spec.bpm);
    if (spec.key_scale) setKey(spec.key_scale);
    if (spec.duration) {
      durationTouched.current = true;
      setDuration(Math.min(spec.duration, maxDuration));
    }
    const g = GENRES.find((x) => x.tag === spec.genre);
    if (g) setGenre(g.id);
    const m = MOODS.find((x) => x.tag === spec.mood);
    if (m) setMood(m.id);
  };

  const busy = job?.status === 'queued' || job?.status === 'running';
  const canGenerate = engine.ok && !busy && buildPrompt().length > 1
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

  return (
    <div className="min-h-full w-full flex flex-col xl:flex-row items-start px-6 py-6 gap-8 xl:px-10">
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
          <button onClick={enhancePrompt} disabled={enhancing} className="btn btn-ghost px-4 h-9">
            {enhancing ? <Loader2 size={13} className="animate-spin" /> : <WandSparkles size={13} />} MEJORAR PROMPT
          </button>
          {engine.checked && !engine.ok && (
            <span className="ml-auto label st-err">MOTOR APAGADO</span>
          )}
        </div>

        {/* Una línea de desplegables. Las filas de chips llenaban la ventana. */}
        <div className="flex items-center gap-2 flex-wrap">
          <SelectBox label="GÉNERO" placeholder="AUTO"
            options={GENRES.map(({ id, tag }) => ({ id, label: tag }))}
            value={genre ?? ''} onChange={(id) => setGenre(id || null)} />
          <SelectBox label="MOOD" placeholder="AUTO"
            options={MOODS.map(({ id, tag }) => ({ id, label: tag }))}
            value={mood ?? ''} onChange={(id) => setMood(id || null)} />
          <SelectBox label="BPM" placeholder="AUTO"
            options={BPM_PRESETS.filter((p) => p.value != null).map(({ value, tag }) => ({ id: String(value), label: tag }))}
            value={bpm == null ? '' : String(bpm)} onChange={(id) => setBpm(id ? Number(id) : null)} />
          <SelectBox label="TONO" placeholder="AUTO"
            options={KEYS.filter((k) => k.id).map(({ id, tag }) => ({ id, label: tag }))}
            value={key} onChange={setKey} />
        </div>

        {/* Prompt libre + duración + seed */}
        <div className="flex flex-col gap-3">
          {enhanceInfo && (
            <div className="flex flex-col gap-1 border-l-2 border-[var(--acc-line)] pl-4 py-1">
              <span className="label">PROMPT MEJORADO · AÑADIDO POR LAS REGLAS DE PRODUCCIÓN:</span>
              <span className="mono text-[10px] text-[var(--muted)] leading-relaxed">{enhanceInfo.additions.join(' · ')}</span>
              <button onClick={() => setEnhanceInfo(null)} className="mono text-[9.5px] text-[var(--faint)] hover:text-red-300 self-start">OCULTAR</button>
            </div>
          )}
          <textarea
            value={prompt}
            onChange={(e) => { setPrompt(e.target.value); if (enhanceInfo) setEnhanceInfo(null); }}
            placeholder="…o describe libremente: guitarra española con lluvia de fondo…"
            className="bg-transparent outline-none resize-none text-[17px] leading-relaxed text-zinc-100 placeholder:text-[var(--faint)] min-h-[110px] font-medium border-l-2 border-[var(--line-strong)] pl-5 py-1.5 focus:border-[var(--acc-line)] transition-colors"
          />
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
                  {vocalSummary || 'AUTO · el motor decide la voz'}
                </span>
                <button onClick={() => setShowLyricPreview((s) => !s)} className="btn btn-ghost h-7 px-2.5"
                  title="Ver exactamente lo que recibe el motor: prompt, idioma y letra">
                  {showLyricPreview ? 'OCULTAR DETALLE' : 'VER LO QUE SE ENVÍA'}
                </button>
              </div>

              {showLyricPreview && (
                <div className="flex flex-col gap-1.5 bg-[var(--surface-2)] border border-[var(--line)] p-4">
                  <span className="label">ESTO ES EXACTAMENTE LO QUE RECIBE EL MOTOR</span>
                  <dl className="mono text-[10.5px] text-[var(--muted)] flex flex-col gap-1">
                    <div className="flex gap-2">
                      <dt className="text-[var(--faint)] shrink-0 w-[110px]">DESCRIPCIÓN</dt>
                      <dd className="text-zinc-200">{finalPrompt || '(vacía)'}</dd>
                    </div>
                    <div className="flex gap-2">
                      <dt className="text-[var(--faint)] shrink-0 w-[110px]">IDIOMA VOZ</dt>
                      <dd className="text-zinc-200">{vocalLang}</dd>
                    </div>
                    <div className="flex gap-2">
                      <dt className="text-[var(--faint)] shrink-0 w-[110px]">VOCALES</dt>
                      <dd className="text-zinc-200">{buildVocalTags(vocal) || 'AUTO · el motor elige la voz'}</dd>
                    </div>
                    <div className="flex gap-2">
                      <dt className="text-[var(--faint)] shrink-0 w-[110px]">TIPO</dt>
                      <dd className="text-zinc-200">{lyrics.trim() ? 'CON VOZ · canta la letra' : 'INSTRUMENTAL'}</dd>
                    </div>
                    {lyrics.trim() !== '' && (
                      <div className="flex gap-2">
                        <dt className="text-[var(--faint)] shrink-0 w-[110px]">LETRA</dt>
                        <dd className="text-zinc-200 whitespace-pre-wrap">{structureLyric(lyrics.trim())}</dd>
                      </div>
                    )}
                  </dl>
                </div>
              )}

              <div className="flex flex-col gap-2">
                <div className="flex items-center justify-between gap-4 flex-wrap">
                  <span className="label">LETRA</span>
                  <button onClick={autoWriteLyrics} disabled={writingLyrics}
                    title="Construye la canción a partir de las frases que hayas escrito; el motor intenta ampliarlas"
                    className="btn btn-ghost h-8 px-3">
                    {writingLyrics ? <><Loader2 size={12} className="animate-spin" /> EL MOTOR ESCRIBE (hasta 5 min)…</>
                      : <><Feather size={12} /> ESCRIBIRLA POR MÍ</>}
                  </button>
                </div>

                <textarea
                  value={lyrics}
                  onChange={(e) => { setLyrics(e.target.value); if (lyricsWarning) setLyricsWarning(null); }}
                  placeholder="Con dos frases basta: la canción se construye con ellas. Pulsa ESCRIBIRLA POR MÍ y las convierto en [Verse] y [Chorus]."
                  className="bg-transparent outline-none resize-none text-[15px] leading-relaxed text-zinc-100 placeholder:text-[var(--faint)] min-h-[96px] font-medium border-l-2 border-[var(--acc-line)] pl-5 py-1.5"
                />

                <p className="mono text-[10px] text-[var(--faint)]">
                  {lyricsWarning
                    ? <span className="text-[var(--warn)]">{lyricsWarning}</span>
                    : lyrics.trim() === ''
                      ? 'Sin letra el motor hace un instrumental. Con letra, canta.'
                      : hasLyricStructure(lyrics)
                        ? 'Ya tiene marcas de estructura: se canta tal cual.'
                        : 'Se enviará con [Verse]/[Chorus] añadidos automáticamente.'}
                </p>
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

        {/* Cola de trabajos + comparador A/B */}
        <JobsPanel />

        {/* Estado del job: línea fina, sin caja */}
        {(busy || error || job?.status === 'failed') && (
          <div className="flex flex-col gap-2.5 py-4 border-y border-[var(--line)]">
            <div className="flex items-center gap-4">
              {busy && <div className="eq shrink-0"><span /><span /><span /><span /><span /><span /></div>}
              {job?.status === 'failed' && <AlertTriangle size={16} className="st-err shrink-0" />}
              <span className={`mono text-[11px] tracking-[0.1em] shrink-0 ${statusInfo?.cls ?? ''}`}>{statusInfo?.label}</span>
              {busy && (
                <span className="num text-[15px] shrink-0">
                  {Math.floor((job?.elapsed_seconds ?? 0) / 60)}:{String((job?.elapsed_seconds ?? 0) % 60).padStart(2, '0')}
                </span>
              )}
              {error && <span className="mono text-[10.5px] st-err truncate flex-1">{error}</span>}
              {busy && (
                <div className="steps shrink-0 ml-auto">
                  {[0, 1, 2].map((i) => <span key={i} className={`step ${stepIdx >= i ? 'done' : ''}`} />)}
                  <span className="mono text-[9px] text-[var(--faint)] ml-2">COLA→SÍNTESIS→RENDER</span>
                </div>
              )}
            </div>
            {busy && (
              <div className="flex flex-col gap-2 pl-1">
                {/* Barra con el porcentaje REAL del motor */}
                <div className="vu w-full" style={{ height: 8 }}>
                  <i style={{ width: `${Math.round((job?.progress_ratio ?? 0) * 100)}%` }} />
                </div>
                <p className="text-[13px] text-zinc-300">
                  {job?.phase ?? 'Trabajando en el motor…'}
                  {job?.progress_ratio > 0 && (
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

        {/* Reproductor: protagonista cuando hay resultado */}
        {playing && (
          <div className="flex items-center gap-6 py-5 px-5 border border-[var(--acc-line)] bg-[var(--acc-dim)] fade-up" style={{ borderRadius: 8 }}>
            <div className="w-14 h-14 rounded-[6px] bg-[var(--acc)] flex items-center justify-center shrink-0 shadow-[0_0_20px_rgba(184,255,41,0.4)]">
              <Music4 size={24} className="text-[#0c0f04]" />
            </div>
            <div className="flex-1 min-w-0">
              <p className="mono text-[11px] tracking-[0.14em] text-[var(--acc)] mb-2">TU PISTA ESTÁ LISTA — SE REPRODUCE AQUÍ MISMO</p>
              <audio key={playing} controls autoPlay src={playing} className="player w-full" style={{ height: 44 }} />
            </div>
            <a href={playing} download className="btn btn-signal h-11 px-5 shrink-0"><Download size={14} /> MP3</a>
          </div>
        )}

        {/* Motor caído */}
        {engine.checked && !engine.ok && (
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

      {/* ============ SESIÓN ============ */}
      <aside className="w-full xl:w-[280px] xl:shrink-0 flex flex-col min-h-0 xl:sticky xl:top-0 xl:max-h-[calc(100vh-7rem)]">
        <div className="flex items-center justify-between pb-4 border-b border-[var(--line)]">
          <span className="label">SESIÓN · {history.length}</span>
          {history.length > 0 && (
            <button onClick={clearHistory} className="text-[var(--faint)] hover:text-red-400 transition-colors" title="Vaciar">
              <Trash2 size={12} />
            </button>
          )}
        </div>
        <div className="flex-1 min-h-0 overflow-y-auto py-3 space-y-1">
          {history.length === 0 && (
            <p className="mono text-[10px] text-[var(--faint)] leading-relaxed tracking-wide py-6 text-center">
              SIN PISTAS AÚN.<br />GENERA LA PRIMERA.
            </p>
          )}
          {history.map((item) => {
            const isCurrent = playing === api.audioUrl(item.outputName);
            return (                <button key={item.id} onClick={() => setPlaying(api.audioUrl(item.outputName))}
                  className={`w-full text-left px-4 py-3.5 flex items-center gap-4 transition-colors border-l-2 ${isCurrent ? 'border-[var(--acc)] bg-[var(--acc-dim)]' : 'border-transparent hover:border-[var(--line-strong)] hover:bg-[var(--surface-2)]'}`}>
                <span className="min-w-0 flex-1">
                  <span className="block text-[13.5px] font-semibold truncate text-zinc-200">{item.title}</span>
                  <span className="block mono text-[11px] text-[var(--faint)] mt-1">{fmt(item.duration)} · {new Date(item.createdAt).toLocaleDateString()}</span>
                </span>
                {isCurrent ? <div className="eq scale-[.4] -m-1.5 shrink-0"><span /><span /><span /><span /><span /><span /></div>
                  : <Play size={10} className="text-[var(--faint)] shrink-0" fill="currentColor" />}
              </button>
            );
          })}
        </div>
      </aside>
    </div>
  );
}
