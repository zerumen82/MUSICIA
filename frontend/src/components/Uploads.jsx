import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  Upload, Loader2, AlertTriangle, Trash2, Download, RefreshCw, Play, Pause, Pencil, Check,
} from 'lucide-react';
import { api, actionError, isTransportBlip, JOB_POLL_INTERVAL_MS, JOB_POLL_MAX_MISSES, TRANSPORT_ERROR_CLEAR_MS } from '../api';
import { identifyReading } from '../identify_reading';
import RemixIAPanel from './RemixIAPanel';
import RemixActions from './RemixActions';

const fmtBytes = (b) => (b > 1e6 ? `${(b / 1e6).toFixed(1)} MB` : `${Math.round(b / 1e3)} KB`);

export default function Uploads({ onChanged }) {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [lastAnalysis, setLastAnalysis] = useState(null); // {file_name, analysis}
  const [playing, setPlaying] = useState(null);
  const [remixState, setRemixState] = useState(null); // resultado o error del remix
  const [generating, setGenerating] = useState(false);
  const [renameName, setRenameName] = useState(null); // item en renombrado
  const [renameValue, setRenameValue] = useState('');
  const [remixName, setRemixName] = useState(null); // subida abierta en la mesa de remix
  const [confirmDelete, setConfirmDelete] = useState(null); // subida pendiente de confirmar
  const [identify, setIdentify] = useState({});
  const inputRef = useRef(null);
  const alive = useRef(true);

  const refresh = useCallback(async () => {
    while (alive.current) {
      try {
        const data = await api.uploads();
        if (alive.current) setItems(data.items ?? []);
        return;
      } catch (e) {
        if (!alive.current) return;
        if (!isTransportBlip(e.message)) { setError(actionError(e.message)); return; }
        await new Promise((resolve) => setTimeout(resolve, TRANSPORT_ERROR_CLEAR_MS));
      } finally {
        if (alive.current) setLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    alive.current = true;
    void refresh();
    return () => { alive.current = false; };
  }, [refresh]);

  const identifyBusy = Object.values(identify).some((item) => item.status === 'running');

  const identifyFile = async (name) => {
    setIdentify((current) => ({ ...current, [name]: { status: 'running', phase: 'Esperando análisis', message: '' } }));
    while (alive.current) {
      try {
        const started = await api.remixAnalyze({ source_name: name, source_kind: 'upload' });
        let misses = 0;
        for (;;) {
          if (!alive.current) return;
          let job;
          try {
            job = await api.remixAnalyzeStatus(started.job_id);
            misses = 0;
          } catch (err) {
            if (isTransportBlip(err.message)) {
              // La API puede haberse reiniciado: busca el trabajo antes de seguir fallando.
              try {
                const found = await api.findJob(started.job_id);
                if (found) {
                  misses = 0;
                  if (found.status === 'failed' && /Interrumpido|reinici/i.test(found.error ?? '')) {
                    setIdentify((current) => ({ ...current, [name]: { status: 'failed', phase: '', message: 'La API se reinició y se perdió el trabajo en curso. Vuelve a intentarlo.' } }));
                    return;
                  }
                  if (found.status === 'succeeded') {
                    setIdentify((current) => ({ ...current, [name]: { status: 'succeeded', phase: '', message: identifyReading(found.result) } }));
                    return;
                  }
                  if (found.status === 'failed') {
                    setIdentify((current) => ({ ...current, [name]: { status: 'failed', phase: '', message: found.error || 'El análisis falló' } }));
                    return;
                  }
                  continue;
                }
              } catch {
                // La API sigue caída.
              }
              await new Promise((resolve) => setTimeout(resolve, TRANSPORT_ERROR_CLEAR_MS));
              continue;
            }
            if (++misses >= JOB_POLL_MAX_MISSES) throw err;
            await new Promise((resolve) => setTimeout(resolve, JOB_POLL_INTERVAL_MS));
            continue;
          }
          if (!alive.current) return;
          if (job.status === 'failed') throw new Error(job.error || 'El análisis falló');
          if (job.status === 'succeeded') {
            setIdentify((current) => ({ ...current, [name]: { status: 'succeeded', phase: '', message: identifyReading(job.result) } }));
            return;
          }
          setIdentify((current) => ({ ...current, [name]: { status: 'running', phase: job.phase || 'El modelo local analiza el audio', message: '' } }));
          await new Promise((resolve) => setTimeout(resolve, JOB_POLL_INTERVAL_MS));
        }
      } catch (err) {
        if (!alive.current) return;
        if (!isTransportBlip(err.message)) {
          setIdentify((current) => ({ ...current, [name]: { status: 'failed', phase: '', message: err.message } }));
          return;
        }
        await new Promise((resolve) => setTimeout(resolve, TRANSPORT_ERROR_CLEAR_MS));
      }
    }
  };

  const doUpload = async (file) => {
    setError(null);
    setRemixState(null);
    setLastAnalysis(null);
    setUploading(true);
    setProgress(0);
    try {
      const res = await api.uploadAudio(file, (evt) => {
        if (evt.total) setProgress(Math.round((evt.loaded / evt.total) * 100));
      });
      setLastAnalysis(res);
      setRemixName(res.file_name);
      await refresh();
      onChanged?.();
    } catch (e) {
      setError(actionError(e.message));
    } finally {
      setUploading(false);
    }
  };

  // El formulario prepara una sola petición para preview y envío, sin recomponerla.
  const runAIGeneration = async (request) => {
    setError(null);
    setGenerating(true);
    try {
      const created = await api.generateMusic(request);
      setRemixState({
        ok: true, job: true, job_id: created.job_id,
        note: 'Base nueva lanzada. El progreso está en la barra de arriba.',
      });
    } catch (e) {
      const message = actionError(e.message);
      if (message) setRemixState({ ok: false, error: message });
      throw e;
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
      onChanged?.();
    } catch (e) {
      setError(actionError(e.message));
    }
  };

  const remove = async (name) => {
    try {
      await api.deleteUpload(name);
      if (playing === name) setPlaying(null);
      if (remixName === name) setRemixName(null);
      if (lastAnalysis?.file_name === name) setLastAnalysis(null);
      setConfirmDelete(null);
      await refresh();
      onChanged?.();
    } catch (e) {
      setError(actionError(e.message));
    }
  };

  return (
    <div className="h-full overflow-y-auto">
      <div className="max-w-[1300px] mx-auto w-full px-6 py-8 xl:px-10 flex flex-col gap-6">
        {/* Cabecera + zona de subida */}
        <div className="flex items-center gap-4">
          <h2 className="h-title text-[20px]">AUDIO PROPIO</h2>
          <span className="mono text-[12px] text-[var(--faint)]">remix: arrastra una canción aquí, o haz clic</span>
          <button onClick={refresh} className="btn btn-ghost h-8 px-3 ml-auto"><RefreshCw size={12} /> ACTUALIZAR</button>
        </div>

        <div
          role="button" tabIndex={uploading ? -1 : 0} aria-label="Remix: archivo MP3 o WAV" aria-disabled={uploading}
          className={`border border-dashed border-[var(--line-strong)] flex flex-col items-center cursor-pointer hover:border-[var(--acc-line)] transition-colors ${lastAnalysis ? 'py-4 gap-2' : 'py-14 gap-4'}`}
          onClick={() => { if (!uploading) inputRef.current?.click(); }}
          onKeyDown={(e) => {
            if (e.key === 'Enter' || e.key === ' ') {
              e.preventDefault();
              if (!uploading) inputRef.current?.click();
            }
          }}
          onDragOver={(e) => e.preventDefault()}
          onDrop={(e) => {
            e.preventDefault();
            if (!uploading && e.dataTransfer.files?.[0]) doUpload(e.dataTransfer.files[0]);
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
                  ? 'Remix: otro .mp3 o .wav'
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
            <span className="mono text-[11px] tracking-[0.1em] text-[var(--acc)]">{lastAnalysis.file_name}</span>
            <div className="flex flex-wrap gap-x-8 gap-y-2 mono text-[11px]">
              <span>duración <b className="text-[var(--acc)]">{lastAnalysis.analysis.duration_seconds}s</b></span>
              <span>bpm <b className="text-[var(--acc)]">{lastAnalysis.analysis.bpm ?? '—'}</b></span>
              <span>loudness <b className="text-[var(--acc)]">{lastAnalysis.analysis.mean_loudness_dbfs} dBFS</b></span>
            </div>
            <details data-new-backing>
              <summary className="label cursor-pointer">ACOMPAÑAMIENTO NUEVO</summary>
              <RemixIAPanel fileName={lastAnalysis.file_name} sourceKind="upload" sourceDuration={lastAnalysis.analysis.duration_seconds}
                createBacking onLaunch={runAIGeneration} generating={generating} jobNote={remixState?.job ? remixState.note : null} />
            </details>

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

        {remixName && (
          <div className="border border-[var(--line)] bg-[var(--surface)] p-4">
            <RemixActions fileName={remixName} sourceKind="upload" onDone={() => { void refresh(); }} />
          </div>
        )}

        {/* ===== Lista de subidas previas ===== */}
        <div className="flex items-center gap-4">
          <span className="label">REMIX · {items.length}</span>
        </div>
        {loading && <p className="mono text-[11px] text-[var(--muted)] animate-pulse py-4">CARGANDO…</p>}
        {!loading && items.length === 0 && (
          <p className="mono text-[10px] text-[var(--faint)] py-4">NINGÚN REMIX AÚN.</p>
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
                  <>
                    <button
                      type="button"
                      onClick={() => setRemixName(remixName === item.name ? null : item.name)}
                      className={`btn btn-ghost h-7 px-2.5 shrink-0 ${remixName === item.name ? '!border-[var(--acc-line)] !text-[var(--text)]' : ''}`}
                    >
                      REMIX
                    </button>
                    <button
                      type="button"
                      disabled={identifyBusy}
                      onClick={() => void identifyFile(item.name)}
                      className="btn btn-ghost h-7 px-2.5 shrink-0"
                    >
                      {identify[item.name]?.status === 'running' ? <Loader2 size={11} className="animate-spin" /> : null}
                      IDENTIFY
                    </button>
                  </>
                )}
                <span className="mono text-[10px] text-[var(--faint)] shrink-0">{fmtBytes(item.size_bytes)}</span>
                <a href={api.uploadUrl(item.name)} download className="btn btn-ghost h-7 px-2 shrink-0"><Download size={11} /></a>
                {confirmDelete === item.name ? (
                  <>
                    <button onClick={() => void remove(item.name)} className="btn btn-ghost h-7 px-2 shrink-0 !border-[rgba(255,92,92,0.5)] !text-red-300">SÍ</button>
                    <button onClick={() => setConfirmDelete(null)} className="btn btn-ghost h-7 px-2 shrink-0">NO</button>
                  </>
                ) : (
                  <button onClick={() => setConfirmDelete(item.name)} className="btn btn-ghost h-7 px-2 shrink-0 hover:!border-[rgba(255,92,92,0.5)] hover:!text-red-300"><Trash2 size={11} /></button>
                )}
              </div>
              {identify[item.name]?.status === 'running' && (
                <p role="status" className="mono text-[11px] text-[var(--muted)] px-3 pb-2">{identify[item.name].phase}</p>
              )}
              {identify[item.name]?.message && (
                <p role={identify[item.name].status === 'failed' ? 'alert' : 'status'} className={`mono text-[11px] px-3 pb-2 ${identify[item.name].status === 'failed' || identify[item.name].message.startsWith('No está') || identify[item.name].message.startsWith('El modelo no') ? 'st-err' : 'text-[var(--acc)]'}`}>{identify[item.name].message}</p>
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
