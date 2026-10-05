import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  Upload, Loader2, AlertTriangle, Trash2, Download, RefreshCw, Play, Pause,
  Music, Mic2, Sparkles, CheckCircle2, HelpCircle, Pencil, Check,
} from 'lucide-react';
import { api, isTransportBlip } from '../api';
import RemixIAPanel from './RemixIAPanel';
import RemixActions from './RemixActions';
import { structureLyric } from '../vocal';

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
    { id: 'remix', title: 'Remix del audio', desc: 'Abre el remixer: versión, voz, tempo, loop y el ajuste local.' },
    { id: 'recreate', title: 'Re-crear con IA', desc: 'Versión nueva sobre este audio, con el prompt que escribas.' },
    { id: 'extend', title: 'Rehacer un tramo', desc: 'Regenera un trozo de esta pista. El resto se queda.' },
  ],
  voz: [
    { id: 'remix', title: 'Procesar la voz', desc: 'Abre el remixer sobre esta voz.' },
    { id: 'backing', title: 'Crear base para la voz', desc: 'Base nueva, de la misma duración que este audio, con el prompt que escribas.' },
  ],
  mixta: [
    { id: 'remix', title: 'Remix del audio', desc: 'Abre el remixer: versión, voz, tempo, loop y el ajuste local.' },
    { id: 'recreate', title: 'Re-creación IA', desc: 'Versión nueva del tema, con el prompt que escribas.' },
  ],
  otro: [
    { id: 'remix', title: 'Efectos sobre el audio', desc: 'Abre el remixer sobre este audio.' },
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
  const [remixName, setRemixName] = useState(null); // subida abierta en la mesa de remix
  const inputRef = useRef(null);

  const refresh = useCallback(async () => {
    try {
      const data = await api.uploads();
      setItems(data.items ?? []);
    } catch (e) {
      if (!isTransportBlip(e.message)) setError(e.message);
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

  // Re-creación: cover del audio, sin duración y sin el BPM medido.
  // Crear base: pieza nueva de la duración del audio. El BPM medido no se manda.
  const runAIGeneration = async ({ prompt, seed = null, name = null, lyrics = null, duration_seconds = null, bpm = null, source_kind = null } = {}) => {
    setError(null);
    const text = (prompt ?? '').trim();
    if (!text) {
      setError('Escribe un prompt antes de la versión');
      return;
    }
    setGenerating(true);
    const a = lastAnalysis?.analysis ?? {};
    const letra = lyrics ? structureLyric(lyrics) : null;
    const esBaseNueva = chosenAction === 'backing';
    let duration = null;
    if (esBaseNueva) {
      const measured = Number(duration_seconds ?? a.duration_seconds);
      if (Number.isFinite(measured) && measured > 0) {
        const cfg = await api.musicConfig().catch(() => null);
        const max = Number(cfg?.max_duration_seconds);
        duration = Number.isFinite(max) && max > 0 ? Math.min(measured, max) : measured;
      }
    }
    try {
      const created = await api.generateMusic({
        prompt: text,
        instrumental: !letra,
        lyrics: letra,
        bpm: bpm ?? null,
        seed,
        output_name: name,
        ...(esBaseNueva
          ? { duration_seconds: duration }
          : { source_name: lastAnalysis.file_name, source_kind: source_kind ?? 'upload', task_type: 'cover' }),
      });
      setRemixState({
        ok: true, job: true, job_id: created.job_id,
        note: esBaseNueva
          ? 'Base nueva lanzada. El progreso está en la barra de arriba.'
          : 'Versión lanzada sobre este audio. El progreso está en la barra de arriba.',
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
      const res = await api.renameAudio(oldName, next, 'upload');
      // Si el renombrado es del audio analizado, el panel sigue apuntando al
      // fichero viejo: se actualiza al nombre real que devolvió la API.
      if (lastAnalysis?.file_name === oldName) {
        setLastAnalysis({ ...lastAnalysis, file_name: res.name });
      }
      if (remixName === oldName) setRemixName(res.name);
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
      if (remixName === name) setRemixName(null);
      await refresh();
    } catch (e) {
      setError(e.message);
    }
  };

  return (
    <div className="h-full overflow-y-auto">
      <div className="max-w-[1300px] mx-auto w-full px-6 py-8 xl:px-10 flex flex-col gap-6">
        {/* Cabecera + zona de subida */}
        <div className="flex items-center gap-4">
          <h2 className="h-title text-[20px]">AUDIO PROPIO</h2>
          <span className="mono text-[12px] text-[var(--faint)]">sube una canción: la analizo y tú decides</span>
          <button onClick={refresh} className="btn btn-ghost h-8 px-3 ml-auto"><RefreshCw size={12} /> ACTUALIZAR</button>
        </div>

        <div
          className={`border border-dashed border-[var(--line-strong)] flex flex-col items-center cursor-pointer hover:border-[var(--acc-line)] transition-colors ${lastAnalysis ? 'py-4 gap-2' : 'py-14 gap-4'}`}
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
              <span className="text-[13.5px] text-[var(--muted)] text-center px-4">
                {lastAnalysis
                  ? 'Subir otro .mp3 o .wav'
                  : <>Arrastra un <b className="text-zinc-300">.mp3</b> o <b className="text-zinc-300">.wav</b> aquí, o haz clic (máx. 50 MB)</>}
              </span>
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
                    className={`btn btn-ghost h-8 px-3 ${confirmKind === id ? '!border-[var(--acc-line)] !text-[var(--text)]' : ''}`}>
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
            {chosenAction === 'remix' && (
              <RemixActions fileName={lastAnalysis.file_name} sourceKind="upload" onDone={async () => {
                await refresh();
                setRemixState(null);
              }} />
            )}
            {chosenAction === 'extend' && (
              <RemixActions fileName={lastAnalysis.file_name} sourceKind="upload" initialAction="tramo" onDone={async () => {
                await refresh();
              }} />
            )}

            {(chosenAction === 'recreate' || chosenAction === 'backing') && (
              <RemixIAPanel fileName={lastAnalysis.file_name} kind={confirmKind} sourceKind="upload"
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
            <div key={item.name} className="border-b border-[var(--line)]">
              <div className={`flex items-center gap-4 py-2.5 px-3 -mx-3 hover:bg-[var(--surface-2)] transition-colors ${remixName === item.name ? 'bg-[var(--surface-2)]' : ''}`}>
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
                {renameName !== item.name && (
                  <button
                    type="button"
                    onClick={() => setRemixName(remixName === item.name ? null : item.name)}
                    className={`btn btn-ghost h-7 px-2.5 shrink-0 ${remixName === item.name ? '!border-[var(--acc-line)] !text-[var(--text)]' : ''}`}
                  >
                    REMIX
                  </button>
                )}
                <span className="mono text-[10px] text-[var(--faint)] shrink-0">{fmtBytes(item.size_bytes)}</span>
                <a href={api.uploadUrl(item.name)} download className="btn btn-ghost h-7 px-2 shrink-0"><Download size={11} /></a>
                <button onClick={() => remove(item.name)} className="btn btn-ghost h-7 px-2 shrink-0 hover:!border-[rgba(255,92,92,0.5)] hover:!text-red-300"><Trash2 size={11} /></button>
              </div>
              {remixName === item.name && (
                <div className="px-3 pb-4 pt-1 bg-[var(--surface-2)]">
                  <RemixActions fileName={item.name} sourceKind="upload" onDone={() => { void refresh(); }} />
                </div>
              )}
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
