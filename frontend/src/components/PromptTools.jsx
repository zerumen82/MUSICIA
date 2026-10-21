import React, { useEffect, useState } from 'react';
import { api, PROMPT_PREVIEW_DEBOUNCE_MS } from '../api';
import Glossary from './Glossary';
import { applyModelTerm } from '../glossary_pick';
import SelectBox from './SelectBox';
import VariantChips from './VariantChips';

/** Details remain editable; preparation never writes derived prose into them. */
export default function PromptTools({ prompt, setPrompt, prepared, disabled = false }) {
  const [options, setOptions] = useState(null);
  useEffect(() => {
    let active = true;
    const timer = setTimeout(async () => {
      const data = await api.styleOptions(prompt.trim());
      if (active) setOptions({ prompt, data });
    }, PROMPT_PREVIEW_DEBOUNCE_MS);
    return () => { active = false; clearTimeout(timer); };
  }, [prompt]);
  const chips = (options?.prompt === prompt ? options.data?.chips ?? [] : []).filter((chip) => chip.suggested);
  const add = (id) => {
    const chip = chips.find((item) => item.label === id);
    if (chip) setPrompt((text) => applyModelTerm(text, chip.clause ?? chip.text));
  };
  const selection = prepared.selection;
  const remove = (term) => prepared.setSelection((current) => ({
    ...current, main_style: current.main_style === term ? null : current.main_style,
    influence_styles: current.influence_styles.filter((item) => item !== term),
  }));
  return <fieldset disabled={disabled} className="flex flex-col gap-2 min-w-0 border-0 p-0" data-prompt-tools>
    <div className="flex items-center gap-2 flex-wrap">
      <Glossary prompt={prompt} setPrompt={setPrompt} selection={selection} setSelection={prepared.setSelection} />
      {chips.length > 0 ? <SelectBox label="AÑADIR" placeholder="DETALLE OPCIONAL" clearable={false} value="" options={chips.map((chip) => ({ id: chip.label, label: chip.label, title: `Se añade: «${chip.clause ?? chip.text}»` }))} onChange={add} />
        : <span className="label">AÑADIR · {options?.data ? 'SIN SUGERENCIAS' : 'SIN DATOS DEL MOTOR'}</span>}
    </div>
    <div className="flex items-center gap-2 flex-wrap" data-style-selection>
      <span className="label">PRINCIPAL: {selection.main_style || 'SIN ELEGIR'}</span>
      {selection.main_style && <button type="button" aria-label="Quitar estilo principal" onClick={() => remove(selection.main_style)} className="btn btn-ghost h-7 px-2">×</button>}
      {selection.influence_styles.map((term) => <button type="button" key={term} onClick={() => remove(term)} className="btn btn-ghost h-7 px-2">MATIZ: {term} ×</button>)}
    </div>
    <button type="button" onClick={() => prepared.setSelection((current) => ({ ...current, include_descriptions: !current.include_descriptions }))} className="btn btn-ghost h-7 px-2 self-start" data-description-toggle>
      {selection.include_descriptions ? 'QUITAR DESCRIPCIÓN' : 'AÑADIR DESCRIPCIÓN DEL CATÁLOGO'}
    </button>
    {prepared.pending && <p role="status" className="mono text-[10px]">PREPARANDO PROMPT…</p>}
    {prepared.retrying && <p role="status" className="mono text-[10px]">REINTENTANDO CONEXIÓN PARA PREPARAR EL PROMPT…</p>}
    {(prepared.result?.warnings ?? []).map((warning) => <p key={warning} className="mono text-[10px] text-[var(--warn)]">{warning}</p>)}
    {prepared.error && <p role="alert" className="mono text-[10px] st-err">{prepared.error}</p>}
    <details><summary className="label cursor-pointer">SUGERENCIAS OPTATIVAS</summary>
      <div className="flex flex-col gap-2 py-2"><VariantChips prompt={prompt} setPrompt={setPrompt} /></div>
    </details>
  </fieldset>;
}
