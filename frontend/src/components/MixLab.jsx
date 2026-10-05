import React, { useCallback, useEffect, useState } from 'react';
import {
  Play, Pause, Loader2, AlertTriangle, Download, Layers, Scissors, AlignLeft, Check,
} from 'lucide-react';
import { api, isTransportBlip } from '../api';
import SelectBox from './SelectBox';

/**
 * MIX en una sola línea (el usuario pidió no saturar la pantalla):
 * BASE ▾ · VOZ ▾ · volumen · CUADRAR ▾ · -14 LUFS · MEZCLAR.
 * Debajo, solo si hace falta: el plan de cuadre explicado y el resultado.
 */
export default function MixLab() {
  const [library, setLibrary] = useState([]);
  const [uploads, setUploads] = useState([]);
  const [base, setBase] = useState('');
  const [vocal, setVocal] = useState('');
  const [baseVol, setBaseVol] = useState(0);
  const [vocalVol, setVocalVol] = useState(0);
  const [mixing, setMixing] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);
  const [plan, setPlan] = useState(null);        // propuesta de cuadre
  const [arrange, setArrange] = useState(null);  // trozos, si la base es más larga
  const [planNote, setPlanNote] = useState(null);
  const [planning, setPlanning] = useState(false);
  const [align, setAlign] = useState('si');      // si | no  (decidir antes de mezclar)
  const [normalize, setNormalize] = useState(true);
  const [separator, setSeparator] = useState(null); // {available, device}
  const [separating, setSeparating] = useState(false);
  const [stems, setStems] = useState(null);      // {vocals, base}
  const [fadeTracks, setFadeTracks] = useState([]); // crossfade: 2+ pistas
  const [fading, setFading] = useState(false);
  const [fadeNote, setFadeNote] = useState(null);
  const [mixName, setMixName] = useState('');

  const refresh = useCallback(async () => {
    try {
      const [lib, ups, sep] = await Promise.all([api.library(), api.uploads(), api.separateStatus()]);
      setLibrary(lib.items ?? []);
      setUploads(ups.items ?? []);
      setSeparator(sep);
    } catch (e) {
      if (!isTransportBlip(e.message)) setError(e.message);
    }
  }, []);

  useEffect(() => { void refresh(); }, [refresh]);

  const canMix = base && vocal && !mixing;

  // La UI sabe de qué lista viene cada pista: la mezcla no toca homónimos.
  const kindOf = useCallback(
    (name) => (library.some((i) => i.name === name) ? 'output' : 'upload'),
    [library],
  );

  // Al elegir base y voz se pide la propuesta de cuadre (no se mezcla nada).
  useEffect(() => {
    if (!base || !vocal) { setPlan(null); setArrange(null); setPlanNote(null); return undefined; }
    let active = true;
    setPlanning(true);
    api.mixPlan({ base_track: base, vocal_track: vocal, base_kind: kindOf(base), vocal_kind: kindOf(vocal) })
      .then((d) => { if (active) { setPlan(d.plan); setArrange(d.arrange ?? null); setPlanNote(d.explanation); } })
      .catch((e) => { if (active) { setPlan(null); setArrange(null); setPlanNote(`No pude calcular el cuadre: ${e.message}`); } })
      .finally(() => { if (active) setPlanning(false); });
    return () => { active = false; };
  }, [base, vocal, kindOf]);

  const doMix = async () => {
    setError(null);
    setResult(null);
    setMixing(true);
    try {
      const res = await api.mixTracks({
        base_track: base,
        vocal_track: vocal,
        base_kind: kindOf(base),
        vocal_kind: kindOf(vocal),
        output_name: mixName.trim() ? mixName.trim() : null,
        base_volume: baseVol,
        vocal_volume: vocalVol,
        align: align === 'si',
        normalize_lufs: normalize,
      });
      setResult(res.file_name ?? res.file_path);
      await refresh();
    } catch (e) {
      setError(e.message);
    } finally {
      setMixing(false);
    }
  };

  const doSeparate = async () => {
    setError(null);
    setSeparating(true);
    try {
      const res = await api.separate({ file_name: base, source_kind: kindOf(base), output_name: `${base.replace(/\.[^.]+$/, '')}-separado` });
      setStems(res);
      setBase(res.base);
      setVocal(res.vocals);
      await refresh();
    } catch (e) {
      setError(e.message);
    } finally {
      setSeparating(false);
    }
  };

  const trackOptions = () => {
    const libNames = new Set(library.map((i) => i.name));
    const fromLib = library.map((i) => ({ id: i.name, label: `${i.name} · bib`, title: `biblioteca · ${i.name}` }));
    const fromUp = uploads
      .filter((i) => !libNames.has(i.name))
      .map((i) => ({ id: i.name, label: `${i.name} · sub`, title: `subida · ${i.name}` }));
    return [...fromLib, ...fromUp];
  };

  const toggleFadeTrack = (name) => {
    setFadeTracks((prev) => (prev.includes(name)
      ? prev.filter((n) => n !== name)
      : [...prev, name].slice(-4)));
  };

  const doCrossfade = async () => {
    setError(null);
    setFading(true);
    try {
      const res = await api.crossfade({ tracks: fadeTracks, track_kinds: fadeTracks.map(kindOf) });
      setFadeNote(res.note ?? null);
      setResult(res.file_name);
      await refresh();
    } catch (e) {
      setError(e.message);
    } finally {
      setFading(false);
    }
  };
  const ALIGN_OPTIONS = [
    { id: 'si', label: 'CUADRAR', title: 'Igala el tempo y el golpe de la batería' },
    { id: 'no', label: 'SIN CUADRAR', title: 'Mezcla tal cual, sin tocar el tempo' },
  ];

  return (
    <div className="h-full overflow-y-auto">
      <div className="max-w-[1300px] mx-auto w-full px-6 py-8 xl:px-10 flex flex-col gap-5">
        <div className="flex items-center gap-4">
          <h2 className="h-title text-[20px]">MEZCLA</h2>
          <span className="mono text-[12px] text-[var(--faint)]">si la base es más larga, la voz se corta en trozos y se reparte</span>
        </div>

        {error && (
          <div className="flex items-center gap-2 text-red-300 mono text-[11px] py-2 border-y border-[rgba(255,92,92,0.35)]">
            <AlertTriangle size={14} /> {error}
          </div>
        )}

        {/* TODO EN UNA LÍNEA */}
        <div className="flex items-center gap-3 flex-wrap border border-[var(--line)] px-4 py-3">
          <SelectBox label="BASE" options={trackOptions()} value={base}
            onChange={setBase} placeholder="elige la base" />
          <SelectBox label="VOZ" options={trackOptions()} value={vocal}
            onChange={setVocal} placeholder="elige la voz cantada" />
          <input value={mixName} onChange={(e) => setMixName(e.target.value)} placeholder="nombre del mp3" aria-label="Nombre de la mezcla"
            className="px-2 py-1.5 w-36 text-[12px] mono bg-transparent outline-none border border-[var(--line)] focus:border-[var(--acc-line)]" />

          <div className="flex items-center gap-2">
            <span className="label">BASE</span>
            <input type="range" min={-24} max={12} step={1} value={baseVol}
              onChange={(e) => setBaseVol(Number(e.target.value))} className="w-20" />
            <span className="num w-12 text-right">{baseVol > 0 ? '+' : ''}{baseVol} dB</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="label">VOZ</span>
            <input type="range" min={-24} max={12} step={1} value={vocalVol}
              onChange={(e) => setVocalVol(Number(e.target.value))} className="w-20" />
            <span className="num w-12 text-right">{vocalVol > 0 ? '+' : ''}{vocalVol} dB</span>
          </div>

          <SelectBox options={ALIGN_OPTIONS} value={align} onChange={setAlign} clearable={false} />
          <button onClick={() => setNormalize((v) => !v)}
            className={`btn btn-ghost h-8 px-2.5 gap-1.5 ${normalize ? '!border-[var(--acc-line)] !text-[var(--text)]' : ''}`}
            title="Normaliza el volumen final a -14 LUFS con pico máximo -1 dBTP">
            {normalize ? <Check size={12} /> : null} -14 LUFS
          </button>

          <button onClick={doMix} disabled={!canMix} className="btn btn-signal h-9 px-5 ml-auto">
            {mixing ? <><Loader2 size={14} className="animate-spin" /> MEZCLANDO…</>
              : <><Layers size={14} /> MEZCLAR</>}
          </button>
        </div>

        {/* Segunda línea: acciones de estudio */}
        <div className="flex items-center gap-3 flex-wrap">
          <button onClick={doSeparate} disabled={!base || separating || !separator?.available}
            className="btn btn-ghost h-8 px-3 gap-1.5"
            title={separator?.available
              ? 'Separa la voz de la base con el motor local (1-3 min la primera vez)'
              : 'Motor de separación no instalado: no se puede extraer'}>
            {separating ? <><Loader2 size={12} className="animate-spin" /> SEPARANDO…</>
              : <><Scissors size={12} /> EXTRAER VOCES DE LA BASE</>}
          </button>
          {separator?.available && (
            <span className="mono text-[10px] text-[var(--faint)]">
              separación lista ({separator.device === 'cuda' ? 'GPU' : 'CPU'})
            </span>
          )}
          {stems && (
            <span className="mono text-[10px] text-[var(--acc)]">
              ya tienes: {stems.vocals} + {stems.base}
            </span>
          )}
          {planning && <span className="mono text-[10px] text-[var(--faint)]">midiendo el groove…</span>}
        </div>

        {/* CROSSFADE: marca 2+ pistas y las funde (estilo DJ) */}
        <div className="flex items-start gap-3 flex-wrap border border-[var(--line)] px-4 py-3">
          <span className="label shrink-0 pt-2">FUNDIR</span>
          <div className="flex flex-wrap gap-2 flex-1 min-w-0 max-h-28 overflow-y-auto">
            {(() => {
              const seen = new Set();
              return [...library, ...uploads].filter((item) => {
                if (seen.has(item.name)) return false;
                seen.add(item.name);
                return true;
              });
            })().map((item) => (
              <button key={item.name} onClick={() => toggleFadeTrack(item.name)}
                className={`btn btn-ghost h-7 px-2 ${fadeTracks.includes(item.name) ? '!border-[var(--acc-line)] !text-[var(--text)]' : ''}`}
                title={item.name}>
                <span className="mono text-[10.5px]">{item.name.replace(/\.[^.]+$/, '').slice(0, 28)}</span>
              </button>
            ))}
          </div>
          <button onClick={doCrossfade} disabled={fadeTracks.length < 2 || fading}
            className="btn btn-signal h-8 px-4 ml-auto">
            {fading ? <><Loader2 size={13} className="animate-spin" /> FUNDIENDO…</>
              : <><Play size={12} /> FUNDIR {fadeTracks.length || ''}</>}
          </button>
          <span className="mono text-[10px] text-[var(--faint)] basis-full">Iguala el tempo solo si el ajuste es pequeño. Si no, la pista se queda a su tempo.</span>
          {fadeNote && <span className="mono text-[10px] text-[var(--muted)] basis-full">{fadeNote}</span>}
        </div>

        {/* Lo que se va a hacer (transparencia antes de mezclar) */}
          {planNote && (
            <div className="flex items-start gap-2 border-l-2 border-[var(--acc-line)] pl-4 py-1">
              <AlignLeft size={13} className="text-[var(--acc)] mt-0.5 shrink-0" />
              <div>
                <span className="label">{arrange ? 'SE COLOCAN LOS TROZOS' : align === 'si' ? 'SE VA A CUADRAR ASÍ' : 'NO SE CUADRA'}</span>
                <p className="mono text-[10.5px] text-[var(--muted)] leading-relaxed">{planNote}</p>
                {arrange && (
                  <p className="mono text-[10px] text-[var(--faint)] mt-1">
                    {arrange.pieces} trozos · voz {Math.round(arrange.vocal_seconds)} s · base {Math.round(arrange.base_seconds)} s ·
                    {' '}de {arrange.first_at} s a {arrange.last_at} s
                  </p>
                )}
                {plan && !arrange && (
                  <p className="mono text-[10px] text-[var(--faint)] mt-1">
                    tempo ×{plan.tempo_ratio.toFixed(3)} · desfase {plan.delay_ms > 0 ? '+' : ''}{plan.delay_ms} ms ·
                    {' '}compás {plan.period_ms} ms · seguridad groove {Math.round((plan.base_confidence ?? 0) * 100)}%
                  </p>
                )}
              </div>
            </div>
          )}

        {result && (
          <div className="flex items-center gap-4 py-4 border-t border-[var(--line)] fade-up">
            <div className="w-10 h-10 rounded-[4px] bg-[var(--acc-dim)] border border-[var(--acc-line)] flex items-center justify-center shrink-0">
              <Layers size={16} className="text-[var(--acc)]" />
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
