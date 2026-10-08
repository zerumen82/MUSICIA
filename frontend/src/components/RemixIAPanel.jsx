import React, { useEffect, useState } from 'react';
import { Sparkles, Dices, X } from 'lucide-react';
import { api } from '../api';
import SelectBox from './SelectBox';
import Glossary from './Glossary';
import VariantChips from './VariantChips';
import { glossPrompt } from '../prompt_gloss';

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
  const [styleInfo, setStyleInfo] = useState(null); // capas + chips (del backend)
  const [showTips, setShowTips] = useState(false); // el consejo solo ocupa sitio si se pide

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

  const rollSeed = () => setSeed(Math.floor(Math.random() * 999_999) + 1);

  /** Chips sugeridos mientras escribes: mismo catálogo del backend que en
      CREAR y REMIX (sin LM, sin listas en la UI). Debounce 300 ms. */
  useEffect(() => {
    const t = setTimeout(async () => {
      const info = await api.styleOptions(prompt.trim());
      setStyleInfo(info);
    }, 300);
    return () => clearTimeout(t);
  }, [prompt]);

  /** Cualquier texto (chip o entrada del glosario) se añade al prompt:
      un solo cuadro, todo editable. */
  const addTexto = (text) => {
    const base = prompt.trim();
    setPrompt(base ? `${base} ${text}` : text);
  };
  const addChip = (chip) => addTexto(chip.clause ?? chip.text);

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

  /** Un solo desplegable AÑADIR: todos los chips que sugiere el backend.
      Son vocabulario real del modelo (los valida backend/test_realism.py):
      la lista en español sintético y, al elegir, se añade la cláusula en
      inglés (en el tooltip se ve cuál es la que viaja). */
  const extraOptions = (styleInfo?.chips ?? [])
    .filter((c) => c.suggested)
    .map((c) => ({
      id: `c:${c.label}`, label: c.label, title: `Se añade: «${c.clause ?? c.text}»`,
    }));
  const applyExtra = (id) => {
    const chip = (styleInfo?.chips ?? []).find((c) => c.label === id.slice(2));
    if (chip) addChip(chip);
  };

  return (
    <div className="flex flex-col gap-3 border-t border-[var(--line)] pt-4">
      <span className="label">OTRA VERSIÓN CON IA · PROMPT EDITABLE + SEMILLA</span>

      <textarea
        value={prompt}
        onChange={(e) => setPrompt(e.target.value)}
        placeholder="Describe la versión: nombra el estilo («hardcore», «acústica»…), el patrón («en 4x4») y detalles. Sin estilo, el motor improvisa."
        className="bg-transparent outline-none resize-none text-[13px] leading-relaxed text-zinc-100 placeholder:text-[var(--faint)] min-h-[64px] font-medium border-l-2 border-[var(--acc-line)] pl-3 py-1"
      />
      <div className="flex items-center gap-2 flex-wrap">
        <SelectBox label="AÑADIR" placeholder="DIRECCIÓN O DETALLE" clearable={false}
          options={extraOptions} value="" onChange={applyExtra} />
        <Glossary prompt={prompt} setPrompt={setPrompt} />
        <button type="button" onClick={() => setShowTips((v) => !v)}
          className="mono text-[9.5px] text-[var(--faint)] hover:text-[var(--muted)] ml-auto shrink-0">
          {showTips ? 'OCULTAR CONSEJO' : 'CONSEJO'}
        </button>
      </div>
      <VariantChips prompt={prompt} setPrompt={setPrompt} />
      {prompt.trim() && (
        <div className="mono text-[9px] text-[var(--faint)] break-all leading-relaxed">
          ENVÍA: {glossPrompt(prompt.trim())}
        </div>
      )}
      {prompt.trim() && showTips && (
        <div className="text-[11px] text-[var(--text)] bg-[var(--surface-1)] border border-[var(--line)] rounded px-2 py-1.5">
          💡 <span className="font-medium">Tips:</span> Para conservar voz/guitarra, menciona explícitamente lo que quieres mantener (ej: «manteniendo la voz clara y guitarra principal»). Para cambios de estilo dramaticos (ej: a hardstyle), usa fuerza 0,3-0,5 en el panel de remix. Para cambios sutiles, usa 0,7-0,9.
        </div>
      )}
      {styleInfo && (styleInfo.detected_genre || styleInfo.modifiers?.length > 0) && (
        <div className="mono text-[10px]">
          {styleInfo.detected_genre && (
            <span className="text-[var(--acc)]">
              ESTILO: {styleInfo.detected_genre}{styleInfo.suggested_bpm ? ` · ${styleInfo.suggested_bpm} bpm` : ''}
            </span>
          )}
          {styleInfo.detected_genre && styleInfo.modifiers?.length > 0 && <span className="text-[var(--faint)]"> · </span>}
          {styleInfo.modifiers?.length > 0 && (
            <span className="text-[var(--muted)]">{styleInfo.modifiers.join(', ')}</span>
          )}
        </div>
      )}

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
