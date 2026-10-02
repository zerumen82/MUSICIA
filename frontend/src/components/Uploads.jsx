import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  Upload, Loader2, AlertTriangle, Trash2, Download, RefreshCw, Play, Pause,
  SlidersHorizontal, Music, Mic2, Sparkles, CheckCircle2, HelpCircle, Pencil, Check,
} from 'lucide-react';
import { api } from '../api';
import RemixPanel from './RemixPanel';
import RemixIAPanel from './RemixIAPanel';

const fmtBytes = (b) => (b > 1e6 ? `${(b / 1e6).toFixed(1)} MB` : `${Math.round(b / 1e3)} KB`);

const KIND_OPTIONS = [
  { id: 'musica', label: 'Solo música', icon: Music },
  { id: 'voz', label: 'Solo voz', icon: Mic2 },
  { id: 'mixta', label: 'Música + voz', icon: Sparkles },
  { id: 'otro', label: 'Otro / ambienta', icon: HelpCircle },
];

/* Acciones que la app ofrece según lo que el usuario confirma que es el audio. */
const ACTIONS_BY_KIND = {
  musica: [
    { id: 'remix', title: 'Remix del audio', desc: 'Tempo, tono, reverse, gain, fades — resultado instantáneo en local.' },
    { id: 'recreate', title: 'Re-crear con IA', desc: 'Genera una pista nueva inspirada en el análisis (duración, BPM, graves).' },
    { id: 'extend', title: 'Crear base similar', desc: 'Usa el BPM detectado y el carácter para crear algo en la misma línea.' },
  ],
  voz: [
    { id: 'remix', title: 'Procesar la voz', desc: 'Limpieza de niveles, tempo, recorte, fades — instantáneo en local.' },
    { id: 'backing', title: 'Crear base para la voz', desc: 'Genera con IA una base musical a medida del análisis de la voz.' },
  ],
  mixta: [
    { id: 'remix', title: 'Remix del audio', desc: 'Tempo, tono, reverse, gain, fades — instantáneo en local.' },
    { id: 'recreate', title: 'Re-creación IA', desc: 'Versión nueva del tema con el motor, usando BPM y carácter del análisis.' },
  ],
  otro: [
    { id: 'remix', title: 'Efectos sobre el audio', desc: 'Tempo, tono, reverse, gain, fades — instantáneo en local.' },
  ],
};

export default function Uploads() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [lastAnalysis, setLastAnalysis] = useState(null); // {file_name, analysis}
  const [confirmKind, setConfirmKind] = useState(null); // tipo confirmado por el usuario
  const [chosenAction, setChosenAction] = useState(null);
  const [playing, setPlaying] = useState(null);
  const [remixState, setRemixState] = useState(null); // resultado o error del remix
  const [generating, setGenerating] = useState(false);
  const [renameName, setRenameName] = useState(null); // item en renombrado
  const [renameValue, setRenameValue] = useState('');
  const inputRef = useRef(null);

  const refresh = useCallback(async () => {
    try {
      const data = await api.uploads();
      setItems(data.items ?? []);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void refresh(); }, [refresh]);

  const doUpload = async (file) => {
    setError(null);
    setRemixState(null);
    setLastAnalysis(null);
    setConfirmKind(null);
    setChosenAction(null);
    setUploading(true);
    setProgress(0);
    try {
      const res = await api.uploadAudio(file, (evt) => {
        if (evt.total) setProgress(Math.round((evt.loaded / evt.total) * 100));
      });
      setLastAnalysis(res);
    } catch (e) {
      setError(e.message);
    } finally {
      setUploading(false);
    }
  };

  const confirmType = (kind) => {
    setConfirmKind(kind);
    setChosenAction(null);
  };

  const runRemix = async (params) => {
    setError(null);
    setRemixState(null);
    try {
      const res = await api.remix({ file_name: lastAnalysis.file_name, ...params });
      setRemixState({ ok: true, ...res });
      await refresh();
    } catch (e) {
      setRemixState({ ok: false, error: e.message });
    }
  };

  // Lanza la re-creación con IA. Recibe { prompt, seed, duration_seconds, bpm }
  // desde RemixIAPanel (que pre-rellena con el análisis DSP); si falta algo,
  // cae al análisis local. Con semilla fija se pueden comparar versiones A/B.
  const runAIGeneration = async ({ prompt, seed = null, name = null, duration_seconds = null, bpm = null } = {}) => {
    setError(null);
    setGenerating(true);
    const a = lastAnalysis?.analysis ?? {};
    const dur = duration_seconds ?? a.duration_seconds ?? 30;
    try {
      const created = await api.generateMusic({
        prompt: (prompt ?? '').trim() || 'pieza musical inspirada en una referencia con carácter similar',
        // La re-creación es instrumental: sin letra no se puede pedir voz al motor
        instrumental: true,
        lyrics: null,
        duration_seconds: Math.min(Math.max(dur, 10), 240),
        bpm: bpm ?? a.bpm ?? null,
        seed,
        output_name: name,
      });
      setRemixState({
        ok: true, job: true, job_id: created.job_id,
        note: 'Generación IA lanzada con tu prompt. Mira el progreso en CREAR.',
      });
    } catch (e) {
      setRemixState({ ok: false, error: e.message });
    } finally {
      setGenerating(false);
    }
  };

  const commitRename = async (oldName) => {
    const next = renameValue.trim();
    setRenameName(null);
    if (!next || next === oldName) return;
    setError(null);
    try {
      const res = await api.renameAudio(oldName, next);
      // Si el renombrado es del audio analizado, el panel sigue apuntando al
      // fichero viejo: se actualiza al nombre real que devolvió la API.
      if (lastAnalysis?.file_name === oldName) {
        setLastAnalysis({ ...lastAnalysis, file_name: res.name });
      }
      if (playing === oldName) setPlaying(null);
      await refresh();
    } catch (e) {
      setError(e.message);
    }
  };

  const remove = async (name) => {
    try {
      await api.deleteUpload(name);
      if (playing === name) setPlaying(null);
      await refresh();
    } catch (e) {
      setError(e.message);
    }
  };

  return (
    <div className="h-full overflow-y-auto">
      <div className="max-w-[1300px] mx-auto w-full px-16 py-12 flex flex-col gap-6">
        {/* Cabecera + zona de subida */}
        <div className="flex items-center gap-4">
          <h2 className="h-title text-[20px]">AUDIO PROPIO</h2>
          <span className="mono text-[12px] text-[var(--faint)]">sube una canción: la analizo y tú decides</span>
          <button onClick={refresh} className="btn btn-ghost h-8 px-3 ml-auto"><RefreshCw size={12} /> ACTUALIZAR</button>
        </div>

        <div
          className="border border-dashed border-[var(--line-strong)] py-14 flex flex-col items-center gap-4 cursor-pointer hover:border-[var(--acc-line)] transition-colors"
          onClick={() => inputRef.current?.click()}
          onDragOver={(e) => e.preventDefault()}
          onDrop={(e) => {
            e.preventDefault();
            if (e.dataTransfer.files?.[0]) doUpload(e.dataTransfer.files[0]);
          }}
        >
          <input
            ref={inputRef} type="file" accept=".mp3,.wav,audio/mpeg,audio/wav" hidden
            onChange={(e) => { if (e.target.files?.[0]) doUpload(e.target.files[0]); e.target.value = ''; }}
          />
          {uploading ? (
            <>
              <Loader2 size={22} className="text-[var(--acc)] animate-spin" />
              <span className="mono text-[11px] text-[var(--muted)]">SUBIENDO… {progress}%</span>
            </>
          ) : (
            <>
              <Upload size={22} className="text-[var(--muted)]" />
              <span className="text-[13.5px] text-[var(--muted)]">Arrastra un <b className="text-zinc-300">.mp3</b> o <b className="text-zinc-300">.wav</b> aquí, o haz clic (máx. 50 MB)</span>
            </>
          )}
        </div>

        {error && (
          <div className="flex items-center gap-2 text-red-300 mono text-[11px] py-2 border-y border-[rgba(255,92,92,0.35)]">
            <AlertTriangle size={14} /> {error}
          </div>
        )}

        {/* ===== Análisis + preguntas ===== */}
        {lastAnalysis && (
          <div className="border border-[var(--acc-line)] bg-[var(--acc-dim)] p-5 flex flex-col gap-4 fade-up">
            <div className="flex items-center gap-3">
              <CheckCircle2 size={16} className="text-[var(--acc)]" />
              <span className="mono text-[11px] tracking-[0.1em] text-[var(--acc)]">
                ANÁLISIS DE {lastAnalysis.file_name.toUpperCase()}
              </span>
            </div>

            {/* Features reales */}
            <div className="flex flex-wrap gap-x-8 gap-y-2 mono text-[11px]">
              <span>duración <b className="text-[var(--acc)]">{lastAnalysis.analysis.duration_seconds}s</b></span>
              <span>bpm <b className="text-[var(--acc)]">{lastAnalysis.analysis.bpm ?? '—'}</b></span>
              <span>graves <b className="text-[var(--acc)]">{Math.round(lastAnalysis.analysis.bass_ratio * 100)}%</b></span>
              <span>loudness <b className="text-[var(--acc)]">{lastAnalysis.analysis.mean_loudness_dbfs} dBFS</b></span>
              <span>dinámica <b className="text-[var(--acc)]">±{lastAnalysis.analysis.dynamics_std_db} dB</b></span>
              <span>pausas <b className="text-[var(--acc)]">{Math.round(lastAnalysis.analysis.silence_ratio * 100)}%</b></span>
            </div>

            {/* Hipótesis del sistema */}
            <div className="flex flex-col gap-1.5">
              <span className="label">MI HIPÓTESIS · {lastAnalysis.analysis.hypothesis.kind.toUpperCase()} (confianza {lastAnalysis.analysis.hypothesis.confidence})</span>
              <div className="flex flex-wrap gap-1.5">
                {lastAnalysis.analysis.hypothesis.signals.map((s) => (
                  <span key={s} className="btn-chip">{s}</span>
                ))}
              </div>
            </div>

            {/* PREGUNTA 1: ¿qué es? */}
            <div className="flex flex-col gap-2">
              <span className="label">¿QUÉ ES ESTE AUDIO? (corrígeme si me equivoco)</span>
              <div className="flex flex-wrap gap-1.5">
                {KIND_OPTIONS.map(({ id, label, icon: Icon }) => (
                  <button key={id} onClick={() => confirmType(id)}
                    className={`btn h-8 px-3 ${confirmKind === id ? 'btn-signal' : 'btn-ghost'}`}>
                    <Icon size={12} /> {label}
                  </button>
                ))}
              </div>
            </div>

            {/* PREGUNTA 2: ¿qué hacemos? (aparece al confirmar) */}
            {confirmKind && (
              <div className="flex flex-col gap-2 border-t border-[var(--line)] pt-4">
                <span className="label">¿QUÉ QUEREMOS HACER CON ÉL?</span>
                <div className="flex flex-col gap-1.5">
                  {ACTIONS_BY_KIND[confirmKind].map(({ id, title, desc }) => (
                    <button key={id} onClick={() => setChosenAction(id)}
                      className={`text-left px-4 py-2.5 border transition-colors ${chosenAction === id ? 'border-[var(--acc-line)] bg-[var(--acc-dim)]' : 'border-[var(--line)] hover:border-[var(--line-strong)]'}`}>
                      <span className="block text-[13px] font-semibold text-zinc-200">{title}</span>
                      <span className="block mono text-[10px] text-[var(--faint)] mt-0.5">{desc}</span>
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* Acción elegida: panel específico */}
            {chosenAction === 'remix' && <RemixPanel onRun={runRemix} result={remixState} fileName={lastAnalysis.file_name} />}

            {(chosenAction === 'recreate' || chosenAction === 'backing' || chosenAction === 'extend') && (
              <RemixIAPanel fileName={lastAnalysis.file_name} kind={confirmKind}
                onLaunch={runAIGeneration} generating={generating} jobNote={remixState?.job ? remixState.note : null} />
            )}

            {remixState?.ok && !remixState.job && (
              <div className="border-t border-[var(--line)] pt-3 flex items-center gap-3">
                <Play size={13} className="text-[var(--acc)]" fill="currentColor" />
                <span className="mono text-[11px] text-[var(--acc)]">REMIX LISTO: {remixState.file_name} ({remixState.duration_seconds}s)</span>
                <a href={api.audioUrl(remixState.file_name)} download className="btn btn-ghost h-7 px-2.5"><Download size={11} /></a>
                <span className="mono text-[9.5px] text-[var(--faint)]">disponible también en BIBLIOTECA</span>
              </div>
            )}
            {remixState?.ok === false && (
              <p className="mono text-[10.5px] st-err">{remixState.error}</p>
            )}
          </div>
        )}

        {/* ===== Lista de subidas previas ===== */}
        <div className="flex items-center gap-4">
          <span className="label">SUBIDAS · {items.length}</span>
        </div>
        {loading && <p className="mono text-[11px] text-[var(--muted)] animate-pulse py-4">CARGANDO…</p>}
        {!loading && items.length === 0 && (
          <p className="mono text-[10px] text-[var(--faint)] py-4">AÚN NO HAS SUBIDO NADA.</p>
        )}
        <div className="flex flex-col">
          {items.map((item) => (
            <div key={item.name} className="flex items-center gap-4 py-2.5 px-3 -mx-3 border-b border-[var(--line)] hover:bg-[var(--surface-2)] transition-colors">
              <button onClick={() => setPlaying(playing === item.name ? null : item.name)}
                className={`w-7 h-7 rounded-[3px] flex items-center justify-center shrink-0 border ${playing === item.name ? 'bg-[var(--acc)] border-[var(--acc)]' : 'border-[var(--line-strong)]'}`}>
                {playing === item.name ? <Pause size={10} className="text-[#0c0f04]" fill="currentColor" />
                  : <Play size={10} className="text-[var(--muted)]" fill="currentColor" />}
              </button>
              {renameName === item.name ? (
                <>
                  <input autoFocus value={renameValue} onChange={(e) => setRenameValue(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') void commitRename(item.name);
                      if (e.key === 'Escape') setRenameName(null);
                    }}
                    className="px-3 py-1.5 text-[12px] mono bg-transparent outline-none border border-[var(--acc-line)] flex-1 min-w-0" />
                  <button onClick={() => void commitRename(item.name)} className="btn btn-signal h-7 px-2.5 shrink-0">
                    <Check size={11} /> GUARDAR
                  </button>
                  <button onClick={() => setRenameName(null)} className="btn btn-ghost h-7 px-2.5 shrink-0">CANCELAR</button>
                </>
              ) : (
                <>
                  <span className="mono text-[11.5px] text-zinc-200 truncate flex-1 min-w-0">{item.name}</span>
                  <button onClick={() => { setRenameValue(item.name.replace(/\.[^.]+$/, '')); setRenameName(item.name); }}
                    className="btn btn-ghost h-7 px-2 shrink-0" title="Cambiar nombre">
                    <Pencil size={11} />
                  </button>
                </>
              )}
              <span className="mono text-[10px] text-[var(--faint)] shrink-0">{fmtBytes(item.size_bytes)}</span>
              <a href={api.uploadUrl(item.name)} download className="btn btn-ghost h-7 px-2 shrink-0"><Download size={11} /></a>
              <button onClick={() => remove(item.name)} className="btn btn-ghost h-7 px-2 shrink-0 hover:!border-[rgba(255,92,92,0.5)] hover:!text-red-300"><Trash2 size={11} /></button>
            </div>
          ))}
        </div>
        {playing && (
          <audio key={playing} controls autoPlay src={api.uploadUrl(playing)} className="player"
            onEnded={() => setPlaying(null)} />
        )}
      </div>
    </div>
  );
}

/* Panel de remix DSP: sliders de tempo/pitch/gain + reverse + fades. */
/* Panel de re-creación con IA: ahora es RemixIAPanel (compartido con BIBLIOTECA). */
