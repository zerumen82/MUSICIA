import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  Play, Loader2, AlertTriangle, Download, Trash2, Music4, Sparkles,
  Music, Mic2, Dices, Wand2, WandSparkles, Layers, Feather, ChevronDown, RotateCcw,
} from 'lucide-react';
import { api, JOB_POLL_INTERVAL_MS } from '../api';
import QualityWizard from './QualityWizard';
import JobsPanel from './JobsPanel';
import {
  VOCAL_GENDER, VOCAL_TIMBRE, VOCAL_STYLE, VOCAL_EMOTION, VOCAL_LANGUAGES,
  buildVocalTags, structureLyric, hasLyricStructure,
} from '../vocal';

const UI = {
  minDuration: 10,
  maxDurationFallback: 240,
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
];

const MOODS = [
  { id: 'nocturno', tag: 'Nocturno', text: 'ambiente nocturno' },
  { id: 'tranquilo', tag: 'Tranquilo', text: 'ritmo tranquilo y relajado' },
  { id: 'energico', tag: 'Enérgico', text: 'energía creciente y ritmo marcado' },
  { id: 'melancolico', tag: 'Melancólico', text: 'melancólico y emotivo' },
  { id: 'cinematico', tag: 'Cinematográfico', text: 'tensión cinematográfica creciente' },
];

const BPM_PRESETS = [
  { id: 'auto', value: null, tag: 'Auto' },
  { id: '70', value: 70, tag: '70' },
  { id: '90', value: 90, tag: '90' },
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

/**
 * Selector desplegable de voz: cabe en una línea y solo ocupa espacio cuando
 * lo abres. Es lo que pide el usuario frente a los chips (pantalla llena).
 */
function VocalSelect({ label, options, value, onChange }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    if (!open) return undefined;
    const onDocDown = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener('mousedown', onDocDown);
    return () => document.removeEventListener('mousedown', onDocDown);
  }, [open]);

  const current = options.find((o) => o.id === value);

  return (
    <div className="relative" ref={ref}>
      <button onClick={() => setOpen((o) => !o)}
        className={`btn h-8 px-2.5 gap-1.5 ${current ? 'btn-signal' : 'btn-ghost'}`}>
        <span className="label">{label}</span>
        <span className="mono text-[11px]">{current ? current.label : 'AUTO'}</span>
        <ChevronDown size={12} className={open ? 'rotate-180 transition-transform' : 'transition-transform'} />
      </button>
      {open && (
        <div className="absolute z-30 top-full left-0 mt-1 min-w-[170px] border border-[var(--line-strong)] bg-[var(--surface-2)] p-1 flex flex-col shadow-lg">
          <button onClick={() => { onChange(''); setOpen(false); }}
            className="text-left px-3 py-1.5 hover:bg-[var(--acc-dim)]">
            <span className="label">AUTO</span>
          </button>
          {options.map((o) => (
            <button key={o.id} onClick={() => { onChange(o.id); setOpen(false); }}
              className={`text-left px-3 py-1.5 hover:bg-[var(--acc-dim)] ${value === o.id ? 'text-[var(--acc)]' : 'text-zinc-200'}`}>
              <span className="mono text-[11.5px]">{o.label}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

const loadHistory = () => {
  try { return JSON.parse(localStorage.getItem(UI.historyKey) ?? '[]'); }
  catch { return []; }
};

export default function Composer({ initialMode = 'music' }) {
  const [mode, setMode] = useState(initialMode);
  const [engine, setEngine] = useState({ checked: false, ok: false });
  const [config, setConfig] = useState(null);
  const [prompt, setPrompt] = useState('');
  const [genre, setGenre] = useState(null);
  const [mood, setMood] = useState(null);
  const [bpm, setBpm] = useState(null);
  const [key, setKey] = useState('');
  const [duration, setDuration] = useState(60);
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

  const maxDuration = config?.max_duration_seconds ?? UI.maxDurationFallback;

  useEffect(() => () => { aliveRef.current = false; }, []);

  useEffect(() => {
    let active = true;
    (async () => {
      const [health, cfg] = await Promise.all([
        api.engineHealth(),
        api.musicConfig().catch(() => null),
      ]);
      if (!active) return;
      setEngine({ checked: true, ok: Boolean(health?.engine?.reachable) });
      if (cfg) {
        setConfig(cfg);
        setDuration(Math.min(cfg.duration_seconds ?? 60, cfg.max_duration_seconds ?? 240));
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

  /** "Escribir la letra por mí": el LM local propone un borrador editable. */
  /** Quita todas las elecciones de voz y vuelve a AUTO. */
  const resetVocal = () => {
    setVocal({ gender: '', timbre: '', style: '', emotion: '' });
  };

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
      if (data.warning) {
        // El LM no compone letra aquí: no pisamos lo que haya escrito el usuario.
        setLyricsWarning(data.warning);
      } else {
        setLyrics(structureLyric(data.lyrics || ''));
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
    while (aliveRef.current) {
      await new Promise((r) => setTimeout(r, JOB_POLL_INTERVAL_MS));
      if (!aliveRef.current) return;
      try {
        const status = await api.musicStatus(jobId);
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
          return;
        }
        if (status.status === 'failed') {
          setError(status.error ?? 'La generación falló en el motor');
          return;
        }
      } catch (e) {
        setError(e.message);
        return;
      }
    }
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

  /** Variaciones A/B: mismo prompt, 2 seeds aleatorias distintas → cola. */
  const generateVariations = async () => {
    setError(null);
    const finalPrompt = buildPrompt();
    if (!finalPrompt) {
      setError('Elige un género o escribe una descripción');
      return;
    }
    setJob({ status: 'queued', progress: 'variaciones A/B en cola' });
    try {
      const s1 = Math.floor(Math.random() * 1_000_000);
      let s2 = Math.floor(Math.random() * 1_000_000);
      if (s2 === s1) s2 = (s1 + 1) % 1_000_000;
      await launchGeneration(finalPrompt, s1);
      await launchGeneration(finalPrompt, s2);
    } catch (e) {
      setError(e.message);
      setJob({ status: 'failed' });
    }
  };

  const clearHistory = () => {
    localStorage.removeItem(UI.historyKey);
    setHistory([]);
  };

  /** Mejora el prompt actual con reglas locales de producción. */
  const enhancePrompt = async () => {
    const base = buildPrompt();
    if (base.length < 3) {
      setError('Escribe o elige un género antes de mejorar el prompt');
      return;
    }
    setError(null);
    setEnhancing(true);
    try {
      const res = await api.enhancePrompt({ prompt: base, bpm: bpm ?? null });
      setPrompt(res.enhanced);
      setGenre(null);
      setMood(null);
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
    if (spec.duration) setDuration(Math.min(spec.duration, maxDuration));
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
    <div className="h-full w-full flex px-16 py-10 gap-12">
      {/* ============ CONSOLA ============ */}
      <section className="flex-1 min-w-0 flex flex-col gap-7 my-auto">
        {/* Modo: música / voz + asistente de calidad */}
        <div className="flex items-center gap-2">
          {MODES.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              onClick={() => setMode(id)}
              className={`btn px-4 h-9 ${mode === id ? 'btn-signal' : 'btn-ghost'}`}
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
          <span className="ml-auto label">MOTOR {engine.ok ? 'ACTIVO' : engine.checked ? 'APAGADO' : '…'}</span>
        </div>

        {/* Opciones: género / mood / bpm / tonalidad (sin caja, filas de consola) */}
        <div className="flex flex-col gap-5">
          <div className="flex items-center gap-5">
            <span className="label w-20 shrink-0">GÉNERO</span>
            <div className="flex flex-wrap gap-2">
              {GENRES.map(({ id, tag }) => (
                <button key={id} onClick={() => setGenre(genre === id ? null : id)}
                  className={`btn-chip ${genre === id ? 'active' : ''}`}>{tag}</button>
              ))}
            </div>
          </div>
          <div className="flex items-center gap-5">
            <span className="label w-20 shrink-0">MOOD</span>
            <div className="flex flex-wrap gap-2">
              {MOODS.map(({ id, tag }) => (
                <button key={id} onClick={() => setMood(mood === id ? null : id)}
                  className={`btn-chip ${mood === id ? 'active' : ''}`}>{tag}</button>
              ))}
            </div>
          </div>
          <div className="flex items-center gap-5">
            <span className="label w-20 shrink-0">BPM</span>
            <div className="flex flex-wrap gap-2">
              {BPM_PRESETS.map(({ id, value, tag }) => (
                <button key={id} onClick={() => setBpm(value)}
                  className={`btn-chip ${bpm === value ? 'active' : ''}`}>{tag}</button>
              ))}
            </div>
            <span className="label shrink-0 ml-6">TONO</span>
            <div className="flex flex-wrap gap-2">
              {KEYS.map(({ id, tag }) => (
                <button key={id || 'auto'} onClick={() => setKey(id)}
                  className={`btn-chip ${key === id ? 'active' : ''}`}>{tag}</button>
              ))}
            </div>
          </div>
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
            <div className="flex flex-col gap-3">
              {/* Una sola línea con todo el control de voz; cada grupo se despliega al pulsar. */}
              <div className="flex items-center gap-2 flex-wrap">
                <span className="label shrink-0">VOZ</span>
                <VocalSelect label="GÉNERO" options={VOCAL_GENDER} value={vocal.gender}
                  onChange={(v) => setVocal({ ...vocal, gender: v })} />
                <VocalSelect label="TIMBRE" options={VOCAL_TIMBRE} value={vocal.timbre}
                  onChange={(v) => setVocal({ ...vocal, timbre: v })} />
                <VocalSelect label="CANTADO" options={VOCAL_STYLE} value={vocal.style}
                  onChange={(v) => setVocal({ ...vocal, style: v })} />
                <VocalSelect label="EMOCIÓN" options={VOCAL_EMOTION} value={vocal.emotion}
                  onChange={(v) => setVocal({ ...vocal, emotion: v })} />
                <VocalSelect label="IDIOMA" options={VOCAL_LANGUAGES} value={vocalLang}
                  onChange={setVocalLang} />
                <button onClick={resetVocal} className="btn btn-ghost h-8 px-2.5"
                  title="Quitar todas las elecciones de voz">
                  <RotateCcw size={12} />
                </button>
              </div>

              <div className="flex flex-col gap-2">
                <div className="flex items-center justify-between gap-4 flex-wrap">
                  <span className="label">LETRA</span>
                  <div className="flex items-center gap-2">
                    {lyrics.trim() !== '' && (
                      <button onClick={() => setShowLyricPreview((s) => !s)} className="btn btn-ghost h-8 px-2.5"
                        title="Ver exactamente lo que se envía al motor">
                        {showLyricPreview ? 'OCULTAR' : 'VER LO QUE SE CANTA'}
                      </button>
                    )}
                    <button onClick={autoWriteLyrics} disabled={writingLyrics}
                      title="El motor local propone un borrador que puedes corregir; si no compone, escribe tú"
                      className="btn btn-ghost h-8 px-3">
                      {writingLyrics ? <><Loader2 size={12} className="animate-spin" /> EL MOTOR ESCRIBE (hasta 2 min)…</>
                        : <><Feather size={12} /> ESCRIBIRLA POR MÍ</>}
                    </button>
                  </div>
                </div>

                <textarea
                  value={lyrics}
                  onChange={(e) => { setLyrics(e.target.value); if (lyricsWarning) setLyricsWarning(null); }}
                  placeholder="Escribe la letra tal cual, verso a verso. La app le añade [verso] y [estribillo] si hace falta."
                  className="bg-transparent outline-none resize-none text-[15px] leading-relaxed text-zinc-100 placeholder:text-[var(--faint)] min-h-[96px] font-medium border-l-2 border-[var(--acc-line)] pl-5 py-1.5"
                />

                {showLyricPreview && lyrics.trim() !== '' && (
                  <pre className="mono text-[10.5px] text-[var(--muted)] bg-[var(--surface-2)] border border-[var(--line)] p-3 whitespace-pre-wrap max-h-40 overflow-y-auto">
                    {structureLyric(lyrics.trim())}
                  </pre>
                )}

                <p className="mono text-[10px] text-[var(--faint)]">
                  {lyricsWarning
                    ? <span className="text-[var(--warn)]">{lyricsWarning}</span>
                    : lyrics.trim() === ''
                      ? 'Sin letra el motor hace un instrumental. Con letra, canta.'
                      : hasLyricStructure(lyrics)
                        ? 'Ya tiene marcas de estructura: se canta tal cual.'
                        : 'Se enviará con [verso]/[estribillo] añadidos automáticamente.'}
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
          <div className="flex items-center gap-5">
            <div className="flex items-center gap-3 flex-1 min-w-0">
              <span className="label shrink-0">DURACIÓN</span>
              <input type="range" min={UI.minDuration} max={maxDuration} step={UI.step}
                value={duration} onChange={(e) => setDuration(Number(e.target.value))}
                className="flex-1 min-w-0" aria-label="Duración" />
              <span className="num w-12 text-right">{fmt(duration)}</span>
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
            <button onClick={generateVariations} disabled={!canGenerate} title="Misma idea, 2 semillas distintas, se comparan en la cola"
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
        {!engine.checked && (
          <p className="mono text-[11px] text-[var(--muted)] animate-pulse py-2">SYNC CON MOTOR LOCAL…</p>
        )}
      </section>

      {wizardOpen && (
        <QualityWizard onClose={() => setWizardOpen(false)} onApply={applyWizard} />
      )}

      {/* ============ SESIÓN ============ */}
      <aside className="w-[360px] shrink-0 flex flex-col min-h-0 self-center max-h-full">
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
