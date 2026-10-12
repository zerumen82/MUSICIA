import React, { useEffect, useState } from 'react';
import { api, PROMPT_PREVIEW_DEBOUNCE_MS } from '../api';
import Glossary from './Glossary';
import SelectBox from './SelectBox';
import VariantChips from './VariantChips';

/** Herramientas optativas disponibles también en base nueva y acompañamiento. */
export default function PromptTools({ prompt, setPrompt, bpm = null, disabled = false }) {
  const [options, setOptions] = useState(null);
  const [draft, setDraft] = useState(null);
  const [error, setError] = useState(null);
  const [enhancing, setEnhancing] = useState(false);
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
    if (chip) setPrompt((text) => `${text.trim()} ${chip.clause ?? chip.text}`.trim());
  };
  const improve = async () => {
    setEnhancing(true); setError(null);
    const original = prompt;
    try { setDraft({ original, bpm, result: await api.enhancePrompt({ prompt: original.trim(), bpm }) }); }
    catch (err) { setError(err.message); }
    finally { setEnhancing(false); }
  };
  const currentDraft = draft?.original === prompt && draft?.bpm === bpm ? draft.result : null;
  return <fieldset disabled={disabled} className="flex flex-col gap-2 min-w-0 border-0 p-0" data-prompt-tools>
    <div className="flex items-center gap-2 flex-wrap">
      <Glossary prompt={prompt} setPrompt={setPrompt} />
      {chips.length > 0 ? <SelectBox label="AÑADIR" placeholder="DETALLE OPCIONAL" clearable={false} value="" options={chips.map((chip) => ({ id: chip.label, label: chip.label, title: `Se añade: «${chip.clause ?? chip.text}»` }))} onChange={add} />
        : <span className="label">AÑADIR · {options?.data ? 'SIN SUGERENCIAS' : 'SIN DATOS DEL MOTOR'}</span>}
      <button type="button" disabled={enhancing || prompt.trim().length < 3} onClick={() => void improve()} className="btn btn-ghost h-7 px-2">{enhancing ? 'PREPARANDO…' : 'MEJORAR PROMPT'}</button>
    </div>
    <details><summary className="label cursor-pointer">SUGERENCIAS OPTATIVAS</summary><VariantChips prompt={prompt} setPrompt={setPrompt} /></details>
    {currentDraft && <div className="border border-[var(--line)] p-3 flex flex-col gap-2">
      <p className="mono text-[11px] whitespace-pre-wrap">{currentDraft.enhanced}</p>
      {(currentDraft.warnings ?? []).map((warning) => <p key={warning} className="mono text-[10px] text-[var(--warn)]">{warning}</p>)}
      <div className="flex gap-2"><button type="button" onClick={() => { setPrompt(currentDraft.enhanced); setDraft(null); }} className="btn btn-ghost h-7 px-2">APLICAR BORRADOR</button><button type="button" onClick={() => setDraft(null)} className="btn btn-ghost h-7 px-2">DESCARTAR</button></div>
    </div>}
    {error && <p role="alert" className="mono text-[10px] st-err">{error}</p>}
  </fieldset>;
}
