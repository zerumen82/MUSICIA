import React, { useEffect, useState } from 'react';
import { Sparkles, Dices, X } from 'lucide-react';
import { api } from '../api';
import SelectBox from './SelectBox';

// Variantes que REESCRIBEN el prompt con una dirección musical clara.
// Se aplican como chips conmutables sobre el texto actual.
const VARIANTS = [
  { id: 'energia', label: 'MÁS ENERGÍA', add: 'más enérgica, ritmo acelerado y con pegada' },
  { id: 'calma', label: 'MÁS CALMA', add: 'más tranquila y espaciosa, tempo relajado' },
  { id: 'oscura', label: 'OSCURA', add: 'ambiente oscuro y melancólico, armonías en tono menor' },
  { id: 'luminosa', label: 'LUMINOSA', add: 'luminosa y optimista, armonías abiertas' },
  { id: 'acustica', label: 'ACÚSTICA', add: 'instrumentación acústica, guitarras y cuerdas naturales' },
  { id: 'electronica', label: 'ELECTRÓNICA', add: 'producción electrónica, sintetizadores y beats programados' },
  { id: 'orquestal', label: 'ORQUESTAL', add: 'arreglos orquestales, cuerdas y percusión cinematográfica' },
  { id: 'lofi', label: 'LO-FI', add: 'estética lo-fi, textura cálida con ruido de vinilo' },
  { id: 'epica', label: 'ÉPICA', add: 'escalado épico, dinámica creciente y clímax final' },
  { id: 'minimal', label: 'MINIMAL', add: 'arreglo minimalista, pocos elementos y mucho aire' },
];

const escapeRe = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

/**
 * Panel de re-creación con IA, compartido por SUBIR y BIBLIOTECA.
 * - Pide al backend un prompt sugerido desde el análisis DSP real (/audio/remix_prompt).
 * - El textarea SIEMPRE está visible y editable (touched evita sobreescribir).
 * - Chips de variantes que añaden/quitan dirección musical en el prompt.
 * - Dado de semilla: cada lanzamiento con semilla distinta produce otra versión.
 * - onLaunch({ prompt, seed, duration_seconds, bpm, source_kind }) lo cablea cada pantalla.
 * - sourceKind ('upload' | 'output') dice de qué lista viene el archivo.
 */
export default function RemixIAPanel({ fileName, kind = 'musica', sourceKind = null, onLaunch, generating = false, jobNote = null, initialPrompt = '', initialLyrics = '', showLyrics = false }) {
  const [prompt, setPrompt] = useState(initialPrompt);
  const [basis, setBasis] = useState(null);
  const [note, setNote] = useState(null);
  const [seed, setSeed] = useState(null);
  const [name, setName] = useState(''); // nombre del MP3; vacío = pista-sin-nombre numerado
  const [lyrics, setLyrics] = useState(initialLyrics); // letra opcional: con letra canta, sin ella es instrumental
  const [launching, setLaunching] = useState(false);

  // Con voz: el motor solo canta si le llega letra; sin ella hace instrumental.
  const conVoz = kind === 'voz' || kind === 'mixta';

  useEffect(() => {
    let active = true;
    api.remixPrompt({ file_name: fileName, kind, source_kind: sourceKind })
      .then((d) => {
        if (!active) return;
        setBasis(d.basis ?? null);
        setPrompt((p) => p || d.prompt || '');
      })
      .catch(() => {
        if (active) setNote('Sugerencia automática no disponible; escribe tu prompt libremente.');
      });
    return () => { active = false; };
  }, [fileName, kind, sourceKind]);

  const toggleVariant = (add) => {
    setPrompt((p) => {
      const has = p.toLowerCase().includes(add.toLowerCase());
      if (has) {
        const re = new RegExp(`(,\\s*)?${escapeRe(add)}`, 'i');
        return p.replace(re, '').replace(/,\s*,/g, ',').replace(/^[\s,]+|[\s,]+$/g, '');
      }
      return p ? `${p}, ${add}` : add;
    });
  };

  const rollSeed = () => setSeed(Math.floor(Math.random() * 999_999) + 1);

  const launch = async () => {
    if (launching || generating || !prompt.trim()) return;
    setLaunching(true);
    try {
      await onLaunch({
        prompt: prompt.trim(),
        seed,
        name: name.trim() || null,
        lyrics: lyrics.trim() || null,
        source_kind: sourceKind,
      });
    } finally {
      setLaunching(false);
    }
  };

  const busy = launching || generating;

  return (
    <div className="flex flex-col gap-3 border-t border-[var(--line)] pt-4">
      <span className="label">OTRA VERSIÓN CON IA · PROMPT EDITABLE + SEMILLA</span>

      <div className="flex items-center gap-2 flex-wrap">
        <SelectBox label="DIRECCIÓN" placeholder="AÑADIR" clearable={false}
          options={VARIANTS.map(({ id, label, add }) => ({ id, label, title: add }))}
          value=""
          onChange={(id) => {
            const chosen = VARIANTS.find((v) => v.id === id);
            if (chosen) toggleVariant(chosen.add);
          }} />
        {VARIANTS.filter((v) => prompt.toLowerCase().includes(v.add.toLowerCase())).map((v) => (
          <button key={v.id} type="button" onClick={() => toggleVariant(v.add)}
            className="btn btn-ghost h-8 px-2.5" title="Quitar esta dirección">
            {v.label} <X size={11} />
          </button>
        ))}
      </div>

      <textarea
        value={prompt}
        onChange={(e) => setPrompt(e.target.value)}
        placeholder="Describe cómo quieres la nueva versión: mismo espíritu pero más oscuro, versión acústica…"
        className="bg-transparent outline-none resize-none text-[13.5px] leading-relaxed text-zinc-100 placeholder:text-[var(--faint)] min-h-[88px] font-medium border-l-2 border-[var(--acc-line)] pl-4 py-1.5"
      />

      <div className="flex items-center gap-3 flex-wrap">
        <div className="flex items-center gap-3 flex-1 min-w-[240px]">
          <span className="label shrink-0">NOMBRE</span>
          <input type="text" value={name} onChange={(e) => setName(e.target.value)}
            placeholder={`${String(fileName).replace(/\.[^.]+$/, '').replace(/^[0-9a-f]{8}-/, '')} (versión IA)`}
            title="Nombre del MP3 que se guardará" onKeyDown={(e) => e.key === 'Enter' && launch()}
            className="px-3 py-2 text-[13px] bg-transparent outline-none border border-[var(--line)] focus:border-[var(--acc-line)] flex-1 min-w-0" />
        </div>
      </div>

      {(conVoz || showLyrics) && (
        <div className="flex flex-col gap-2">
          <span className="label">LETRA (con letra canta, vacía es instrumental)</span>
          <textarea value={lyrics} onChange={(e) => setLyrics(e.target.value)}
            placeholder="Escribe la letra… si la dejas vacía solo sonará la base musical"
            className="bg-transparent outline-none resize-none text-[13px] leading-relaxed text-zinc-100 placeholder:text-[var(--faint)] min-h-[70px] font-medium border-l-2 border-[var(--acc-line)] pl-4 py-1.5" />
        </div>
      )}

      <div className="flex items-center gap-3 flex-wrap">
        <button onClick={launch} disabled={busy || !prompt.trim()} className="btn btn-signal h-10 px-6">
          {busy ? <><Sparkles size={13} className="animate-pulse" /> LANZANDO…</>
            : <><Sparkles size={13} /> GENERAR OTRA VERSIÓN</>}
        </button>

        <button onClick={rollSeed} className="btn btn-ghost h-8 px-3" title="Cambia la semilla: misma base, resultado distinto">
          <Dices size={12} /> SEMILLA: {seed ?? 'ALEATORIA'}
        </button>
        {seed != null && (
          <button onClick={() => setSeed(null)} className="btn btn-ghost h-8 px-2" title="Volver a semilla aleatoria">
            <X size={12} />
          </button>
        )}
      </div>

      {basis?.bpm && (
        <p className="mono text-[9.5px] text-[var(--faint)]">
          Medido: {basis.bpm} bpm · {Math.round(basis.duration_seconds ?? 0)}s. No se envía: la versión no hereda ese tempo.
        </p>
      )}
      {note && <p className="mono text-[9.5px] text-[var(--warn)]">{note}</p>}
      {jobNote && <p className="mono text-[10.5px] st-ok">{jobNote}</p>}
    </div>
  );
}
