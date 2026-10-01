import React, { useState } from 'react';
import { Loader2, SlidersHorizontal } from 'lucide-react';
import Waveform from './Waveform';

/**
 * Panel de remix DSP compartido (tempo/tono/volumen/fundidos/invertir +
 * recorte visual). onRun recibe los parámetros y hace la llamada.
 */
export default function RemixPanel({ onRun, result, fileName }) {
  const [tempo, setTempo] = useState(1.0);
  const [pitch, setPitch] = useState(0);
  const [gain, setGain] = useState(0);
  const [reverse, setReverse] = useState(false);
  const [fadeIn, setFadeIn] = useState(0);
  const [fadeOut, setFadeOut] = useState(0);
  const [trim, setTrim] = useState({ trim_start_s: 0, trim_end_s: null });
  const [running, setRunning] = useState(false);

  const onSelection = (sel) => {
    setTrim({ trim_start_s: sel.trim_start_s, trim_end_s: sel.trim_end_s });
  };

  const run = async () => {
    setRunning(true);
    await onRun({
      tempo,
      pitch_semitones: pitch,
      gain_db: gain,
      reverse,
      fade_in_ms: fadeIn,
      fade_out_ms: fadeOut,
      trim_start_s: trim.trim_start_s,
      trim_end_s: trim.trim_end_s === '' || trim.trim_end_s === null ? null : Number(trim.trim_end_s),
    });
    setRunning(false);
  };

  const dirty = tempo !== 1.0 || pitch !== 0 || gain !== 0 || reverse || fadeIn > 0 || fadeOut > 0
    || trim.trim_start_s > 0 || (trim.trim_end_s !== null && trim.trim_end_s !== '');

  return (
    <div className="flex flex-col gap-4 pt-4">
      {fileName && <Waveform key={fileName} fileName={fileName} onSelection={onSelection} />}
      <div className="flex items-center gap-3">
        <span className="label shrink-0">VELOCIDAD</span>
        <input type="range" min={0.5} max={2} step={0.05} value={tempo}
          onChange={(e) => setTempo(Number(e.target.value))} className="flex-1 min-w-0" />
        <span className="num w-14 text-right">{tempo.toFixed(2)}×</span>
      </div>
      <div className="flex items-center gap-3">
        <span className="label shrink-0">TONO</span>
        <input type="range" min={-12} max={12} step={1} value={pitch}
          onChange={(e) => setPitch(Number(e.target.value))} className="flex-1 min-w-0" />
        <span className="num w-14 text-right">{pitch > 0 ? '+' : ''}{pitch} st</span>
      </div>
      <div className="flex items-center gap-3">
        <span className="label shrink-0">VOLUMEN</span>
        <input type="range" min={-24} max={24} step={1} value={gain}
          onChange={(e) => setGain(Number(e.target.value))} className="flex-1 min-w-0" />
        <span className={`num w-14 text-right ${gain > 0 ? 'st-warn' : ''}`}>{gain > 0 ? '+' : ''}{gain} dB</span>
      </div>
      <div className="flex items-center gap-3">
        <span className="label shrink-0">FUNDIDOS</span>
        <input type="range" min={0} max={6000} step={250} value={fadeIn}
          onChange={(e) => setFadeIn(Number(e.target.value))} className="w-28" />
        <span className="mono text-[10px] text-[var(--faint)] w-10">in {fadeIn / 1000}s</span>
        <input type="range" min={0} max={6000} step={250} value={fadeOut}
          onChange={(e) => setFadeOut(Number(e.target.value))} className="w-28" />
        <span className="mono text-[10px] text-[var(--faint)] w-10">out {fadeOut / 1000}s</span>
        <button onClick={() => setReverse(!reverse)}
          className={`btn h-8 px-3 shrink-0 ${reverse ? 'btn-signal' : 'btn-ghost'}`}>
          INVERTIR
        </button>
      </div>
      <div className="flex items-center gap-3">
        <button onClick={run} disabled={!dirty || running} className="btn btn-signal h-10 px-6">
          {running ? <><Loader2 size={13} className="animate-spin" /> PROCESANDO…</> : <><SlidersHorizontal size={13} /> APLICAR REMIX</>}
        </button>
        {!dirty && !running && <span className="mono text-[10px] text-[var(--faint)]">ajusta algún control para poder aplicar</span>}
        {running && <span className="mono text-[10px] text-[var(--muted)]">procesando en local (puede tardar según la duración)…</span>}
      </div>
      {result?.ok === false && <p className="mono text-[10.5px] st-err">{result.error}</p>}
    </div>
  );
}
