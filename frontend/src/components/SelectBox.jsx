import React, { useEffect, useRef, useState } from 'react';
import { ChevronDown } from 'lucide-react';

/**
 * Desplegable compacto: cabe en una línea y solo ocupa espacio al abrirlo.
 * Se usa en CREAR (voz) y en MEZCLA (base/voz): la UI no debe llenarse de
 * listas largas (petición explícita del usuario).
 */
export default function SelectBox({ label, options, value, onChange, placeholder = 'AUTO', mono = true }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    if (!open) return undefined;
    const onDocDown = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener('mousedown', onDocDown);
    return () => document.removeEventListener('mousedown', onDocDown);
  }, [open]);

  const current = options.find((o) => (o.id ?? o.name) === value);

  return (
    <div className="relative" ref={ref}>
      <button onClick={() => setOpen((o) => !o)}
        className={`btn h-8 px-2.5 gap-1.5 max-w-[220px] ${current ? 'btn-signal' : 'btn-ghost'}`}>
        {label && <span className="label">{label}</span>}
        <span className={`text-[11px] truncate ${mono ? 'mono' : ''}`}>
          {current ? current.label : placeholder}
        </span>
        <ChevronDown size={12} className={open ? 'rotate-180 transition-transform' : 'transition-transform'} />
      </button>
      {open && (
        <div className="absolute z-30 top-full left-0 mt-1 min-w-[190px] max-h-72 overflow-y-auto border border-[var(--line-strong)] bg-[var(--surface-2)] p-1 flex flex-col shadow-lg">
          <button onClick={() => { onChange(''); setOpen(false); }}
            className="text-left px-3 py-1.5 hover:bg-[var(--acc-dim)]">
            <span className="label">{placeholder}</span>
          </button>
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
