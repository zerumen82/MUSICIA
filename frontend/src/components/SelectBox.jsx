import React, { useEffect, useRef, useState } from 'react';
import { ChevronDown } from 'lucide-react';

/** Alto máximo del menú. Si no cabe debajo del botón, se abre hacia arriba. */
const MENU_MAX_PX = 288;
const MENU_GUTTER_PX = 8;

/**
 * Desplegable compacto: cabe en una línea y solo ocupa espacio al abrirlo.
 * Se usa en CREAR (voz) y en MEZCLA (base/voz): la UI no debe llenarse de
 * listas largas (petición explícita del usuario).
 */
export default function SelectBox({ label, options, value, onChange, placeholder = 'AUTO', mono = true, clearable = true, disabled = false }) {
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
    const width = Math.min(Math.max(190, rect.width), window.innerWidth - MENU_GUTTER_PX * 2);
    setBox({
      left: Math.max(MENU_GUTTER_PX, Math.min(rect.left, window.innerWidth - width - MENU_GUTTER_PX)),
      width,
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
    const onKeyDown = (event) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        close();
        ref.current?.querySelector('button')?.focus();
      }
    };
    const onScroll = (e) => {
      if (menuRef.current && menuRef.current.contains(e.target)) return;
      close();
    };
    document.addEventListener('mousedown', onDocDown);
    document.addEventListener('keydown', onKeyDown);
    window.addEventListener('resize', close);
    window.addEventListener('scroll', onScroll, true);
    return () => {
      document.removeEventListener('mousedown', onDocDown);
      document.removeEventListener('keydown', onKeyDown);
      window.removeEventListener('resize', close);
      window.removeEventListener('scroll', onScroll, true);
    };
  }, [open]);

  const current = options.find((o) => (o.id ?? o.name) === value);

  return (
    <div className="relative" ref={ref}>
      <button disabled={disabled} aria-expanded={open && !disabled} onClick={() => {
        if (open) { setOpen(false); return; }
        place();
        setOpen(true);
      }}
        className={`btn btn-ghost h-8 px-2.5 gap-1.5 max-w-[280px] ${current ? '!border-[var(--line-strong)] !text-[var(--text)]' : ''}`}>
        {label && <span className="text-[13px] text-[var(--text)]">{label}</span>}
        <span className={`text-[14px] truncate text-[var(--text)] ${mono ? 'mono' : ''}`}>
          {current ? current.label : placeholder}
        </span>
        <ChevronDown size={12} className={open ? 'rotate-180 transition-transform' : 'transition-transform'} />
      </button>
      {open && !disabled && box && (
        <div
          ref={menuRef}
          className="desk-menu fixed z-50 overflow-y-auto p-1 flex flex-col shadow-lg"
          style={{ left: box.left, top: box.top, bottom: box.bottom, width: box.width, maxHeight: MENU_MAX_PX }}
        >
          {clearable && (
            <button type="button" onClick={() => { onChange(''); setOpen(false); }}
              className="px-3 py-2">
              <span>{placeholder}</span>
            </button>
          )}
          {options.map((o) => {
            const id = o.id ?? o.name;
            return (
              <button type="button" key={id} onClick={() => { onChange(id); setOpen(false); }}
                title={o.title ?? o.label}
                aria-selected={value === id}
                className="px-3 py-2">
                <span className="truncate block">{o.label}</span>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
