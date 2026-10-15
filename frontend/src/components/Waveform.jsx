import React, { useCallback, useEffect, useRef, useState } from 'react';
import { api } from '../api';
import { arrowDirection, nudgeInterval } from '../timeline_nudge';

/**
 * Forma de onda interactiva: pinta los picos reales (GET /audio/peaks)
 * y permite seleccionar el tramo útil arrastrando (trim inicio/fin).
 */
export default function Waveform({ fileName, onSelection, sourceKind = null, selection = null, disabled = false, nudgeStep = null, scales = true }) {
  const [peaks, setPeaks] = useState(null);
  const [duration, setDuration] = useState(0);
  const [error, setError] = useState(null);
  const [localSelection, setLocalSelection] = useState({ start: 0, end: null });
  const canvasRef = useRef(null);
  const dragRef = useRef(null); // 'start' | 'end' | 'move'
  const chosen = selection ?? localSelection;
  const selStart = duration ? Math.min(1, Math.max(0, Number(chosen.start) / duration || 0)) : 0;
  const selEnd = duration ? Math.min(1, Math.max(selStart, Number(chosen.end ?? duration) / duration)) : 1;

  useEffect(() => {
    let active = true;
    api.audioPeaks(fileName, undefined, sourceKind)
      .then((d) => {
        if (!active) return;
        setPeaks(d.peaks);
        setDuration(d.duration_seconds);
        setError(null);
      })
      .catch((e) => {
        if (active) setError(e.message);
      });
    return () => { active = false; };
  }, [fileName, sourceKind]);

  const paint = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas || !peaks) return;
    const ctx = canvas.getContext('2d');
    const scale = window.devicePixelRatio || 1;
    const W = canvas.width = canvas.offsetWidth * scale;
    const H = canvas.height = canvas.offsetHeight * scale;
    ctx.clearRect(0, 0, W, H);

    const startPx = selStart * W;
    const endPx = selEnd * W;

    // Fondo del tramo descartado
    const theme = getComputedStyle(canvas);
    ctx.fillStyle = theme.getPropertyValue('--bg').trim() || theme.backgroundColor;
    ctx.fillRect(0, 0, startPx, H);
    ctx.fillRect(endPx, 0, W - endPx, H);

    // Onda
    const mid = H / 2;
    const n = peaks.length;
    for (let x = 0; x < W; x++) {
      const p = peaks[Math.floor((x / W) * n)] ?? 0;
      const h = Math.max(2, p * (H * 0.9));
      const inSel = x >= startPx && x <= endPx;
      ctx.fillStyle = theme.getPropertyValue(inSel ? '--acc' : '--line').trim();
      ctx.fillRect(x, mid - h / 2, 1, h);
    }

    // Marcadores
    ctx.fillStyle = theme.getPropertyValue('--muted').trim();
    ctx.fillRect(startPx - 1, 0, 2, H);
    ctx.fillRect(endPx - 1, 0, 2, H);
  }, [peaks, selStart, selEnd]);

  useEffect(() => {
    paint();
    const observer = new ResizeObserver(paint);
    if (canvasRef.current) observer.observe(canvasRef.current);
    return () => observer.disconnect();
  }, [paint]);

  const change = (name, value) => {
    if (disabled) return;
    const next = { start: selStart * duration, end: selEnd * duration, [name]: Number(value) };
    if (!selection) setLocalSelection(next);
    onSelection?.({ trim_start_s: next.start, trim_end_s: next.end >= duration ? null : next.end });
  };

  const xToRatio = (clientX) => {
    const rect = canvasRef.current.getBoundingClientRect();
    return Math.min(1, Math.max(0, (clientX - rect.left) / rect.width));
  };

  const onDown = (e) => {
    if (disabled) return;
    const r = xToRatio(e.clientX);
    // ¿cerca de un marcador? -> arrastrar ese; si no, arrastrar el más cercano
    dragRef.current = Math.abs(r - selStart) <= Math.abs(r - selEnd) ? 'start' : 'end';
    canvasRef.current.setPointerCapture(e.pointerId);
    onMove(e);
  };
  const onMove = (e) => {
    if (!dragRef.current) return;
    const r = xToRatio(e.clientX);
    if (dragRef.current === 'start') change('start', Math.min(r, selEnd) * duration);
    else change('end', Math.max(r, selStart) * duration);
  };
  const onUp = () => { dragRef.current = null; };
  const onKey = (edge) => (event) => {
    const direction = arrowDirection(event.key);
    if (!direction || disabled) return;
    event.preventDefault();
    const next = nudgeInterval({
      start: selStart * duration,
      end: chosen.end,
      duration,
      edge,
      direction,
      step: nudgeStep,
    });
    if (!next) return;
    if (!selection) setLocalSelection({ start: next.start, end: next.end });
    onSelection?.({ trim_start_s: next.start, trim_end_s: next.end });
  };

  if (error) return <p className="mono text-[10px] st-err">{error}</p>;
  if (!peaks) return <p className="mono text-[10px] text-[var(--faint)] animate-pulse">CARGANDO ONDA…</p>;

  return (
    <div className="flex flex-col gap-1.5">
      <canvas
        ref={canvasRef}
        className="w-full h-[72px] cursor-ew-resize select-none border border-[var(--line)]"
        aria-hidden="true"
        onPointerDown={onDown}
        onPointerMove={onMove}
        onPointerUp={onUp}
        onPointerCancel={onUp}
        style={{ touchAction: 'none' }}
      />
      {scales && <>
        <label className="label">INICIO ONDA
          <input aria-label="Inicio de la selección en la onda" type="range" min="0" max={selEnd * duration} step={Number(nudgeStep) > 0 ? nudgeStep : undefined} value={selStart * duration} disabled={disabled} onKeyDown={onKey('start')} onChange={(event) => change('start', event.target.value)} className="block w-full min-w-0" />
        </label>
        <label className="label">FIN ONDA
          <input aria-label="Final de la selección en la onda" type="range" min={selStart * duration} max={duration} step={Number(nudgeStep) > 0 ? nudgeStep : undefined} value={selEnd * duration} disabled={disabled} onKeyDown={onKey('end')} onChange={(event) => change('end', event.target.value)} className="block w-full min-w-0" />
        </label>
      </>}
    </div>
  );
}
