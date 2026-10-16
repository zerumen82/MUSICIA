import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  Play, Pause, Trash2, Download, RefreshCw, SlidersHorizontal, Loader2, AlertTriangle, Sparkles, Pencil, Check, ChevronDown, CheckSquare, Square, X,
} from 'lucide-react';
import { api, actionError, isTransportBlip, TRANSPORT_ERROR_CLEAR_MS } from '../api';
import RemixActions from './RemixActions';

const fmtBytes = (b) => (b > 1e6 ? `${(b / 1e6).toFixed(1)} MB` : `${Math.round(b / 1e3)} KB`);
const fmtDate = (iso) => new Date(iso).toLocaleString();

const EMPTY_FORM = { gain_db: 0, fade_in_ms: 0, fade_out_ms: 0, trim_start_s: 0, trim_end_s: '' };

// La ficha guarda jerga del motor; la fila enseña palabras.
const TASK_LABEL = {
  text2music: 'crear', cover: 'versión', repaint: 'tramo', remix: 'remix',
  vocals: 'voz', instrumental: 'base', tempo: 'tempo', loop: 'loop', edit: 'ajuste',
};

export default function Library({ externalRefresh = 0 }) {
  const mounted = useRef(true);
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [playing, setPlaying] = useState(null); // name del MP3 sonando
  const [editName, setEditName] = useState(null); // name en edición
  const [iaName, setIaName] = useState(null); // name en re-creación IA
  const [form, setForm] = useState(EMPTY_FORM);
  const [renameName, setRenameName] = useState(null); // item en renombrado
  const [renameValue, setRenameValue] = useState('');
  const [menuName, setMenuName] = useState(null); // item con el menú ACCIONES abierto
  const [confirmDelete, setConfirmDelete] = useState(null);

  // El menú ACCIONES se cierra con clic fuera o Escape (antes se quedaba
  // abierto sin forma de ocultarlo salvo re-pulsar el botón).
  useEffect(() => {
    if (!menuName) return undefined;
    const onDown = (e) => {
      if (e.target.closest('[data-acciones]')) return;
      setMenuName(null);
    };
    const onKey = (e) => {
      if (e.key === 'Escape') setMenuName(null);
    };
    document.addEventListener('mousedown', onDown);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onDown);
      document.removeEventListener('keydown', onKey);
    };
  }, [menuName]);
  const [processing, setProcessing] = useState(false);
  // Tempo medido por pista (GET /audio/groove, DSP local): se mide a mano,
  // una pista cada vez, y se guarda en memoria. Nada automático por fila:
  // medir toda la biblioteca serían N análisis seguidos.
  const [measured, setMeasured] = useState({}); // name -> {bpm, confidence}
  const [measuring, setMeasuring] = useState(null);
  // [M3] Tolerancia (bpm) para enseñar «PEDÍA · SALIÓ»: viene de config,
  // no está escrita en la pantalla. Sin config no se enseña nada.
  const [bpmTolerance, setBpmTolerance] = useState(null);

  useEffect(() => {
    api.musicConfig()
      .then((cfg) => {
        const t = Number(cfg?.bpm_display_tolerance);
        setBpmTolerance(Number.isFinite(t) ? t : null);
      })
      .catch(() => setBpmTolerance(null));
  }, []);

  // [M3] Diferencia automática pedido vs. medido (ficha, tras generar).
  // Solo se enseña si hay AMBOS valores y la diferencia llega a la
  // tolerancia: si no se midió, no se dice nada (nunca se maquilla).
  const tempoDiff = (item) => {
    if (bpmTolerance == null || !item.bpm || !item.bpm_measured) return null;
    const delta = Math.abs(item.bpm - item.bpm_measured);
    return delta >= bpmTolerance
      ? { asked: item.bpm, got: item.bpm_measured, delta }
      : null;
  };

  // Mide el tempo real de una pista de la biblioteca (botón TEMPO). Complementa
  // [M3]: la medición automática de la ficha no cubre pistas antiguas.
  const measureTempo = async (name) => {
    if (measuring) return;
    setMeasuring(name);
    try {
      const g = await api.groove(name, 'output');
      if (g?.bpm) setMeasured((prev) => ({ ...prev, [name]: { bpm: g.bpm, confidence: g.confidence ?? null } }));
    } catch (e) {
      if (!isTransportBlip(e.message)) setError(actionError(e.message));
    } finally {
      setMeasuring(null);
    }
  };
  // Modo SELECCIONAR (spec/02 [L2]): marcar varias filas y borrar el bloque.
  const [selectMode, setSelectMode] = useState(false);
  const [selected, setSelected] = useState(() => new Set());
  const [confirmBulk, setConfirmBulk] = useState(false);
  const [bulkBusy, setBulkBusy] = useState(false);
  // Versiones finales vs piezas (voz/base separadas): por defecto solo se
  // ven las finales; las piezas se muestran en una sección aparte abajo,
  // no desaparecen (spec/02 [L3]).
  const [showParts, setShowParts] = useState(false);
  const isPart = (i) => (
    i.task_type === 'vocals' || i.task_type === 'instrumental'
    // Fichas antiguas sin task (o marcadas "remix"): el nombre del stem manda.
    || /-(base|voces)(-v\d+)?\.mp3$/i.test(i.name)
  );
  const finals = items.filter((i) => !isPart(i));
  const parts = items.filter(isPart);
  const visible = showParts ? [...finals, ...parts] : finals;

  const refresh = useCallback(async () => {
    while (mounted.current) {
      try {
        const data = await api.library();
        if (!mounted.current) return;
        const list = data.items ?? [];
        setItems(list);
        setError(null);
        // La recarga (manual o automática) no rompe la selección: solo poda.
        const alive = new Set(list.map((i) => i.name));
        setSelected((prev) => {
          if (prev.size === 0) return prev;
          const kept = new Set([...prev].filter((n) => alive.has(n)));
          return kept.size === prev.size ? prev : kept;
        });
        return;
      } catch (e) {
        if (!mounted.current) return;
        if (!isTransportBlip(e.message)) { setError(actionError(e.message)); return; }
        await new Promise((resolve) => setTimeout(resolve, TRANSPORT_ERROR_CLEAR_MS));
      } finally {
        if (mounted.current) setLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    mounted.current = true;
    void refresh();
    return () => { mounted.current = false; };
  }, [refresh]);

  // Auto-recarga al terminar un trabajo (spec/02 [L1]): App.jsx avisa con
  // externalRefresh cuando la cola pasa de activa a vacía. Sin jobs no hay
  // tráfico extra. Se salta el primer pintado (ya refresca el efecto de arriba).
  const firstTick = React.useRef(true);
  useEffect(() => {
    if (firstTick.current) { firstTick.current = false; return; }
    void refresh();
  }, [externalRefresh, refresh]);

  const toggle = (name) => setPlaying((cur) => (cur === name ? null : name));

  const commitRename = async (oldName) => {
    const next = renameValue.trim();
    setRenameName(null);
    if (!next || next === oldName) return;
    setError(null);
    try {
      await api.renameAudio(oldName, next, 'output');
      if (playing === oldName) setPlaying(null);
      await refresh();
    } catch (e) {
      setError(actionError(e.message));
    }
  };

  const remove = async (name) => {
    setError(null);
    try {
      // El cliente libera src antes de que React desmonte el reproductor.
      const deletion = api.deleteAudio(name);
      if (playing === name) setPlaying(null);
      await deletion;
      await refresh();
    } catch (e) {
      setError(actionError(e.message));
    }
  };

  const toggleSelect = (name) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(name)) next.delete(name);
      else next.add(name);
      return next;
    });
    setConfirmBulk(false);
  };

  const exitSelect = () => {
    setSelectMode(false);
    setSelected(new Set());
    setConfirmBulk(false);
  };

  // Borrado en bloque con un solo SÍ/NO (spec/02 [L2]).
  const removeMany = async () => {
    const names = [...selected];
    if (names.length === 0) return;
    setBulkBusy(true);
    setError(null);
    try {
      const deletion = api.deleteMany(names);
      if (playing && names.includes(playing)) setPlaying(null);
      const res = await deletion;
      const blocked = res.blocked ?? [];
      const failed = res.failed ?? [];
      const remaining = [...blocked, ...failed.map((item) => item.name)];
      setSelected(new Set(remaining));
      setConfirmBulk(false);
      setSelectMode(remaining.length > 0);
      await refresh();
      const messages = [];
      if (blocked.length) messages.push(`Siguen abiertos en otro proceso: ${blocked.join(', ')}`);
      if (failed.length) messages.push(...failed.map((item) => `${item.name}: ${item.detail}`));
      if (res.not_found?.length) messages.push(`No estaban: ${res.not_found.join(', ')}`);
      if (messages.length) setError(messages.join(' · '));
    } catch (e) {
      setError(actionError(e.message));
    } finally {
      setBulkBusy(false);
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
      setError(actionError(e.message));
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
      <div className="max-w-[1300px] mx-auto w-full px-6 py-8 xl:px-10 flex flex-col gap-6">
        {/* Cabecera */}
        <div className="flex items-center gap-4 flex-wrap">
          <h2 className="h-title text-[20px]">BIBLIOTECA</h2>
          <span className="mono text-[12px] text-[var(--faint)]">
            {finals.length} versiones finales{parts.length > 0 ? ` · ${parts.length} base/voz aparte` : ''}
          </span>
          {selectMode ? (
            <div className="flex items-center gap-2 ml-auto flex-wrap">
              <span className="mono text-[11px] text-[var(--acc)]">{selected.size} SELECCIONADAS</span>
              <button onClick={() => { setSelected(new Set(visible.map((i) => i.name))); setConfirmBulk(false); }}
                className="btn btn-ghost h-8 px-3">TODAS</button>
              <button onClick={() => { setSelected(new Set()); setConfirmBulk(false); }}
                className="btn btn-ghost h-8 px-3">NINGUNA</button>
              {confirmBulk ? (
                <>
                  <button onClick={() => void removeMany()} disabled={bulkBusy || selected.size === 0}
                    className="btn btn-ghost h-8 px-3 !border-[rgba(255,92,92,0.5)] !text-red-300">
                    {bulkBusy ? <Loader2 size={12} className="animate-spin" /> : null} SÍ, BORRAR {selected.size}
                  </button>
                  <button onClick={() => setConfirmBulk(false)} className="btn btn-ghost h-8 px-3">NO</button>
                </>
              ) : (
                <button onClick={() => setConfirmBulk(true)} disabled={selected.size === 0}
                  className="btn btn-ghost h-8 px-3 hover:!border-[rgba(255,92,92,0.5)] hover:!text-red-300">
                  <Trash2 size={12} /> BORRAR
                </button>
              )}
              <button onClick={exitSelect} className="btn btn-ghost h-8 px-3"><X size={12} /> SALIR</button>
            </div>
          ) : (
            <div className="flex items-center gap-2 ml-auto">
              <button onClick={() => { setSelectMode(true); setMenuName(null); setConfirmDelete(null); }}
                className="btn btn-ghost h-8 px-3">SELECCIONAR</button>
              <button onClick={refresh} className="btn btn-ghost h-8 px-3"><RefreshCw size={12} /> ACTUALIZAR</button>
            </div>
          )}
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

        {/* Lista: primero las versiones finales; las piezas (voz/base) se
            añaden al final SOLO si el usuario las pide abajo. */}
        <div className="flex flex-col">
          {visible.map((item) => (
            <div key={item.name} className={`border-b border-[var(--line)] ${isPart(item) ? 'opacity-60' : ''}`}>
              <div className={`flex flex-col gap-2 py-3 px-2 ${playing === item.name ? 'bg-[var(--acc-dim)]' : ''}`}>
                <div
                  className={`flex items-center gap-3 min-w-0 ${selectMode ? 'cursor-pointer' : ''}`}
                  onClick={selectMode ? (e) => {
                    // En modo SELECCIONAR el clic en la fila marca; los
                    // controles siguen siendo clicables sin marcar.
                    if (e.target.closest('button,a,input,audio')) return;
                    toggleSelect(item.name);
                  } : undefined}
                >
                  {selectMode && (
                    <button onClick={() => toggleSelect(item.name)} title="seleccionar"
                      className="shrink-0 text-[var(--muted)] hover:text-[var(--acc)]">
                      {selected.has(item.name)
                        ? <CheckSquare size={17} className="text-[var(--acc)]" />
                        : <Square size={17} />}
                    </button>
                  )}
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
                    <span className="min-w-0 flex-1">
                      <span className="mono text-[13.5px] text-zinc-200 truncate block">{item.name.replace(/\.mp3$/i, '')}</span>
                      <span className="mono text-[10px] text-[var(--faint)] truncate block">
                        {[fmtBytes(item.size_bytes), fmtDate(item.modified), item.bpm ? `${item.bpm} bpm` : null, TASK_LABEL[item.task_type] ?? item.task_type, item.prompt].filter(Boolean).join(' · ')}
                      </span>
                      {/* [M3] «PEDÍA 180 · SALIÓ 170» automático de la ficha.
                          Solo con diferencia ≥ tolerancia de config; sin
                          medición, la línea no existe. */}
                      {tempoDiff(item) && (
                        <span className="mono text-[10px] text-[var(--warn)] block">
                          PEDÍA {Math.round(tempoDiff(item).asked)} · SALIÓ {Math.round(tempoDiff(item).got)} BPM
                        </span>
                      )}
                    </span>
                  )}
                </div>
                {renameName !== item.name && (
                  <div className="flex flex-wrap gap-2 pl-14" data-acciones>
                    <button onClick={() => { setMenuName(menuName === item.name ? null : item.name); setConfirmDelete(null); }}
                      className={`btn h-8 px-2.5 ${menuName === item.name ? 'btn-ghost !border-[var(--acc-line)] !text-[var(--text)]' : 'btn-ghost'}`}>
                      ACCIONES <ChevronDown size={12} className={menuName === item.name ? 'rotate-180 transition-transform' : 'transition-transform'} />
                    </button>
                    {confirmDelete === item.name && (
                      <>
                        <button onClick={() => { setConfirmDelete(null); setMenuName(null); void remove(item.name); }}
                          className="btn btn-ghost h-8 px-2.5 !border-[rgba(255,92,92,0.5)] !text-red-300">
                          SÍ, BORRAR
                        </button>
                        <button onClick={() => setConfirmDelete(null)} className="btn btn-ghost h-8 px-2.5">NO</button>
                      </>
                    )}
                  </div>
                )}
                {menuName === item.name && renameName !== item.name && confirmDelete !== item.name && (
                  <div className="flex flex-wrap gap-2 pl-14 pt-1" data-acciones>
                    <button onClick={() => { setEditName(null); setMenuName(null); setIaName(iaName === item.name ? null : item.name); }}
                      className={`btn h-8 px-2.5 ${iaName === item.name ? 'btn-ghost !border-[var(--acc-line)] !text-[var(--text)]' : 'btn-ghost'}`}>
                      <Sparkles size={12} /> REMIX
                    </button>

                    <button onClick={() => { setIaName(null); setMenuName(null); openEditor(item.name); }}
                      className={`btn h-8 px-2.5 ${editName === item.name ? 'btn-ghost !border-[var(--acc-line)] !text-[var(--text)]' : 'btn-ghost'}`}>
                      <SlidersHorizontal size={12} /> AJUSTES
                    </button>
                    <button onClick={() => { setMenuName(null); setRenameValue(item.name.replace(/\.[^.]+$/, '')); setRenameName(item.name); }}
                      className="btn btn-ghost h-8 px-2.5">
                      <Pencil size={12} /> NOMBRE
                    </button>
                    <a href={api.audioUrl(item.name)} download className="btn btn-ghost h-8 px-2.5">
                      <Download size={12} /> BAJAR
                    </a>
                    <button onClick={() => setConfirmDelete(item.name)} className="btn btn-ghost h-8 px-2.5 hover:!border-[rgba(255,92,92,0.5)] hover:!text-red-300">
                      <Trash2 size={12} /> BORRAR
                    </button>
                    <button onClick={() => void measureTempo(item.name)} disabled={measuring === item.name}
                      className="btn btn-ghost h-8 px-2.5" title="Mide el tempo real de esta pista (DSP local)">
                      {measuring === item.name ? <Loader2 size={12} className="animate-spin" /> : null} TEMPO
                    </button>
                  </div>
                )}
                {measured[item.name] && menuName === item.name && (
                  <div className="flex flex-wrap gap-2 pl-14 pt-1">
                    <span className="mono text-[10.5px] text-[var(--acc)]">
                      MEDIDO ≈{Math.round(measured[item.name].bpm)} BPM
                      {measured[item.name].confidence != null
                        ? ` · SEGURIDAD ${Math.round(measured[item.name].confidence * 100)}%` : ''}
                    </span>
                    {item.bpm && measured[item.name] && bpmTolerance != null
                      && Math.abs(item.bpm - measured[item.name].bpm) >= bpmTolerance && (
                      <span className="mono text-[10.5px] text-[var(--warn)]">
                        PEDÍA {Math.round(item.bpm)} · SALE {Math.round(measured[item.name].bpm)}
                      </span>
                    )}
                  </div>
                )}
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
                <div className="py-3 border-y border-[var(--line)]">
                  <RemixActions fileName={item.name} ficha={item} sourceKind="output" onDone={() => refresh()} />
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

        {/* Piezas aparte (spec/02 [L3]): existen, pero no marean. */}
        {!loading && finals.length === 0 && parts.length > 0 && !showParts && (
          <p className="mono text-[11px] text-[var(--faint)] py-4 text-center">
            SIN VERSIONES FINALES TODAVÍA · LAS PIEZAS ESTÁN DETRÁS DE ESTE BOTÓN
          </p>
        )}
        {parts.length > 0 && !loading && (
          <button type="button" onClick={() => setShowParts((v) => !v)}
            className="btn btn-ghost h-7 px-3 self-start text-[10px]">
            <ChevronDown size={11} className={showParts ? 'rotate-180 transition-transform' : 'transition-transform'} />
            {showParts ? 'OCULTAR' : 'VER'} BASE Y VOZ SEPARADAS · {parts.length}
          </button>
        )}
      </div>
    </div>
  );
}



