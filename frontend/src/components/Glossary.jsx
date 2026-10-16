import React, { useEffect, useRef, useState } from 'react';
import { BookOpen, Shuffle, X } from 'lucide-react';
import { api, TRANSPORT_ERROR_CLEAR_MS } from '../api';
import { applyModelTerm, glossaryFoot, glossaryShown, modelTerms, stylesForQuery } from '../glossary_pick';

/** Alto máximo del panel. Si no cabe debajo del botón, se abre hacia arriba. */
const PANEL_MAX_PX = 360;
const DEBOUNCE_MS = 250;
const LIMIT = 50;

/**
 * Glosario de estilos, en cualquier sitio que tenga prompt (CREAR, remix,
 * otra versión). Todo lo que se añade está en inglés, que es el idioma de
 * las captions de entrenamiento: ver y enviar, el mismo idioma.
 *
 * - El vocabulario del modelo (`genres_vocab.txt`) sigue siendo la lista.
 *   Cada elección es una línea del vocabulario del modelo. Varias quedan en
 *   una sola caption: «A track with gabber · medieval». El BPM, si el cuadro
 *   iba vacío, pasa a su control y no se escribe en la frase.
 * - Combinar: eliges dos y solo aparecen combinaciones que existen en ese
 *   vocabulario (techno + hardcore -> «hardcore techno»). Si no existe la
 *   mezcla, no se ofrece nada.
 * - Lo que ya está en tu frase se marca ELEGIDO y vuelve a pulsarlo lo quita.
 */
export default function Glossary({ prompt = '', setPrompt, onBpm = null, bpm = null }) {
  const [open, setOpen] = useState(false);
  const [box, setBox] = useState(null);
  const [q, setQ] = useState('');
  const [data, setData] = useState(null);
  const [pick, setPick] = useState([]);
  const [combos, setCombos] = useState(null);
  const [busy, setBusy] = useState(false);
  const [fail, setFail] = useState(null);
  const ref = useRef(null);
  const menuRef = useRef(null);
  const seq = useRef(0);

  const place = () => {
    const el = ref.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    const below = window.innerHeight - rect.bottom;
    const up = below < PANEL_MAX_PX && rect.top > below;
    setBox({
      left: Math.max(8, Math.min(rect.left, window.innerWidth - 352)),
      ...(up
        ? { bottom: window.innerHeight - rect.top + 4 }
        : { top: rect.bottom + 4 }),
    });
  };

  useEffect(() => {
    if (!open) return undefined;
    place();
    const onDown = (e) => {
      if (ref.current && !ref.current.contains(e.target)
        && menuRef.current && !menuRef.current.contains(e.target)) setOpen(false);
    };
    const onKey = (e) => { if (e.key === 'Escape') setOpen(false); };
    document.addEventListener('mousedown', onDown);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onDown);
      document.removeEventListener('keydown', onKey);
    };
  }, [open]);

  /** Búsqueda con espera: cada tecla no dispara una petición. Al abrir con
      consulta vacía trae el catálogo y las primeras entradas. */
  useEffect(() => {
    if (!open) return undefined;
    let active = true;
    const value = q.trim();
    const id = ++seq.current;
    const timer = setTimeout(async () => {
      if (!active || id !== seq.current) return;
      setBusy(true);
      setFail(null);
      while (active && id === seq.current) {
        try {
          const res = await api.genreGlossary(value, LIMIT);
          if (!active || id !== seq.current) return;
          if (res) { setData(res); setBusy(false); return; }
        } catch (err) {
          if (!active || id !== seq.current) return;
          setFail(err?.message || 'Error desconocido');
          setBusy(false);
          return;
        }
        await new Promise((resolve) => setTimeout(resolve, TRANSPORT_ERROR_CLEAR_MS));
      }
    }, DEBOUNCE_MS);
    return () => { active = false; clearTimeout(timer); };
  }, [q, open]);

  /** Dos estilos elegidos: combinaciones reales del modelo (o nada). El
      estado de la bandeja lo limpia el propio clic (el efecto solo consulta). */
  useEffect(() => {
    if (pick.length < 2) return undefined;
    let alive = true;
    const load = async () => {
      while (alive) {
        try {
          const res = await api.genreCombine(pick[0], pick[1], LIMIT);
          if (!alive) return;
          if (res) { setCombos(res); return; }
        } catch (err) {
          if (!alive) return;
          setCombos({ items: [], error: err?.message || 'Error desconocido' });
          return;
        }
        await new Promise((resolve) => setTimeout(resolve, TRANSPORT_ERROR_CLEAR_MS));
      }
    };
    void load();
    return () => { alive = false; };
  }, [pick]);

  const enCaption = (prompt ?? '').trim().toLowerCase().startsWith('a track with ');
  const elegido = (text) => enCaption && modelTerms(prompt).some((part) => part.toLowerCase() === String(text).trim().toLowerCase());

  const cerrar = () => {
    setOpen(false);
    setQ('');
    setPick([]);
    setCombos(null);
    setFail(null);
  };

  const meter = (termino, tempo = null) => {
    const before = (prompt ?? '').trim();
    const framed = before.toLowerCase().startsWith('a track with ');
    const next = applyModelTerm(prompt, termino);
    setPrompt(next);
    const quitado = framed && !modelTerms(next).some((part) => part.toLowerCase() === String(termino).trim().toLowerCase());
    if (onBpm && !next) onBpm(null);
    else if (onBpm && next && !quitado && (!before || bpm == null || bpm === '')) onBpm(tempo);
    cerrar();
  };

  const add = (text) => meter(text);

  const togglePick = (name) => {
    setCombos(null);
    setPick((prev) => (prev.includes(name) ? prev.filter((n) => n !== name)
      : prev.length < 2 ? [...prev, name] : [prev[0], name]));
  };

  const row = (k, text, extra = null, hint = '') => {
    const on = elegido(text);
    return (
      <div key={k} className="flex items-center gap-1 pr-1 hover:bg-[var(--acc-dim)]">
        <button onClick={() => add(text)}
          title={on ? `Quitar «${text}» de tu frase` : `Añade al prompt: «${text}»${hint}`}
          className={`flex-1 text-left px-2 py-1 text-[11.5px] truncate ${on ? 'text-[var(--acc)]' : 'text-zinc-200'}`}>
          {text}
        </button>
        {on && <span className="mono text-[7.5px] text-[var(--acc)] shrink-0">ELEGIDO</span>}
        {extra}
      </div>
    );
  };

  const pickBtn = (name) => (
    <button key={`p:${name}`} onClick={() => togglePick(name)}
      title="Elegir para combinar con otro estilo"
      className={`shrink-0 p-1 ${pick.includes(name) ? 'text-[var(--acc)]' : 'text-[var(--faint)] hover:text-[var(--text)]'}`}>
      <Shuffle size={12} />
    </button>
  );

  const query = q.trim();
  const current = glossaryShown(data, query);
  const items = current?.items ?? [];
  const frases = stylesForQuery(current?.styles, query);
  const foot = glossaryFoot(current, fail);

  return (
    <span className="relative inline-flex" ref={ref}>
      <button onClick={() => setOpen((o) => !o)} title="Glosario de estilos del modelo (y combinaciones reales)"
        className={`btn btn-ghost h-3.5 px-1.5 text-[8px] leading-none gap-1 ${open ? '!border-[var(--acc-line)] !text-[var(--text)]' : ''}`}>
        <BookOpen size={9} /> GLOSARIO
      </button>
      {open && box && (
        <div ref={menuRef} style={{ left: box.left, top: box.top, bottom: box.bottom }}
          className="fixed z-50 w-[344px] border border-[var(--line-strong)] bg-[var(--surface-2)] p-2 flex flex-col gap-2 shadow-lg">
          <div className="flex items-center justify-between">
            <span className="label">GLOSARIO DEL MODELO</span>
            <button onClick={() => setOpen(false)} className="text-[var(--faint)] hover:text-[var(--text)]">
              <X size={13} />
            </button>
          </div>

          <input value={q} onChange={(e) => { setQ(e.target.value); setFail(null); }} autoFocus
            placeholder="Buscar estilo o subestilo…"
            className="w-full bg-transparent border border-[var(--line)] px-2 py-1 text-[12px] text-zinc-100 placeholder:text-[var(--faint)] focus:border-[var(--acc-line)] outline-none" />

          {(pick.length > 0 || (combos?.items?.length > 0)) && (
            <div className="border border-[var(--line)] p-1.5 flex flex-col gap-1">
              <div className="flex items-center gap-1 flex-wrap">
                <span className="label">COMBINAR</span>
                {pick.map((p) => (
                  <button key={p} onClick={() => togglePick(p)} title="Quitar de la combinación"
                    className="mono text-[10px] px-1.5 py-0.5 border border-[var(--acc-line)] text-[var(--acc)]">
                    {p} ×
                  </button>
                ))}
                {pick.length < 2 && (
                  <span className="text-[10px] text-[var(--faint)]">elige 2 con ⇄</span>
                )}
              </div>
              {pick.length === 2 && (
                combos === null ? (
                  <span className="text-[10px] text-[var(--faint)]">buscando…</span>
                ) : combos.error ? (
                  <span className="text-[10px] text-[var(--faint)]">{combos.error}</span>
                ) : combos.items?.length > 0 ? (
                  <div className="flex flex-col">
                    {combos.items.map((item) => row(item, item))}
                  </div>
                ) : (
                  <span className="text-[10px] text-[var(--faint)]">
                    el modelo no tiene esa combinación
                  </span>
                )
              )}
            </div>
          )}

          {frases.length > 0 && (
            <div className="flex flex-col gap-1 border border-[var(--line)] p-1.5">
              <span className="label">SE ENVÍA</span>
              {frases.map((style) => {
                const termino = String(style.genre || '').trim();
                if (!termino) return null;
                const on = elegido(termino);
                return (
                  <button key={style.name} type="button" onClick={() => meter(termino, style.bpm ?? null)}
                    title={on ? `Quitar «${termino}»` : `El modelo escribe «${termino}»`}
                    className={`text-left px-1 py-1 ${on ? 'text-[var(--acc)]' : 'text-zinc-200'}`}>
                    <span className="label">{style.name}{style.bpm ? ` · ${style.bpm}` : ''}</span>
                    <span className="block text-[12px] leading-snug">{termino}</span>
                  </button>
                );
              })}
            </div>
          )}

          <div className="flex flex-col">
            <span className="label">{query ? 'RESULTADOS' : 'DEL VOCABULARIO DEL MODELO'}</span>
            <div className="max-h-[280px] overflow-y-auto">
              {items.map((item) => row(item, item, pickBtn(item)))}
              {!busy && foot === 'ready' && items.length === 0 && (
                <span className="text-[10px] text-[var(--faint)] px-1">nada por aquí</span>
              )}
            </div>
          </div>

          <div className="mono text-[9.5px] text-[var(--faint)] border-t border-[var(--line)] pt-1">
            {foot === 'ready'
              ? `${current.total.toLocaleString('es')} entradas${query ? ' para «' + query + '»' : ''} · whitelist del motor`
              : foot === 'missing'
                ? 'vocabulario del motor no disponible'
                : foot === 'error'
                  ? fail
                  : 'Cargando el vocabulario…'}
          </div>
        </div>
      )}
    </span>
  );
}
