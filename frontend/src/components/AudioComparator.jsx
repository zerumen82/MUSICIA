import React, { useEffect, useRef, useState } from 'react';
import { comparisonBounds, comparisonPosition, switchComparisonSource } from '../audio_comparison';
import { arrowDirection, nudgePosition } from '../timeline_nudge';

const field = 'px-2 py-1 bg-transparent border border-[var(--line)] w-24 text-[12px]';

/** One media element guarantees that changing A/B never overlaps playback. */
export default function AudioComparator({ tracks, interval = null, nudgeStep = null }) {
  const [selected, setSelected] = useState(null);
  const [metadata, setMetadata] = useState({});
  const [customRange, setCustomRange] = useState(null);
  const [playing, setPlaying] = useState(false);
  const [time, setTime] = useState(0);
  const [error, setError] = useState(null);
  const audio = useRef(null);
  const position = useRef(0);
  const resume = useRef(false);
  const currentBounds = useRef(null);
  const active = tracks.find((track) => track.id === selected) ?? tracks[0];
  const activeUrl = active?.url;
  const signature = `${interval?.start ?? 0}:${interval?.end ?? ''}`;
  const encodedTracks = JSON.stringify(tracks.map(({ url, duration, label }) => ({ url, duration, label })));
  const range = customRange?.signature === signature ? customRange : interval;
  const durations = tracks.map((track) => track.duration ?? metadata[track.url] ?? null);
  const ready = durations.every((duration) => Number.isFinite(duration) && duration > 0);
  const bounds = comparisonBounds(range, durations);
  useEffect(() => {
    const limits = { start: bounds.start, end: bounds.end, valid: bounds.valid && ready };
    currentBounds.current = limits;
    const player = audio.current;
    if (player?.readyState >= 1 && limits.valid) {
      player.currentTime = comparisonPosition(player.currentTime, limits);
      if (resume.current && player.paused) player.play().catch((err) => setError(err.message));
    }
  }, [bounds.start, bounds.end, bounds.valid, ready]);

  useEffect(() => {
    let active = true;
    const probes = JSON.parse(encodedTracks).filter((track) => !track.duration).map((track) => {
      const probe = document.createElement('audio');
      probe.preload = 'metadata';
      probe.onloadedmetadata = () => {
        if (active) setMetadata((current) => ({ ...current, [track.url]: probe.duration }));
      };
      probe.onerror = () => { if (active) setError(`No se puede leer la duración de ${track.label}`); };
      probe.src = track.url;
      return probe;
    });
    return () => {
      active = false;
      probes.forEach((probe) => { probe.onloadedmetadata = null; probe.onerror = null; probe.removeAttribute('src'); probe.load(); });
    };
  }, [encodedTracks]);

  useEffect(() => {
    const coordinate = (event) => {
      const player = audio.current;
      if (!player) return;
      if (event.target === player) {
        document.querySelectorAll('audio').forEach((other) => { if (other !== player) other.pause(); });
      } else {
        resume.current = false;
        player.pause();
      }
    };
    document.addEventListener('play', coordinate, true);
    return () => document.removeEventListener('play', coordinate, true);
  }, []);

  useEffect(() => {
    if (!audio.current || !activeUrl) return undefined;
    return switchComparisonSource(audio.current, activeUrl, position.current, () => resume.current,
      () => currentBounds.current, (err) => setError(err.message));
  }, [activeUrl]);

  const choose = (track) => {
    if (track.url === active.url) return;
    if (audio.current?.readyState >= 1) position.current = audio.current.currentTime;
    resume.current = audio.current ? !audio.current.paused || resume.current : false;
    setSelected(track.id); setError(null);
  };
  const seek = (value) => {
    const next = comparisonPosition(Number(value), bounds);
    position.current = next; setTime(next);
    if (audio.current?.readyState >= 1) audio.current.currentTime = next;
  };
  const toggle = () => {
    const player = audio.current;
    if (!player || !currentBounds.current.valid) return;
    if (!player.paused) { resume.current = false; player.pause(); return; }
    player.currentTime = comparisonPosition(player.currentTime, bounds);
    resume.current = true; player.play().catch((err) => setError(err.message));
  };
  const tick = () => {
    const player = audio.current;
    const limits = currentBounds.current;
    if (!player || player.readyState < 1 || !limits?.valid) return;
    if (player.currentTime < limits.start || player.currentTime >= limits.end) {
      player.pause(); resume.current = false; player.currentTime = limits.start;
    }
    position.current = player.currentTime; setTime(player.currentTime);
  };
  const changeRange = (name, value) => {
    audio.current?.pause(); resume.current = false;
    setCustomRange({ signature, start: range?.start ?? 0, end: range?.end ?? bounds.duration, [name]: value });
  };

  if (!active) return null;
  return <div className="flex flex-col gap-2 border-t border-[var(--line)] pt-3" data-audio-comparator>
    <span className="label">COMPARAR ORIGINAL Y VARIANTES · MISMO TRAMO</span>
    <div role="group" aria-label="Audio de la comparación" className="flex gap-2 flex-wrap">
      {tracks.map((track) => <button key={track.id} type="button" aria-pressed={track.id === active.id} onClick={() => choose(track)}
        className={`btn h-8 px-3 ${track.id === active.id ? 'btn-signal' : 'btn-ghost'}`}>{track.label}</button>)}
    </div>
    <audio ref={audio} preload="metadata" onTimeUpdate={tick} onPlay={() => { resume.current = true; setPlaying(true); }} onPause={() => setPlaying(false)}
      onEnded={() => { resume.current = false; setPlaying(false); }} onError={() => setError(`No se puede reproducir ${active.label}`)} aria-label="Reproductor de comparación" />
    <div className="flex items-center gap-3 flex-wrap">
      <button type="button" disabled={!ready || !bounds.valid} onClick={toggle} className="btn btn-ghost h-8 px-3" aria-label={playing ? 'Pausar comparación' : 'Reproducir comparación'}>{playing ? 'PAUSAR' : 'ESCUCHAR'}</button>
      <input type="range" aria-label="Posición compartida A/B" disabled={!ready || !bounds.valid} min={bounds.start} max={bounds.end ?? bounds.start} step={Number(nudgeStep) > 0 ? nudgeStep : undefined} value={comparisonPosition(time, bounds)} onKeyDown={(event) => {
        const direction = arrowDirection(event.key);
        const next = direction ? nudgePosition(audio.current?.currentTime ?? time, bounds, direction, nudgeStep) : null;
        if (next == null) return;
        event.preventDefault();
        seek(next);
      }} onChange={(event) => seek(event.target.value)} className="flex-1 min-w-28" />
      <span className="mono text-[10px]">{comparisonPosition(time, bounds).toFixed(1)} s</span>
    </div>
    <div className="flex gap-3 flex-wrap">
      <label className="label">DESDE <input className={field} aria-label="Inicio de comparación" type="number" step="any" min="0" max={bounds.duration ?? undefined} value={range?.start ?? 0} onChange={(event) => changeRange('start', event.target.value)} /> s</label>
      <label className="label">HASTA <input className={field} aria-label="Final de comparación" type="number" step="any" min="0" max={bounds.duration ?? undefined} value={range?.end ?? bounds.duration ?? ''} onChange={(event) => changeRange('end', event.target.value)} /> s</label>
    </div>
    {!ready && <p role="status" className="mono text-[10px] text-[var(--faint)]">Leyendo duración real de los audios…</p>}
    {ready && !bounds.valid && <p role="alert" className="mono text-[10px] st-err">Elige un intervalo con final posterior al inicio dentro de todos los audios.</p>}
    <p className="mono text-[10px] text-[var(--faint)]">Al cambiar de audio se conserva la posición y la reproducción. El intervalo común llega hasta el audio más corto.{ready && bounds.valid ? ` Tramo efectivo: ${bounds.start.toFixed(1)}–${bounds.end.toFixed(1)} s.` : ''}</p>
    {error && <p role="alert" className="mono text-[10px] st-err">{error}</p>}
  </div>;
}
