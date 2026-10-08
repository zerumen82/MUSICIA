// Mesa de remix de una pista (SUBIR y BIBLIOTECA).
import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Loader2, ChevronDown, Check, AlertTriangle } from 'lucide-react';
import { api, isEnginePollBlip, JOB_POLL_INTERVAL_MS, JOB_POLL_MAX_MISSES } from '../api';
import RemixPanel from './RemixPanel';
import Waveform from './Waveform';
import SelectBox from './SelectBox';
import Glossary from './Glossary';
import VariantChips from './VariantChips';
import { structureLyric } from '../vocal';
import { glossPrompt } from '../prompt_gloss';

// Acciones que usan el modelo ACE-Step (generación IA)
const AI_ACTIONS = [
  { id: 'version', label: 'VERSIÓN · CAMBIAR EL ESTILO', needs: 'prompt', needsBpm: true, needsStrength: true },
  { id: 'tramo', label: 'TRAMO · REHACER UN TROZO', needs: 'prompt', needsRange: true },
  { id: 'reestilar', label: 'REESTILAR · OYE TU PISTA', needs: 'prompt', needsBpm: true, needsStrength: true },
  { id: 'voz', label: 'VOZ + BASE NUEVA', needs: 'prompt', needsBpm: true },
  // LEGO / EXTRACT / COMPLETE exigen el modelo base (acestep-v15-base),
  // no instalado: se ocultan hasta medirlo (spec/05 fuera de propuesta).
];

// Acciones que usan procesamiento local (DSP/demucs)
const LOCAL_ACTIONS = [
  { id: 'ajustar', label: 'AJUSTAR · TEMPO, TONO, RECORTE' },
  { id: 'loop4', label: 'LOOP DE 4 COMPASES' },
  { id: 'medio', label: 'MEDIO TIEMPO' },
  { id: 'doble', label: 'DOBLE TIEMPO' },
  { id: 'bpm', label: 'FORZAR TEMPO A', needs: 'bpm' },
  { id: 'instrumental', label: 'QUITAR VOCES' },
  { id: 'acapella', label: 'SOLO LA VOZ' },
];

// Concatenar para la acción original (mantener compatibilidad)
const ACTIONS = [...AI_ACTIONS, ...LOCAL_ACTIONS];

const MENU_MAX_PX = 288;

const PROMPT_PLACEHOLDER = {
  version: 'Estilo nuevo: nómbralo («hardcore», «drum and bass»…) y di el patrón («en 4x4») y detalles. Sin nombre de estilo, el motor improvisa.',
  tramo: 'Qué debe sonar aquí: estilo + patrón + detalles («percusión hardcore en 4x4, sin melodías»).',
  reestilar: 'Nuevo estilo: nómbralo («hardcore», «drum and bass»…) y di el patrón («en 4x4») y detalles. El motor OYE tu pista y la reviste: conserva la estructura, cambia el resto.',
  voz: 'Música nueva para tu voz: nombra el estilo («techno oscuro en 4x4»…) y el patrón. Tu voz se conserva tal cual; la música la genera el modelo estricto al tempo de tu tema.',
};

const STATUS = {
  queued: { label: 'EN COLA', cls: 'text-[var(--warn)]' },
  running: { label: 'CREANDO', cls: 'text-[var(--acc)]' },
  succeeded: { label: 'LISTA', cls: 'st-ok' },
  failed: { label: 'ERROR', cls: 'st-err' },
};

const HINT = {
  crear: 'Normalmente tarda 1-3 min con el modelo cargado (la primera vez, 5-6 min: descarga y carga del modelo).',
  separar: 'La primera vez tarda 1-3 min. Luego va más rápido.',
  local: 'Se hace en esta máquina, sin el motor de música.',
};

// El corte de verdad lo hace el servidor (mixer.loop_bars y beats_per_bar).
const ACTION_NOTE = {
  instrumental: 'Quita la voz cantada y deja la música de la pista.',
  acapella: 'Deja solo la voz cantada.',
  loop4: 'Corta cuatro compases de 4/4 desde el primer golpe medido.',
  medio: 'Mitad de velocidad. El tono no cambia.',
  doble: 'Doble de velocidad. El tono no cambia.',
  bpm: 'La lleva al BPM escrito. El tono no cambia.',
};

export default function RemixActions({ fileName, onDone, initialAction = '', ficha = null, sourceKind = null }) {
  const [open, setOpen] = useState(false);
  const [action, setAction] = useState(initialAction);
  const [prompt, setPrompt] = useState(ficha?.prompt ?? '');
  const [bpm, setBpm] = useState(ficha?.bpm ? String(Math.round(Number(ficha.bpm))) : '');
  const [lyrics, setLyrics] = useState(ficha?.lyrics ?? '');
  const [key, setKey] = useState(ficha?.key_scale ?? '');
  const [seed, setSeed] = useState('');
  const [songName, setSongName] = useState('');
  const [enhancing, setEnhancing] = useState(false);
  const [strength, setStrength] = useState(null);
  const [forceAuto, setForceAuto] = useState(true); // reestilar: AUTO deduce del prompt; off = mando yo
  const [repaintStart, setRepaintStart] = useState('');
  const [repaintEnd, setRepaintEnd] = useState('');
  const [status, setStatus] = useState(null);
  const [job, setJob] = useState(null);
  const [busy, setBusy] = useState(false);
  const [box, setBox] = useState(null);
  const [styleInfo, setStyleInfo] = useState(null); // capas + chips (del backend)
  const [extendMinutes, setExtendMinutes] = useState(''); // vacío = dura el tema
  const [maxMinutes, setMaxMinutes] = useState(10); // real desde /music/config
  const [showTips, setShowTips] = useState(false); // el consejo solo si se pide
  const ref = useRef(null);
  const menuRef = useRef(null);

  useEffect(() => {
    let alive = true;
    api.musicConfig()
      .then((cfg) => {
        if (!alive) return;
        if (typeof cfg?.cover_strength === 'number') setStrength(cfg.cover_strength);
        // Tope de MINUTOS = duración máxima del motor (config, no hardcode).
        const maxS = Number(cfg?.max_duration_seconds);
        if (Number.isFinite(maxS) && maxS > 0) {
          setMaxMinutes(Math.max(1, Math.floor(maxS / 60)));
        }
      })
      .catch(() => {});
    return () => { alive = false; };
  }, []);

  /** Reloj en vivo: el contador corre cada segundo entre sondeos, como en CREAR. */
  useEffect(() => {
    if (!busy) return undefined;
    const t = setInterval(() => {
      setJob((cur) => (cur ? { ...cur, elapsed_seconds: (cur.elapsed_seconds ?? 0) + 1 } : cur));
    }, 1000);
    return () => clearInterval(t);
  }, [busy]);

  const placeMenu = () => {
    const el = ref.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    const below = window.innerHeight - rect.bottom;
    const up = below < MENU_MAX_PX && rect.top > below;
    setBox({
      left: Math.max(8, rect.left),
      minWidth: Math.max(280, rect.width),
      ...(up
        ? { bottom: window.innerHeight - rect.top + 4 }
        : { top: rect.bottom + 4 }),
    });
  };

  useEffect(() => {
    if (!open) return undefined;
    const onDoc = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    const close = () => setOpen(false);
    const onScroll = (e) => {
      if (menuRef.current && menuRef.current.contains(e.target)) return;
      close();
    };
    document.addEventListener('mousedown', onDoc);
    window.addEventListener('resize', close);
    window.addEventListener('scroll', onScroll, true);
    return () => {
      document.removeEventListener('mousedown', onDoc);
      window.removeEventListener('resize', close);
      window.removeEventListener('scroll', onScroll, true);
    };
  }, [open]);

  const onRange = useCallback((sel) => {
    setRepaintStart(String(sel.trim_start_s ?? 0));
    setRepaintEnd(sel.trim_end_s == null ? '' : String(sel.trim_end_s));
  }, []);

  const current = ACTIONS.find((a) => a.id === action);

  /** Chips sugeridos mientras escribes en el remix: mismo catálogo del
      backend que en CREAR (sin LM, sin listas en la UI). Debounce 300 ms. */
  useEffect(() => {
    if (!(current?.needs === 'prompt')) {
      setStyleInfo(null);
      return undefined;
    }
    const t = setTimeout(async () => {
      const info = await api.styleOptions(prompt.trim());
      setStyleInfo(info);
    }, 300);
    return () => clearTimeout(t);
  }, [prompt, current?.needs]);

  /** Cualquier texto (chip o entrada del glosario) se añade al prompt:
      un solo cuadro, todo editable. */
  const addTexto = (text) => {
    const base = prompt.trim();
    setPrompt(base ? `${base} ${text}` : text);
  };
  const addChip = (chip) => addTexto(chip.clause ?? chip.text);

  const absorb = (incoming, pipeline) => {
    setJob((cur) => {
      const ratio = typeof incoming.progress_ratio === 'number'
        ? incoming.progress_ratio
        : (typeof incoming.engine_progress === 'number' ? incoming.engine_progress : null);
      const serverElapsed = Number(incoming.elapsed_seconds) || 0;
      return {
        status: incoming.status ?? cur?.status ?? 'running',
        phase: incoming.phase || cur?.phase || 'Trabajando…',
        progress_ratio: ratio,
        elapsed_seconds: Math.max(serverElapsed, cur?.elapsed_seconds ?? 0),
        events: Array.isArray(incoming.events) ? incoming.events : (cur?.events ?? []),
        pipeline: pipeline || cur?.pipeline || 'crear',
        error: incoming.error ?? null,
      };
    });
  };

  const begin = (pipeline, phase, jobStatus = 'running') => {
    setStatus(null);
    setJob({
      status: jobStatus,
      phase,
      progress_ratio: pipeline === 'crear' ? 0 : null,
      elapsed_seconds: 0,
      events: [{ t: 0, text: phase }],
      pipeline,
      error: null,
    });
  };

  const waitUntil = async (read) => {
    let misses = 0;
    let phase = 'Trabajando…';
    for (;;) {
      try {
        const incoming = await read();
        if (incoming.phase && incoming.phase !== 'Error') phase = incoming.phase;
        if (incoming.status === 'succeeded') return incoming;
        if (incoming.status === 'failed') {
          // El servidor ya cerró el trabajo. El texto del error no lo reabre.
          const err = new Error(incoming.error ?? 'El trabajo falló');
          err.hard = true;
          throw err;
        } else {
          misses = 0;
          absorb({ ...incoming, phase });
        }
      } catch (e) {
        if (e.hard) throw e;
        const gone = /no encontrada|no existe/i.test(e.message ?? '');
        if (gone) throw e;
        misses += 1;
        if (isEnginePollBlip(e.message)) misses = 0;
        else if (misses >= JOB_POLL_MAX_MISSES) {
          const health = await api.engineHealth();
          if (health?.engine?.reachable) throw e;
          misses = 0;
        }
      }
      await new Promise((r) => setTimeout(r, JOB_POLL_INTERVAL_MS));
    }
  };

  const run = async () => {
    const id = action;
    if (!id || id === 'ajustar') return;
    const needsPrompt = current?.needs === 'prompt';
    if (needsPrompt && prompt.trim().length < 3) {
      setJob(null);
      setStatus({ tone: 'err', text: 'Escribe un prompt antes de hacer' });
      return;
    }
    if (id === 'bpm' && !bpm) {
      setJob(null);
      setStatus({ tone: 'err', text: 'Escribe el BPM objetivo' });
      return;
    }
    let start = 0;
    let end = -1;
    if (id === 'tramo') {
      start = repaintStart === '' ? 0 : Number(repaintStart);
      end = repaintEnd === '' ? -1 : Number(repaintEnd);
      if (Number.isNaN(start) || Number.isNaN(end) || start < 0 || end < -1 || (end !== -1 && end <= start)) {
        setJob(null);
        setStatus({ tone: 'err', text: 'El tramo empieza en 0 o más y acaba después. Vacío en hasta = el final' });
        return;
      }
    }
    if ((id === 'version' || id === 'reestilar') && strength !== null) {
      const fuerza = Number(strength);
      if (Number.isNaN(fuerza) || fuerza < 0 || fuerza > 1) {
        setJob(null);
        setStatus({ tone: 'err', text: 'La fuerza tiene que estar entre 0 y 1' });
        return;
      }
    }

    setBusy(true);
    try {
      let result = null;
      if (id === 'version' || id === 'tramo') {
        begin('crear', id === 'tramo' ? 'Enviando el tramo al motor…' : 'Enviando la versión al motor…');
        const letra = lyrics.trim() ? structureLyric(lyrics) : null;
        const started = await api.generateMusic({
          prompt: prompt.trim(),
          instrumental: !letra,
          lyrics: letra,
          source_name: fileName,
          source_kind: sourceKind,
          task_type: id === 'version' ? 'cover' : 'repaint',
          bpm: bpm ? Number(bpm) : null,
          key_scale: key.trim() || null,
          seed: seed.trim() === '' ? null : Number(seed),
          output_name: songName.trim() || null,
          ...(id === 'version' && strength !== null ? { cover_strength: Number(strength) } : {}),
          ...(id === 'tramo' ? { repaint_start: start, repaint_end: end } : {}),
        });
        const done = await waitUntil(() => api.musicStatus(started.job_id));
        result = done.output_name;
        setStatus({ tone: 'ok', text: `Listo: ${result}` });
      } else if (id === 'voz') {
        // Conservar voz (spec/02 [R5]): la voz se separa y la música es
        // nueva. Sin letra (la pone tu grabación) y sin fuerza (no hay cover).
        begin('crear', 'Separando tu voz y pidiendo música nueva…');
        const started = await api.remixAi({
          file_name: fileName,
          source_kind: sourceKind,
          prompt: prompt.trim(),
          bpm: bpm ? Number(bpm) : null,
          // MINUTOS: vacío = dura el tema; elegido = base nueva más larga
          // (el backend la pide al motor con esa duración, spec 2026-10-06).
          duration_seconds: extendMinutes ? Number(extendMinutes) * 60 : null,
          output_name: songName.trim() || null,
          mode: 'voz',
        });
        const done = await waitUntil(() => api.remixAiStatus(started.job_id));
        const variants = done.result?.variants ?? [];
        result = done.result?.mix ?? done.result?.base;
        setStatus({ tone: 'ok', text: variants.length > 1 ? `Listo: ${variants.join(', ')} (elige en BIBLIOTECA)` : `Listo: ${result}` });
      } else if (id === 'reestilar') {
        // Cover nativo (spec/02 [R2]): el motor oye la pista y la reviste.
        // Sin letra nueva sale instrumental; el motor no clona tu voz.
        begin('crear', 'Enviando el reestilo al motor…');
        const letra = lyrics.trim() ? structureLyric(lyrics.trim()) : '';
        const started = await api.remixAi({
          file_name: fileName,
          source_kind: sourceKind,
          prompt: prompt.trim(),
          bpm: bpm ? Number(bpm) : null,
          lyrics: letra || null,
          output_name: songName.trim() || null,
          cover_strength: !forceAuto && strength !== null ? Number(strength) : null,
        });
        const done = await waitUntil(() => api.remixAiStatus(started.job_id));
        const variants = done.result?.variants ?? [];
        result = done.result?.mix ?? done.result?.base;
        setStatus({ tone: 'ok', text: variants.length > 1 ? `Listo: ${variants.join(', ')} (elige en BIBLIOTECA)` : `Listo: ${result}` });
      } else if (id === 'instrumental' || id === 'acapella') {
        begin('separar', 'En cola', 'queued');
        const res = await api.separate(
          { file_name: fileName, source_kind: sourceKind, output_name: fileName.replace(/\.[^.]+$/, '') },
          (incoming) => absorb(incoming, 'separar'),
        );
        result = id === 'instrumental' ? res.base : res.vocals;
        setStatus({ tone: 'ok', text: `Listo: ${result}` });
      } else if (id === 'medio' || id === 'doble') {
        const half = id === 'medio';
        begin('local', half ? 'Pasando a medio tiempo, sin cambiar el tono…' : 'Pasando a doble tiempo, sin cambiar el tono…');
        const res = await api.setTempo({ file_name: fileName, source_kind: sourceKind, mode: half ? 'half' : 'double' });
        setStatus({ tone: 'ok', text: `${half ? 'Medio' : 'Doble'} tiempo: ${res.source_bpm} → ${res.result_bpm} bpm` });
        result = res.file_name;
      } else if (id === 'loop4') {
        begin('local', 'Midiendo el golpe y cortando cuatro compases…');
        const res = await api.makeLoop({ file_name: fileName, source_kind: sourceKind });
        result = res.file_name;
        setStatus({
          tone: 'ok',
          text: `Loop de ${res.bars} compases de ${res.beats_per_bar}/4 desde ${res.start_seconds}s, ${res.seconds}s a ${res.bpm} bpm: ${result}`,
        });
      } else if (id === 'bpm') {
        begin('local', `Forzando el tempo a ${bpm} bpm, sin cambiar el tono…`);
        const res = await api.setTempo({ file_name: fileName, source_kind: sourceKind, mode: 'bpm', bpm: Number(bpm) });
        result = res.file_name;
        setStatus({ tone: 'ok', text: `${res.source_bpm} → ${res.result_bpm} bpm` });
      }
      if (result) {
        setJob(null);
        onDone?.(result);
      }
    } catch (e) {
      // Un fallo real se enseña aunque el texto diga «no responde».
      // Ese texto solo se traga si el sondeo se cortó y el trabajo sigue vivo.
      if (!e.hard && isEnginePollBlip(e.message)) setStatus(null);
      else {
        setJob((cur) => (cur ? { ...cur, status: 'failed', phase: 'Error', error: e.message } : cur));
        setStatus({ tone: 'err', text: e.message });
      }
    } finally {
      setBusy(false);
    }
  };

  const improve = async () => {
    if (prompt.trim().length < 3) {
      setStatus({ tone: 'err', text: 'Escribe un prompt antes de mejorarlo' });
      return;
    }
    setEnhancing(true);
     try {
       const res = await api.enhancePrompt({ prompt: prompt.trim(), bpm: bpm ? Number(bpm) : null });
       setPrompt(res.enhanced ?? prompt);
       const added = Array.isArray(res.additions) ? res.additions.slice(0, 3).join(', ') : '';
       setStatus({ tone: 'ok', text: added ? `Se añade: ${added}. La frase no se reescribe.` : 'La frase se queda como la escribiste' });
     } catch (e) {
       setStatus({ tone: 'err', text: e.message });
     } finally {
       setEnhancing(false);
     }
  };

  const applyAjuste = async (params) => {
    setBusy(true);
    begin('local', 'Aplicando tempo, tono y recorte…');
    try {
      const res = await api.remix({ file_name: fileName, source_kind: sourceKind, ...params });
      setJob(null);
      setStatus({ tone: 'ok', text: `Listo: ${res.file_name}` });
      onDone?.(res.file_name);
    } catch (e) {
      setJob((cur) => (cur ? { ...cur, status: 'failed', phase: 'Error' } : cur));
      setStatus({ tone: 'err', text: e.message });
    } finally {
      setBusy(false);
    }
  };

  /** AÑADIR ofrece todos los chips que sugiere el backend: son vocabulario
      real del modelo (los valida backend/test_realism.py), así que no se
      esconden ni por prompt vacío ni por modo instrumental/voz. En la lista
      la etiqueta corta en español; al elegirla se añade la cláusula en
      inglés (en el tooltip se ve cuál es). */
  const chipOptions = (styleInfo?.chips ?? [])
    .filter((c) => c.suggested)
    .map((c) => ({
      id: c.label, label: c.label, title: `Se añade: «${c.clause ?? c.text}»`,
    }));
  const addChipById = (id) => {
    const chip = (styleInfo?.chips ?? []).find((c) => c.label === id);
    if (chip) addChip(chip);
  };

  const statusInfo = job?.status === 'failed'
    ? STATUS.failed
    : job?.status === 'queued'
      ? STATUS.queued
      : job?.pipeline === 'separar'
        ? { label: 'SEPARANDO', cls: 'text-[var(--acc)]' }
        : job?.pipeline === 'local'
          ? { label: 'TRABAJANDO', cls: 'text-[var(--acc)]' }
          : (job ? STATUS[job.status] : null);
  const stepIdx = job?.status === 'running' ? 1 : 0;

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center gap-2 flex-wrap">
        <span className="label shrink-0">REMIXER</span>
        <div className="relative" ref={ref}>
          <button type="button" onClick={() => {
            if (open) { setOpen(false); return; }
            placeMenu();
            setOpen(true);
          }} disabled={busy}
            className="btn btn-ghost h-8 px-2.5 gap-1.5 max-w-full">
            <span className="mono text-[11px] truncate">{current?.label ?? 'ELIGE UNA ACCIÓN'}</span>
            <ChevronDown size={12} className={open ? 'rotate-180 transition-transform' : 'transition-transform'} />
          </button>
          {open && (
             <div ref={menuRef}
               className="fixed z-50 overflow-y-auto border border-[var(--line-strong)] bg-[var(--surface-2)] p-1 flex flex-col shadow-lg"
               style={box ? { left: box.left, top: box.top, bottom: box.bottom, minWidth: box.minWidth, maxHeight: MENU_MAX_PX } : { visibility: 'hidden', maxHeight: MENU_MAX_PX }}>
               {AI_ACTIONS.map((a) => (
                 <button key={a.id} type="button" onClick={() => { setOpen(false); setAction(a.id); setStatus(null); setJob(null); setForceAuto(true); }}
                   className="text-left px-3 py-2 hover:bg-[var(--acc-dim)] text-zinc-200">
                   <span className="mono text-[11.5px]">{a.label}</span>
                   <span className="mono text-[9px] text-[var(--acc)] ml-1">[IA]</span>
                 </button>
               ))}
               <div className="border-t border-[var(--line)] my-1" />
               {LOCAL_ACTIONS.map((a) => (
                 <button key={a.id} type="button" onClick={() => { setOpen(false); setAction(a.id); setStatus(null); setJob(null); setForceAuto(true); }}
                   className="text-left px-3 py-2 hover:bg-[var(--acc-dim)] text-zinc-200">
                   <span className="mono text-[11.5px]">{a.label}</span>
                   <span className="mono text-[9px] text-[var(--muted)] ml-1">[LOCAL]</span>
                 </button>
               ))}
             </div>
          )}
        </div>
        {action && action !== 'ajustar' && (
          <button type="button" onClick={() => void run()} disabled={busy} className="btn btn-signal h-8 px-4">
            {busy ? <Loader2 size={13} className="animate-spin" /> : null} HACER
          </button>
        )}
      </div>

       {current?.needs === 'prompt' && (
         <div className="flex flex-col gap-2">
            <textarea value={prompt} onChange={(e) => setPrompt(e.target.value)} rows={2}
              placeholder={PROMPT_PLACEHOLDER[action]}
              className="px-3 py-2 text-[13px] bg-transparent outline-none border border-[var(--line)] focus:border-[var(--acc-line)] resize-y" />
            <div className="flex items-center gap-3 flex-wrap">
              {prompt.trim() && (
                <span className="mono text-[9px] text-[var(--faint)] break-all max-w-[60ch]">
                  ENVÍA: {glossPrompt(prompt.trim())}
                </span>
              )}
              <button type="button" onClick={() => setShowTips((v) => !v)}
                className="mono text-[9.5px] text-[var(--faint)] hover:text-[var(--muted)] ml-auto shrink-0">
                {showTips ? 'OCULTAR CONSEJO' : 'CONSEJO'}
              </button>
            </div>
            {prompt.trim() && showTips && (
              <div className="text-[11px] text-[var(--text)] bg-[var(--surface-1)] border border-[var(--line)] rounded px-2 py-1.5">
                💡 <span className="font-medium">Tips:</span> Para conservar voz/guitarra, menciona explícitamente lo que quieres mantener (ej: «manteniendo la voz clara y guitarra principal»). Para cambios de estilo dramaticos (ej: a hardstyle), usa fuerza 0,3-0,5. Para cambios sutiles, usa 0,7-0,9.
              </div>
            )}
            <div className="flex items-center gap-2 flex-wrap">
              <SelectBox label="AÑADIR" placeholder="DETALLE DEL CATÁLOGO" clearable={false}
                options={chipOptions} value="" onChange={addChipById} />
              <Glossary prompt={prompt} setPrompt={setPrompt} />
            </div>
            <VariantChips prompt={prompt} setPrompt={setPrompt} />
            {styleInfo && (
              <div className="mono text-[10px]">
                {styleInfo.detected_genre && (
                  <span className="text-[var(--acc)]">
                    ESTILO: {styleInfo.detected_genre}{styleInfo.suggested_bpm ? ` · ${styleInfo.suggested_bpm} bpm` : ''}
                  </span>
                )}
                {styleInfo.detected_genre && styleInfo.modifiers?.length > 0 && <span className="text-[var(--faint)]"> · </span>}
                {styleInfo.modifiers?.length > 0 && (
                  <span className="text-[var(--muted)]">{styleInfo.modifiers.join(', ')}</span>
                )}
              </div>
            )}
        </div>
      )}
      {action === 'reestilar' && (
        <span className="mono text-[10px] text-[var(--faint)]">
          El motor OYE tu pista y la reviste del estilo que pides: conserva la estructura, cambia el resto.
          {' '}Sin letra nueva sale instrumental: no clona tu voz. Salen 2 variantes y eliges en BIBLIOTECA.
        </span>
      )}
      {action === 'voz' && (
        <span className="mono text-[10px] text-[var(--faint)]">
          Tu voz se separa y se conserva tal cual; debajo se genera música nueva con el estilo que pides,
          al tempo de tu tema (o al BPM que escribas). Salen 2 mezclas y eliges en BIBLIOTECA.
        </span>
      )}
      {action === 'reestilar' && (
        <label className="flex flex-col gap-1">
          <span className="label">LETRA NUEVA · VACÍO = REESTILO INSTRUMENTAL</span>
          <textarea value={lyrics} onChange={(e) => setLyrics(e.target.value)} rows={3}
            placeholder="Si la escribes, la versión la canta con el estilo nuevo"
            className="px-3 py-2 text-[13px] bg-transparent outline-none border border-[var(--line)] focus:border-[var(--acc-line)] resize-y" />
        </label>
      )}
      {(action === 'reestilar' || action === 'voz') && (
        <label className="flex items-center gap-2">
          <span className="label">NOMBRE</span>
          <input value={songName} onChange={(e) => setSongName(e.target.value)} placeholder="nombre del reestilo"
            className="px-2 py-1.5 flex-1 min-w-0 text-[12px] mono bg-transparent outline-none border border-[var(--line)] focus:border-[var(--acc-line)]" />
        </label>
      )}

       <div className="flex items-center gap-2 flex-wrap">
         {(current?.needsBpm || current?.needs === 'bpm') && (
           <label className="flex items-center gap-2">
             <span className="label">BPM</span>
             <input value={bpm} onChange={(e) => setBpm(e.target.value.replace(/[^0-9]/g, ''))} placeholder="auto"
               className="px-2 py-1.5 w-16 text-[12px] mono bg-transparent outline-none border border-[var(--line)] focus:border-[var(--acc-line)]" />
           </label>
         )}
         {action === 'voz' && (
           <div className="flex items-center gap-2">
             <SelectBox label="MINUTOS" placeholder="COMO EL TEMA" clearable
               options={Array.from({ length: maxMinutes }, (_, i) => ({ id: String(i + 1), label: `${i + 1} MIN` }))}
               value={extendMinutes} onChange={setExtendMinutes} />
             <span className="mono text-[10px] text-[var(--faint)]">vacío = dura el tema · más = base más larga (la voz se reparte en trozos, no se estira)</span>
           </div>
         )}
         {current?.needsStrength && strength !== null && (
           <label className="flex items-center gap-2">
             <span className="label shrink-0">FUERZA</span>
             <input type="range" min={0} max={1} step={0.05} value={strength}
               onChange={(e) => setStrength(Number(e.target.value))} className="w-28" />
             <span className="num w-8 text-right">{Number(strength).toFixed(2)}</span>
             {action !== 'reestilar' || !forceAuto && (
               <span className="mono text-[10px] text-[var(--muted)] block mt-1">
                 0,3-0,5 = cambio significativo │ 0,7-0,9 = cambio sutil
               </span>
             )}
           </label>
         )}
       {action === 'reestilar' && (
           <label className="flex items-center gap-2">
             <span className="label shrink-0">FUERZA</span>
             <button type="button" onClick={() => setForceAuto((v) => !v)}
               className={`btn btn-ghost h-8 px-2.5 ${forceAuto ? '!border-[var(--acc-line)] !text-[var(--text)]' : ''}`}
               title="AUTO deduce la fuerza de tu prompt (sin melodías = baja, como la original = alta). Apágalo para fijarla tú: 0,3-0,5 cambia mucho, 0,7-0,9 es sutil.">
               {forceAuto ? 'AUTO' : 'MANUAL'}
             </button>
             {!forceAuto && strength !== null && (
               <>
                 <input type="range" min={0} max={1} step={0.05} value={strength}
                   onChange={(e) => setStrength(Number(e.target.value))} className="w-28" />
                 <span className="num w-8 text-right">{Number(strength).toFixed(2)}</span>
                 <span className="mono text-[10px] text-[var(--muted)] block mt-1">
                   0,3-0,5 = cambio significativo │ 0,7-0,9 = cambio sutil
                 </span>
               </>
             )}
           </label>
         )}
        {current?.needsRange && (
          <>
            <label className="flex items-center gap-2">
              <span className="label">DESDE</span>
              <input value={repaintStart} onChange={(e) => setRepaintStart(e.target.value.replace(/[^0-9.]/g, ''))}
                placeholder="0"
                className="px-2 py-1.5 w-16 text-[12px] mono bg-transparent outline-none border border-[var(--line)] focus:border-[var(--acc-line)]" />
              <span className="mono text-[10px] text-[var(--faint)]">s</span>
            </label>
            <label className="flex items-center gap-2">
              <span className="label">HASTA</span>
              <input value={repaintEnd} onChange={(e) => setRepaintEnd(e.target.value.replace(/[^0-9.]/g, ''))}
                placeholder="final"
                className="px-2 py-1.5 w-16 text-[12px] mono bg-transparent outline-none border border-[var(--line)] focus:border-[var(--acc-line)]" />
              <span className="mono text-[10px] text-[var(--faint)]">s</span>
            </label>
          </>
        )}
      </div>

      {(action === 'version' || action === 'tramo') && (
        <div className="flex flex-col gap-2">
          <label className="flex flex-col gap-1">
            <span className="label">LETRA · VACÍO = INSTRUMENTAL</span>
            <textarea value={lyrics} onChange={(e) => setLyrics(e.target.value)} rows={3}
              placeholder="Si esta versión canta, escribe la letra"
              className="px-3 py-2 text-[13px] bg-transparent outline-none border border-[var(--line)] focus:border-[var(--acc-line)] resize-y" />
          </label>
          <div className="flex items-center gap-2 flex-wrap">
            <label className="flex items-center gap-2">
              <span className="label">TONO</span>
              <input value={key} onChange={(e) => setKey(e.target.value)} placeholder="La m"
                className="px-2 py-1.5 w-24 text-[12px] mono bg-transparent outline-none border border-[var(--line)] focus:border-[var(--acc-line)]" />
            </label>
            <label className="flex items-center gap-2">
              <span className="label">SEMILLA</span>
              <input value={seed} onChange={(e) => setSeed(e.target.value.replace(/[^0-9]/g, ''))} placeholder="auto"
                className="px-2 py-1.5 w-24 text-[12px] mono bg-transparent outline-none border border-[var(--line)] focus:border-[var(--acc-line)]" />
            </label>
            <label className="flex items-center gap-2 flex-1 min-w-[180px]">
              <span className="label">NOMBRE</span>
              <input value={songName} onChange={(e) => setSongName(e.target.value)} placeholder="nombre del mp3"
                className="px-2 py-1.5 flex-1 min-w-0 text-[12px] mono bg-transparent outline-none border border-[var(--line)] focus:border-[var(--acc-line)]" />
            </label>
            <button type="button" onClick={() => void improve()} disabled={enhancing || busy} className="btn btn-ghost h-8 px-3">
              {enhancing ? <Loader2 size={12} className="animate-spin" /> : null} MEJORAR PROMPT
            </button>
          </div>
        </div>
      )}

      {action === 'tramo' && (
        <div className="flex flex-col gap-1">
          {/* key = otra pista remonta la onda: el recorte anterior no se hereda. */}
          <Waveform key={fileName} fileName={fileName} sourceKind={sourceKind} onSelection={onRange} />
          <span className="mono text-[10px] text-[var(--faint)]">Arrastra la onda para marcar el trozo. Hasta vacío = el final de la pista.</span>
        </div>
      )}

      {action === 'ajustar' && (
        <RemixPanel fileName={fileName} sourceKind={sourceKind} onRun={applyAjuste} />
      )}

      {current?.needsStrength && strength !== null && (
        <span className="mono text-[10px] text-[var(--faint)]">Fuerza 0,3-0,5: cambia mucho el estilo. 0,7-0,9: sutil, se parece al original. 1 casi lo copia.</span>
      )}

      {ACTION_NOTE[action] && (
        <span className="mono text-[10px] text-[var(--faint)]">{ACTION_NOTE[action]}</span>
      )}

      {job && (busy || job.status === 'failed') && (
        <div className="flex flex-col gap-2.5 py-4 border-y border-[var(--line)]">
          <div className="flex items-center gap-4">
            {busy && <div className="eq shrink-0"><span /><span /><span /><span /><span /><span /></div>}
            {job.status === 'failed' && <AlertTriangle size={16} className="st-err shrink-0" />}
            <span className={`mono text-[11px] tracking-[0.1em] shrink-0 ${statusInfo?.cls ?? ''}`}>{statusInfo?.label}</span>
            {busy && (
              <span className="num text-[15px] shrink-0">
                {Math.floor((job.elapsed_seconds ?? 0) / 60)}:{String(Math.floor((job.elapsed_seconds ?? 0) % 60)).padStart(2, '0')}
              </span>
            )}
            {job.status === 'failed' && status?.text && (
              <span className="mono text-[10.5px] st-err truncate flex-1">{status.text}</span>
            )}
            {busy && job.pipeline === 'crear' && (
              <div className="steps shrink-0 ml-auto">
                {[0, 1, 2].map((i) => <span key={i} className={`step ${stepIdx >= i ? 'done' : ''}`} />)}
                <span className="mono text-[9px] text-[var(--faint)] ml-2">COLA→SÍNTESIS→RENDER</span>
              </div>
            )}
            {busy && job.pipeline === 'separar' && (
              <div className="steps shrink-0 ml-auto">
                {[0, 1].map((i) => <span key={i} className={`step ${stepIdx >= i ? 'done' : ''}`} />)}
                <span className="mono text-[9px] text-[var(--faint)] ml-2">COLA→SEPARACIÓN</span>
              </div>
            )}
          </div>
          {busy && (
            <div className="flex flex-col gap-2 pl-1">
              {job.pipeline === 'crear' && (
                <div className="vu w-full" style={{ height: 8 }}>
                  <i style={{ width: `${Math.round((job.progress_ratio ?? 0) * 100)}%` }} />
                </div>
              )}
              <p className="text-[13px] text-zinc-300">
                {job.phase ?? 'Trabajando…'}
                {job.pipeline === 'crear' && job.progress_ratio > 0 && (
                  <span className="num ml-3">{Math.round(job.progress_ratio * 100)}%</span>
                )}
              </p>
              <p className="mono text-[10px] text-[var(--faint)] leading-relaxed">
                {HINT[job.pipeline] ?? HINT.crear}
              </p>
              {job.events?.length > 0 && (
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

      {status?.tone === 'ok' && (
        <p className="mono text-[10.5px] flex items-center gap-1.5 st-ok">
          <Check size={11} />
          {status.text}
        </p>
      )}
      {status?.tone === 'err' && job?.status !== 'failed' && (
        <p className="mono text-[10.5px] flex items-center gap-1.5 st-err">
          <AlertTriangle size={11} />
          {status.text}
        </p>
      )}
    </div>
  );
}
