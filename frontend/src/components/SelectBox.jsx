import React, { useEffect, useRef, useState } from 'react';
import { ChevronDown } from 'lucide-react';

/** Alto máximo del menú. Si no cabe debajo del botón, se abre hacia arriba. */
const MENU_MAX_PX = 288;

/**
 * Desplegable compacto: cabe en una línea y solo ocupa espacio al abrirlo.
 * Se usa en CREAR (voz) y en MEZCLA (base/voz): la UI no debe llenarse de
 * listas largas (petición explícita del usuario).
 */
export default function SelectBox({ label, options, value, onChange, placeholder = 'AUTO', mono = true, clearable = true }) {
  const [open, setOpen] = useState(false);
  const [box, setBox] = useState(null);
  const ref = useRef(null);
  const menuRef = useRef(null);

  const place = () => {
    const el = ref.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    const below = window.innerHeight - rect.bottom;
    const up = below < MENU_MAX_PX && rect.top > below;
    setBox({
      left: Math.max(8, rect.left),
      minWidth: Math.max(190, rect.width),
      ...(up
        ? { bottom: window.innerHeight - rect.top + 4 }
        : { top: rect.bottom + 4 }),
    });
  };

  useEffect(() => {
    if (!open) return undefined;
    const onDocDown = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    };
    const close = () => setOpen(false);
    const onScroll = (e) => {
      if (menuRef.current && menuRef.current.contains(e.target)) return;
      close();
    };
    document.addEventListener('mousedown', onDocDown);
    window.addEventListener('resize', close);
    window.addEventListener('scroll', onScroll, true);
    return () => {
      document.removeEventListener('mousedown', onDocDown);
      window.removeEventListener('resize', close);
      window.removeEventListener('scroll', onScroll, true);
    };
  }, [open]);

  const current = options.find((o) => (o.id ?? o.name) === value);

  return (
    <div className="relative" ref={ref}>
      <button onClick={() => {
        if (open) { setOpen(false); return; }
        place();
        setOpen(true);
      }}
        className={`btn btn-ghost h-8 px-2.5 gap-1.5 max-w-[280px] ${current ? '!border-[var(--acc-line)] !text-[var(--text)]' : ''}`}>
        {label && <span className="label">{label}</span>}
        <span className={`text-[11px] truncate ${mono ? 'mono' : ''} ${current ? 'text-[var(--acc)]' : ''}`}>
          {current ? current.label : placeholder}
        </span>
        <ChevronDown size={12} className={open ? 'rotate-180 transition-transform' : 'transition-transform'} />
      </button>
      {open && box && (
        <div
          ref={menuRef}
          className="fixed z-50 overflow-y-auto border border-[var(--line-strong)] bg-[var(--surface-2)] p-1 flex flex-col shadow-lg"
          style={{ left: box.left, top: box.top, bottom: box.bottom, minWidth: box.minWidth, maxHeight: MENU_MAX_PX }}
        >
          {clearable && (
            <button onClick={() => { onChange(''); setOpen(false); }}
              className="text-left px-3 py-1.5 hover:bg-[var(--acc-dim)]">
              <span className="label">{placeholder}</span>
            </button>
          )}
          {options.map((o) => {
            const id = o.id ?? o.name;
            return (
              <button key={id} onClick={() => { onChange(id); setOpen(false); }}
                title={o.title ?? o.label}
                className={`text-left px-3 py-1.5 hover:bg-[var(--acc-dim)] ${value === id ? 'text-[var(--acc)]' : 'text-zinc-200'}`}>
                <span className="mono text-[11.5px] truncate block">{o.label}</span>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
