import React, { useEffect, useRef, useState } from 'react';
import { BookOpen, Shuffle, X } from 'lucide-react';
import { api } from '../api';
import { removeTexto } from '../variants';

/** Alto máximo del panel. Si no cabe debajo del botón, se abre hacia arriba. */
const PANEL_MAX_PX = 360;
const DEBOUNCE_MS = 250;
const LIMIT = 50;

/**
 * Glosario de estilos, en cualquier sitio que tenga prompt (CREAR, remix,
 * otra versión). Todo lo que se añade está en inglés, que es el idioma de
 * las captions de entrenamiento: ver y enviar, el mismo idioma.
 *
 * - Estilos de Musicia (caption real de cada uno) y entradas del vocabulario
 *   del motor (`genres_vocab.txt`, la whitelist con la que escribe el campo
 *   genres): lo que ves es lo que el modelo puede decir.
 * - Combinar: eliges dos y solo aparecen combinaciones que existen en ese
 *   vocabulario (techno + hardcore -> «hardcore techno»). Si no existe la
 *   mezcla, no se ofrece nada.
 * - Lo que ya está en tu frase se marca ELEGIDO y vuelve a pulsarlo lo quita.
 */
export default function Glossary({ prompt = '', setPrompt }) {
  const [open, setOpen] = useState(false);
  const [box, setBox] = useState(null);
  const [q, setQ] = useState('');
  const [data, setData] = useState(null);
  const [pick, setPick] = useState([]);
  const [combos, setCombos] = useState(null);
  const [busy, setBusy] = useState(false);
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
    window.addEventListener('resize', onDown);
    return () => {
      document.removeEventListener('mousedown', onDown);
      document.removeEventListener('keydown', onKey);
      window.removeEventListener('resize', onDown);
    };
  }, [open]);

  /** Búsqueda con espera: cada tecla no dispara una petición. Al abrir con
      consulta vacía trae el catálogo y las primeras entradas. */
  useEffect(() => {
    if (!open) return undefined;
    const value = q.trim();
    const id = ++seq.current;
    const timer = setTimeout(() => {
      setBusy(true);
      api.genreGlossary(value, LIMIT).then((res) => {
        if (res && id === seq.current) setData(res);
        setBusy(false);
      });
    }, DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [q, open]);

  /** Dos estilos elegidos: combinaciones reales del modelo (o nada). El
      estado de la bandeja lo limpia el propio clic (el efecto solo consulta). */
  useEffect(() => {
    if (pick.length < 2) return undefined;
    let alive = true;
    api.genreCombine(pick[0], pick[1], LIMIT).then((res) => {
      if (alive) setCombos(res);
    });
    return () => { alive = false; };
  }, [pick]);

  const texto = (prompt ?? '').trim();
  const elegido = (text) => texto.toLowerCase().includes(text.toLowerCase());

  const cerrar = () => {
    setOpen(false);
    setQ('');
    setPick([]);
    setCombos(null);
  };

  const add = (text) => {
    setPrompt((prev) => {
      const base = (prev ?? '').trim();
      return base ? `${base} ${text}` : text;
    });
    cerrar();
  };

  const quitar = (text) => setPrompt((prev) => removeTexto(prev ?? '', text));

  const togglePick = (name) => {
    setCombos(null);
    setPick((prev) => (prev.includes(name) ? prev.filter((n) => n !== name)
      : prev.length < 2 ? [...prev, name] : [prev[0], name]));
  };

  const row = (k, text, extra = null, hint = '') => {
    const on = elegido(text);
    return (
      <div key={k} className="flex items-center gap-1 pr-1 hover:bg-[var(--acc-dim)]">
        <button onClick={() => (on ? quitar(text) : add(text))}
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

  const items = data?.items ?? [];
  const styles = data?.styles ?? [];
  const query = q.trim();
  /** Buscador completo: el catálogo también se filtra mientras escribes,
      no solo el vocabulario del motor. */
  const stylesMatching = query
    ? styles.filter((s) => `${s.name} ${s.genre ?? ''} ${s.text ?? ''}`.toLowerCase().includes(query.toLowerCase()))
    : styles;

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

          <input value={q} onChange={(e) => setQ(e.target.value)} autoFocus
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

          {stylesMatching.length > 0 && (
            <div className="flex flex-col">
              <span className="label">ESTILOS DE MUSICIA</span>
              <div className="max-h-[110px] overflow-y-auto">
                {stylesMatching.map((s) => {
                  /* Solo el GÉNERO, que es lo que se añade al prompt: la
                     caption completa («definición») es lo que rellena el
                     motor por su cuenta con style_caption. */
                  const genre = s.genre || s.name;
                  return row(s.name, genre, pickBtn(genre), ` · ${s.name} · ${s.bpm} bpm`);
                })}
              </div>
            </div>
          )}

          <div className="flex flex-col">
            <span className="label">{query ? 'RESULTADOS' : 'DEL VOCABULARIO DEL MODELO'}</span>
            <div className="max-h-[190px] overflow-y-auto">
              {items.map((item) => row(item, item, pickBtn(item)))}
              {!busy && items.length === 0 && (
                <span className="text-[10px] text-[var(--faint)] px-1">nada por aquí</span>
              )}
            </div>
          </div>

          <div className="mono text-[9.5px] text-[var(--faint)] border-t border-[var(--line)] pt-1">
            {data?.available
              ? `${data.total.toLocaleString('es')} entradas${query ? ' para «' + query + '»' : ''} · whitelist del motor`
              : 'vocabulario del motor no disponible'}
          </div>
        </div>
      )}
    </span>
  );
}
