import React, { useCallback, useEffect, useState } from 'react';
import { Play, Pause, Loader2, AlertTriangle, SlidersHorizontal, Download, Layers } from 'lucide-react';
import { api } from '../api';

/**
 * Mixer real: conecta con POST /audio/mix (pydub, mezcla 2 pistas con
 * ganancia en dB). Elige base (biblioteca) + voz (subidas) y mezcla.
 */
export default function MixLab() {
  const [library, setLibrary] = useState([]);
  const [uploads, setUploads] = useState([]);
  const [base, setBase] = useState(null);
  const [vocal, setVocal] = useState(null);
  const [baseVol, setBaseVol] = useState(0);
  const [vocalVol, setVocalVol] = useState(0);
  const [mixing, setMixing] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);

  const refresh = useCallback(async () => {
    try {
      const [lib, ups] = await Promise.all([api.library(), api.uploads()]);
      setLibrary(lib.items ?? []);
      setUploads(ups.items ?? []);
    } catch (e) {
      setError(e.message);
    }
  }, []);

  useEffect(() => { void refresh(); }, [refresh]);

  const canMix = base && vocal && !mixing;

  const doMix = async () => {
    setError(null);
    setResult(null);
    setMixing(true);
    try {
      const name = `mix-${Date.now()}.mp3`;
      const res = await api.mixTracks({
        base_track: base,
        vocal_track: vocal,
        output_name: name,
        base_volume: baseVol,
        vocal_volume: vocalVol,
      });
      // El backend devuelve file_path; el nombre real viene ahí:
      const realName = String(res.file_path ?? name).split(/[\\/]/).pop();
      setResult(realName);
      await refresh();
    } catch (e) {
      setError(e.message);
    } finally {
      setMixing(false);
    }
  };

  return (
    <div className="h-full overflow-y-auto">
      <div className="max-w-[1300px] mx-auto w-full px-16 py-12 flex flex-col gap-6">
        <div className="flex items-center gap-4">
          <h2 className="h-title text-[20px]">MIX</h2>
          <span className="mono text-[12px] text-[var(--faint)]">instrumental + voz = canción completa</span>
        </div>

        {error && (
          <div className="flex items-center gap-2 text-red-300 mono text-[11px] py-2 border-y border-[rgba(255,92,92,0.35)]">
            <AlertTriangle size={14} /> {error}
          </div>
        )}

        <div className="grid grid-cols-2 gap-8">
          {/* Base */}
          <div className="flex flex-col gap-3">
            <span className="label">1 · BASE (de tu biblioteca)</span>
            {library.length === 0 && (
              <p className="mono text-[10px] text-[var(--faint)]">Sin pistas. Genera una en CREAR.</p>
            )}
            {library.map((item) => (
              <button key={item.name} onClick={() => setBase(item.name)}
                className={`text-left px-3 py-2 border transition-colors ${base === item.name ? 'border-[var(--acc-line)] bg-[var(--acc-dim)]' : 'border-[var(--line)] hover:border-[var(--line-strong)]'}`}>
                <span className="block mono text-[11px] text-zinc-200 truncate">{item.name}</span>
              </button>
            ))}
            {base && (
              <div className="flex items-center gap-3">
                <span className="label shrink-0">VOLUMEN</span>
                <input type="range" min={-24} max={12} step={1} value={baseVol}
                  onChange={(e) => setBaseVol(Number(e.target.value))} className="flex-1" />
                <span className={`num w-14 text-right ${baseVol > 0 ? 'st-warn' : ''}`}>{baseVol > 0 ? '+' : ''}{baseVol} dB</span>
              </div>
            )}
          </div>

          {/* Voz */}
          <div className="flex flex-col gap-3">
            <span className="label">2 · VOZ (de tus subidas)</span>
            {uploads.length === 0 && (
              <p className="mono text-[10px] text-[var(--faint)]">Sin subidas. Sube tu voz en UPLOADS.</p>
            )}
            {uploads.map((item) => (
              <button key={item.name} onClick={() => setVocal(item.name)}
                className={`text-left px-3 py-2 border transition-colors ${vocal === item.name ? 'border-[var(--acc-line)] bg-[var(--acc-dim)]' : 'border-[var(--line)] hover:border-[var(--line-strong)]'}`}>
                <span className="block mono text-[11px] text-zinc-200 truncate">{item.name}</span>
              </button>
            ))}
            {vocal && (
              <div className="flex items-center gap-3">
                <span className="label shrink-0">VOLUMEN</span>
                <input type="range" min={-24} max={12} step={1} value={vocalVol}
                  onChange={(e) => setVocalVol(Number(e.target.value))} className="flex-1" />
                <span className={`num w-14 text-right ${vocalVol > 0 ? 'st-warn' : ''}`}>{vocalVol > 0 ? '+' : ''}{vocalVol} dB</span>
              </div>
            )}
          </div>
        </div>

        {/* Mezclar */}
        <div className="flex items-center gap-4 pt-4 border-t border-[var(--line)]">
          <button onClick={doMix} disabled={!canMix} className="btn btn-signal h-10 px-7">
            {mixing ? <><Loader2 size={14} className="animate-spin" /> MEZCLANDO…</>
              : <><Layers size={14} /> MEZCLAR</>}
          </button>
          {!base || !vocal ? (
            <span className="mono text-[10px] text-[var(--faint)]">elige una base y una voz para mezclar</span>
          ) : (
            <span className="mono text-[10px] text-[var(--faint)]">{base} + {vocal}</span>
          )}
        </div>

        {result && (
          <div className="flex items-center gap-4 py-4 border-t border-[var(--line)] fade-up">
            <div className="w-10 h-10 rounded-[4px] bg-[var(--acc-dim)] border border-[var(--acc-line)] flex items-center justify-center shrink-0">
              <SlidersHorizontal size={16} className="text-[var(--acc)]" />
            </div>
            <div className="flex-1 min-w-0">
              <p className="mono text-[10px] tracking-[0.12em] text-[var(--acc)] mb-1.5">MEZCLA LISTA · {result}</p>
              <audio key={result} controls autoPlay src={api.audioUrl(result)} className="player" />
            </div>
            <a href={api.audioUrl(result)} download className="btn btn-ghost h-9 px-3 shrink-0"><Download size={13} /> MP3</a>
          </div>
        )}
      </div>
    </div>
  );
}
