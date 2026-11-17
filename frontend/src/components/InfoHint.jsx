import React from 'react';
import { Info } from 'lucide-react';

/** Icono circulado i con la información al pasar el ratón por encima (y al
 *  recibir foco, para teclado). Sustituye a los desplegables ⓘ: la información
 *  se ve sin clic y no ocupa sitio hasta que hace falta. */
export default function InfoHint({ children, label = 'Más información' }) {
  return <span className="relative inline-flex group items-center" tabIndex={0} aria-label={label}>
    <Info size={13} aria-hidden="true" className="text-[var(--muted)] group-hover:text-[var(--acc)] cursor-help shrink-0 transition-colors" />
    <span role="tooltip"
      className="pointer-events-none absolute left-0 top-full z-50 mt-1.5 w-72 rounded border border-[var(--line-strong)] bg-[var(--surface)] p-2.5 text-[11px] leading-snug text-[var(--text)] shadow-lg opacity-0 group-hover:opacity-100 group-focus-within:opacity-100">
      {children}
    </span>
  </span>;
}
