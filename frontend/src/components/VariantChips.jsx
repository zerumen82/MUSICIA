import React from 'react';
import { X } from 'lucide-react';
import { VARIANTS, toggleVariantText } from '../variants';

/**
 * Fila de VARIANTES compartida por CREAR, remix y OTRA VERSIÓN: mismos
 * botones en los tres sitios y mismo comportamiento que los chips (lo que
 * ya está en tu frase se marca y se quita de un clic).
 */
export default function VariantChips({ prompt, setPrompt, className = '' }) {
  const texto = prompt ?? '';
  const activas = VARIANTS.filter((v) => texto.toLowerCase().includes(v.add.toLowerCase()));
  const alternar = (add) => setPrompt(toggleVariantText(texto, add));

  return (
    <div className={`flex items-center gap-1.5 flex-wrap ${className}`}>
      <span className="label shrink-0">VARIANTES</span>
      {VARIANTS.map((v) => {
        const activa = activas.some((a) => a.id === v.id);
        return (
          <button key={v.id} type="button" onClick={() => alternar(v.add)}
            title={activa ? `Quitar «${v.add}»` : `Añade: ${v.add}`}
            className={`btn btn-ghost h-3.5 px-1.5 text-[8px] leading-none gap-1 ${activa ? '!border-[var(--acc-line)] !text-[var(--text)]' : ''}`}>
            {v.label}
            {activa && <X size={9} />}
          </button>
        );
      })}
    </div>
  );
}
