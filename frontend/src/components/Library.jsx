import React, { useCallback, useEffect, useState } from 'react';
import {
  Play, Pause, Trash2, Download, RefreshCw, SlidersHorizontal, Loader2, AlertTriangle, Shuffle, Sparkles, Pencil, Check,
} from 'lucide-react';
import { api, API_BASE_URL } from '../api';
import RemixPanel from './RemixPanel';
import RemixIAPanel from './RemixIAPanel';

const fmtBytes = (b) => (b > 1e6 ? `${(b / 1e6).toFixed(1)} MB` : `${Math.round(b / 1e3)} KB`);
const fmtDate = (iso) => new Date(iso).toLocaleString();

const EMPTY_FORM = { gain_db: 0, fade_in_ms: 0, fade_out_ms: 0, trim_start_s: 0, trim_end_s: '' };

export default function Library() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [playing, setPlaying] = useState(null); // name del MP3 sonando
  const [editName, setEditName] = useState(null); // name en edición
  const [remixName, setRemixName] = useState(null); // name en remix
  const [iaName, setIaName] = useState(null); // name en re-creación IA
  const [iaBusy, setIaBusy] = useState(false);
  const [iaNote, setIaNote] = useState(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [renameName, setRenameName] = useState(null); // item en renombrado
  const [renameValue, setRenameValue] = useState('');
  const [processing, setProcessing] = useState(false);

  const refresh = useCallback(async () => {
    setError(null);
    try {
      const data = await api.library();
      setItems(data.items ?? []);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void refresh(); }, [refresh]);

  const toggle = (name) => setPlaying((cur) => (cur === name ? null : name));

  const commitRename = async (oldName) => {
    const next = renameValue.trim();
    setRenameName(null);
    if (!next || next === oldName) return;
    setError(null);
    try {
      await api.renameAudio(oldName, next);
      if (playing === oldName) setPlaying(null);
      await refresh();
    } catch (e) {
      setError(e.message);
    }
  };

  // Re-creación IA de una pista de la biblioteca: mismo panel que en SUBIR.
  const runIAFromLibrary = async ({ prompt, seed = null, name = null, duration_seconds = null, bpm = null } = {}) => {
    setError(null);
    setIaBusy(true);
    setIaNote(null);
    try {
      const created = await api.generateMusic({
        prompt: (prompt ?? '').trim() || 'pieza musical inspirada en una referencia con carácter similar',
        instrumental: true,
        lyrics: null,
        duration_seconds: Math.min(Math.max(duration_seconds ?? 30, 10), 240),
        bpm: bpm ?? null,
        seed,
        output_name: name,
      });
      setIaNote(`Versión lanzada (tarea ${created.job_id}). Mira el progreso en CREAR; al terminar estará aquí.`);
    } catch (e) {
      setError(e.message);
    } finally {
      setIaBusy(false);
    }
  };

  const remove = async (name) => {
    setError(null);
    try {
      await api.deleteAudio(name);
      if (playing === name) setPlaying(null);
      await refresh();
    } catch (e) {
      setError(e.message);
    }
  };

  const applyProcess = async () => {
    if (!editName) return;
    setProcessing(true);
    setError(null);
    try {
      const res = await api.processAudio({
        file_name: editName,
        gain_db: Number(form.gain_db),
        fade_in_ms: Number(form.fade_in_ms),
        fade_out_ms: Number(form.fade_out_ms),
        trim_start_s: Number(form.trim_start_s),
        trim_end_s: form.trim_end_s === '' ? null : Number(form.trim_end_s),
      });
      setEditName(null);
      setForm(EMPTY_FORM);
      setPlaying(null);
      await refresh();
      // auto-play del resultado
      setPlaying(res.file_name);
    } catch (e) {
      setError(e.message);
    } finally {
      setProcessing(false);
    }
  };

  const openEditor = (name) => {
    setEditName((cur) => (cur === name ? null : name));
    setForm(EMPTY_FORM);
    setError(null);
  };

  return (
    <div className="h-full overflow-y-auto">
      <div className="max-w-[1300px] mx-auto w-full px-16 py-12 flex flex-col gap-6">
        {/* Cabecera */}
        <div className="flex items-center gap-4">
          <h2 className="h-title text-[20px]">BIBLIOTECA</h2>
          <span className="mono text-[12px] text-[var(--faint)]">{items.length} archivos · backend/outputs/</span>          <button onClick={refresh} className="btn btn-ghost h-8 px-3 ml-auto"><RefreshCw size={12} /> ACTUALIZAR</button>
        </div>

        {error && (
          <div className="flex items-center gap-2 text-red-300 mono text-[11px] py-2 border-y border-[rgba(255,92,92,0.35)]">
            <AlertTriangle size={14} /> {error}
          </div>
        )}

        {loading && <p className="mono text-[11px] text-[var(--muted)] animate-pulse py-6">CARGANDO BIBLIOTECA…</p>}

        {!loading && items.length === 0 && (
          <p className="mono text-[11px] text-[var(--faint)] py-10 text-center leading-relaxed">
            BIBLIOTECA VACÍA.<br />GENERA UNA PISTA EN CREAR.
          </p>
        )}

        {/* Lista */}
        <div className="flex flex-col">
          {items.map((item) => (
            <div key={item.name} className="border-b border-[var(--line)]">
              <div className={`flex items-center gap-5 py-4 px-4 transition-colors ${playing === item.name ? 'bg-[var(--acc-dim)]' : 'hover:bg-[var(--surface-2)]'}`}>
                <button onClick={() => toggle(item.name)}
                  className={`w-11 h-11 rounded-[4px] flex items-center justify-center shrink-0 border ${playing === item.name ? 'bg-[var(--acc)] border-[var(--acc)]' : 'border-[var(--line-strong)] hover:border-[var(--faint)]'}`}>
                  {playing === item.name ? <Pause size={15} className="text-[#0c0f04]" fill="currentColor" />
                    : <Play size={15} className="text-[var(--muted)]" fill="currentColor" />}
                </button>
                {renameName === item.name ? (
                  <>
                    <input autoFocus value={renameValue} onChange={(e) => setRenameValue(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') void commitRename(item.name);
                        if (e.key === 'Escape') setRenameName(null);
                      }}
                      className="px-3 py-1.5 text-[13px] mono bg-transparent outline-none border border-[var(--acc-line)] flex-1 min-w-0" />
                    <button onClick={() => void commitRename(item.name)} className="btn btn-signal h-8 px-2.5 shrink-0">
                      <Check size={11} /> GUARDAR
                    </button>
                    <button onClick={() => setRenameName(null)} className="btn btn-ghost h-8 px-2.5 shrink-0">CANCELAR</button>
                  </>
                ) : (
                  <>
                    <span className="mono text-[13.5px] text-zinc-200 truncate flex-1 min-w-0">{item.name}</span>
                    <button onClick={() => { setRenameValue(item.name.replace(/\.[^.]+$/, '')); setRenameName(item.name); }}
                      className="btn btn-ghost h-8 px-2.5 shrink-0" title="Cambiar nombre">
                      <Pencil size={12} />
                    </button>
                  </>
                )}
                <span className="mono text-[10px] text-[var(--faint)] shrink-0">{fmtBytes(item.size_bytes)}</span>
                <span className="mono text-[10px] text-[var(--faint)] shrink-0 hidden md:block">{fmtDate(item.modified)}</span>
                <button onClick={() => { setEditName(null); setIaName(null); setRemixName(remixName === item.name ? null : item.name); }}
                  className={`btn h-8 px-2.5 shrink-0 ${remixName === item.name ? 'btn-signal' : 'btn-ghost'}`} title="Remix">
                  <Shuffle size={12} />
                </button>
                <button onClick={() => { setEditName(null); setRemixName(null); setIaName(iaName === item.name ? null : item.name); }}
                  className={`btn h-8 px-2.5 shrink-0 ${iaName === item.name ? 'btn-signal' : 'btn-ghost'}`} title="Otra versión con IA">
                  <Sparkles size={12} />
                </button>
                <button onClick={() => { setRemixName(null); openEditor(item.name); }} className="btn btn-ghost h-8 px-2.5 shrink-0" title="Ajustes">
                  <SlidersHorizontal size={12} />
                </button>
                <a href={`${API_BASE_URL}/music/audio/${encodeURIComponent(item.name)}`} download className="btn btn-ghost h-8 px-2.5 shrink-0" title="Descargar">
                  <Download size={12} />
                </a>
                <button onClick={() => remove(item.name)} className="btn btn-ghost h-8 px-2.5 shrink-0 hover:!border-[rgba(255,92,92,0.5)] hover:!text-red-300" title="Borrar">
                  <Trash2 size={12} />
                </button>
              </div>

              {/* Reproductor inline */}
              {playing === item.name && (
                <div className="px-3 pb-4 -mt-1">
                  <audio key={item.name} controls autoPlay src={api.audioUrl(item.name)} className="player"
                    onEnded={() => setPlaying(null)} />
                </div>
              )}

              {/* Re-creación IA de esta pista (encadenable: cada versión vuelve a la biblioteca) */}
              {iaName === item.name && (
                <div className="px-3 pb-5 pt-1 bg-[var(--surface-2)] border-y border-[var(--line)]">
                  <span className="label block mb-1">OTRA VERSIÓN CON IA · {item.name}</span>
                  <RemixIAPanel fileName={item.name} kind="musica"
                    onLaunch={runIAFromLibrary} generating={iaBusy} jobNote={iaName === item.name ? iaNote : null} />
                </div>
              )}

              {/* Remix de esta pista (encadenable: el resultado vuelve a la biblioteca) */}
              {remixName === item.name && (
                <div className="px-3 pb-5 pt-1 bg-[var(--surface-2)] border-y border-[var(--line)]">
                  <span className="label block mb-1">REMIX · {item.name}</span>
                  <RemixPanel
                    fileName={item.name}
                    onRun={async (params) => {
                      setError(null);
                      try {
                        await api.remix({ file_name: item.name, ...params });
                        await refresh();
                        setRemixName(null);
                      } catch (e) {
                        setError(e.message);
                      }
                    }}
                  />
                </div>
              )}

              {/* Editor de post-proceso */}
              {editName === item.name && (
                <div className="px-3 pb-5 pt-1 flex flex-col gap-3 bg-[var(--surface-2)] border-y border-[var(--line)]">
                  <span className="label">AJUSTES · {item.name}</span>
                  <div className="flex items-center gap-6 flex-wrap">
                    <div className="flex items-center gap-2.5 min-w-[220px] flex-1">
                      <span className="label shrink-0">VOLUMEN</span>
                      <input type="range" min={-24} max={24} step={1} value={form.gain_db}
                        onChange={(e) => setForm({ ...form, gain_db: Number(e.target.value) })} className="flex-1" />
                      <span className={`num w-14 text-right ${form.gain_db > 0 ? 'st-warn' : ''}`}>{form.gain_db > 0 ? '+' : ''}{form.gain_db} dB</span>
                    </div>
                    <div className="flex items-center gap-2.5">
                      <span className="label shrink-0">FUNDIDO ENTRADA</span>
                      <input type="range" min={0} max={8000} step={250} value={form.fade_in_ms}
                        onChange={(e) => setForm({ ...form, fade_in_ms: Number(e.target.value) })} className="w-28" />
                      <span className="num w-16 text-right">{form.fade_in_ms / 1000}s</span>
                    </div>
                    <div className="flex items-center gap-2.5">
                      <span className="label shrink-0">FUNDIDO SALIDA</span>
                      <input type="range" min={0} max={8000} step={250} value={form.fade_out_ms}
                        onChange={(e) => setForm({ ...form, fade_out_ms: Number(e.target.value) })} className="w-28" />
                      <span className="num w-16 text-right">{form.fade_out_ms / 1000}s</span>
                    </div>
                  </div>
                  <div className="flex items-center gap-6 flex-wrap">
                    <div className="flex items-center gap-2.5">
                      <span className="label shrink-0">INICIO</span>
                      <input type="text" value={form.trim_start_s}
                        onChange={(e) => setForm({ ...form, trim_start_s: e.target.value.replace(/[^0-9.]/g, '') })}
                        className="w-16 px-2 py-1 text-center" /> <span className="mono text-[10px] text-[var(--faint)]">s</span>
                    </div>
                    <div className="flex items-center gap-2.5">
                      <span className="label shrink-0">FIN</span>
                      <input type="text" value={form.trim_end_s} placeholder="final"
                        onChange={(e) => setForm({ ...form, trim_end_s: e.target.value.replace(/[^0-9.]/g, '') })}
                        className="w-16 px-2 py-1 text-center" /> <span className="mono text-[10px] text-[var(--faint)]">s</span>
                    </div>
                    <div className="flex items-center gap-2 ml-auto">
                      <button onClick={() => setEditName(null)} className="btn btn-ghost h-8 px-3">CANCELAR</button>
                      <button onClick={applyProcess} disabled={processing} className="btn btn-signal h-8 px-4">
                        {processing ? <Loader2 size={12} className="animate-spin" /> : null} APLICAR
                      </button>
                    </div>
                  </div>
                  <p className="mono text-[9.5px] text-[var(--faint)]">
                    Crea un MP3 nuevo (nombre -edit.mp3); el original no se toca.
                  </p>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
