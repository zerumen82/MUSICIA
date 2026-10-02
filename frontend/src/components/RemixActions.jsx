import React, { useEffect, useRef, useState } from 'react';
import { Loader2, ChevronDown, Check, AlertTriangle, Play } from 'lucide-react';
import { api } from '../api';

/**
 * REMIXER compacto: UNA línea con un desplegable de acciones y, debajo, una
 * sola línea de estado. Nada de paneles abiertos (petición del usuario).
 *
 * Las acciones usan solo motores locales: separación (demucs), ffmpeg para
 * tempo/loops y el motor de música para las bases nuevas desde prompt.
 */
const ACTIONS = [
  { id: 'voz_prompt', label: 'VOZ + MÚSICA DESDE PROMPT', needs: 'prompt', needsBpm: true },
  { id: 'solo_base', label: 'SOLO BASE NUEVA DESDE PROMPT', needs: 'prompt', needsBpm: true },
  { id: 'instrumental', label: 'INSTRUMENTAL (QUITAR VOCES)' },
  { id: 'acapella', label: 'ACAPELLA (SOLO LA VOZ)' },
  { id: 'loop4', label: 'LOOP DE 4 COMPASES' },
  { id: 'medio', label: 'MEDIO TIEMPO' },
  { id: 'doble', label: 'DOBLE TIEMPO' },
  { id: 'bpm', label: 'FORZAR TEMPO A', needs: 'bpm' },
];

export default function RemixActions({ fileName, onDone }) {
  const [open, setOpen] = useState(false);
  const [action, setAction] = useState('');
  const [prompt, setPrompt] = useState('');
  const [bpm, setBpm] = useState('');
  const [status, setStatus] = useState(null);  // {tone, text}
  const [busy, setBusy] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    if (!open) return undefined;
    const onDoc = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    document.addEventListener('mousedown', onDoc);
    return () => document.removeEventListener('mousedown', onDoc);
  }, [open]);

  const current = ACTIONS.find((a) => a.id === action);

  const pollRemix = async (jobId) => {
    // El remix con IA son varios pasos: se enseña el último (una línea).
    for (;;) {
      const job = await api.remixAiStatus(jobId);
      if (job.status === 'succeeded') return job;
      if (job.status === 'failed') throw new Error(job.error ?? 'El remix falló');
      setStatus({ tone: 'run', text: job.phase ?? 'Trabajando…' });
      await new Promise((r) => setTimeout(r, 2500));
    }
  };

  const run = async (id) => {
    setAction('');
    setBusy(true);
    setStatus({ tone: 'run', text: 'Trabajando…' });
    try {
      let result = null;
      if (id === 'voz_prompt' || id === 'solo_base') {
        if (prompt.trim().length < 3) {
          setStatus({ tone: 'err', text: 'Escribe un prompt para la música nueva' });
          return;
        }
        const started = await api.remixAi({
          file_name: fileName,
          prompt: prompt.trim(),
          keep_vocals: id === 'voz_prompt',
          bpm: bpm ? Number(bpm) : null,
        });
        const job = await pollRemix(started.job_id);
        result = job.result?.mix ?? job.result?.base;
        setStatus({ tone: 'ok', text: `Listo: ${result}` });
      } else if (id === 'instrumental' || id === 'acapella') {
        setStatus({ tone: 'run', text: 'Separando la voz (1-3 min la primera vez)…' });
        const res = await api.separate({ file_name: fileName, output_name: fileName.replace(/\.[^.]+$/, '') });
        result = id === 'instrumental' ? res.base : res.vocals;
        setStatus({ tone: 'ok', text: `Listo: ${result}` });
      } else if (id === 'medio' || id === 'doble') {
        const res = await api.setTempo({ file_name: fileName, mode: id });
        setStatus({ tone: 'ok', text: `${id === 'medio' ? 'Medio' : 'Doble'} tiempo: ${res.source_bpm} → ${res.result_bpm} bpm` });
        result = res.file_name;
      } else if (id === 'loop4') {
        const groove = await api.groove(fileName);
        const seconds = Math.min(120, Math.max(2, Math.round(240 / groove.bpm)));
        const res = await api.makeLoop({ file_name: fileName, seconds });
        result = res.file_name;
        setStatus({ tone: 'ok', text: `Loop de ${res.seconds}s a ${groove.bpm} bpm: ${result}` });
      } else if (id === 'bpm') {
        if (!bpm) { setStatus({ tone: 'err', text: 'Escribe el BPM objetivo' }); return; }
        const res = await api.setTempo({ file_name: fileName, mode: 'bpm', bpm: Number(bpm) });
        result = res.file_name;
        setStatus({ tone: 'ok', text: `${res.source_bpm} → ${res.result_bpm} bpm` });
      }
      if (result) onDone?.(result);
    } catch (e) {
      setStatus({ tone: 'err', text: e.message });
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center gap-2 flex-wrap">
        <span className="label shrink-0">REMIXER</span>
        <div className="relative" ref={ref}>
          <button onClick={() => setOpen((o) => !o)} disabled={busy}
            className={`btn h-8 px-2.5 gap-1.5 ${action ? 'btn-signal' : 'btn-ghost'}`}>
            <span className="mono text-[11px]">{current?.label ?? 'ACCIONES'}</span>
            <ChevronDown size={12} className={open ? 'rotate-180 transition-transform' : 'transition-transform'} />
          </button>
          {open && (
            <div className="absolute z-30 top-full left-0 mt-1 min-w-[260px] border border-[var(--line-strong)] bg-[var(--surface-2)] p-1 flex flex-col shadow-lg">
              {ACTIONS.map((a) => (
                <button key={a.id} onClick={() => { setOpen(false); run(a.id); }}
                  title={a.label}
                  className="text-left px-3 py-1.5 hover:bg-[var(--acc-dim)] text-zinc-200">
                  <span className="mono text-[11.5px]">{a.label}</span>
                </button>
              ))}
            </div>
          )}
        </div>

        {current?.needs === 'prompt' && (
          <input value={prompt} onChange={(e) => setPrompt(e.target.value)} placeholder="prompt de la música nueva: techno oscuro 130bpm…"
            className="px-3 py-1.5 text-[12px] mono bg-transparent outline-none border border-[var(--line)] focus:border-[var(--acc-line)] w-64" />
        )}
        {current?.needs === 'bpm' && (
          <input value={bpm} onChange={(e) => setBpm(e.target.value.replace(/[^0-9]/g, ''))} placeholder="bpm"
            className="px-2 py-1.5 w-20 text-[12px] mono bg-transparent outline-none border border-[var(--line)] focus:border-[var(--acc-line)]" />
        )}
        {busy && <Loader2 size={13} className="animate-spin text-[var(--acc)]" />}
      </div>

      {status && (
        <p className={`mono text-[10.5px] flex items-center gap-1.5 ${status.tone === 'ok' ? 'st-ok' : status.tone === 'err' ? 'st-err' : 'text-[var(--muted)]'}`}>
          {status.tone === 'ok' ? <Check size={11} /> : status.tone === 'err' ? <AlertTriangle size={11} /> : null}
          {status.text}
        </p>
      )}
    </div>
  );
}
