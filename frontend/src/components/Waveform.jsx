import React, { useCallback, useEffect, useRef, useState } from 'react';
import { api } from '../api';

/**
 * Forma de onda interactiva: pinta los picos reales (GET /audio/peaks)
 * y permite seleccionar el tramo útil arrastrando (trim inicio/fin).
 */
export default function Waveform({ fileName, onSelection, sourceKind = null }) {
  const [peaks, setPeaks] = useState(null);
  const [duration, setDuration] = useState(0);
  const [error, setError] = useState(null);
  const [selStart, setSelStart] = useState(0); // 0..1
  const [selEnd, setSelEnd] = useState(1); // 0..1
  const canvasRef = useRef(null);
  const dragRef = useRef(null); // 'start' | 'end' | 'move'

  useEffect(() => {
    let active = true;
    api.audioPeaks(fileName, 600, sourceKind)
      .then((d) => {
        if (!active) return;
        setPeaks(d.peaks);
        setDuration(d.duration_seconds);
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
    const W = canvas.width = canvas.offsetWidth * 2;   // retina
    const H = canvas.height = canvas.offsetHeight * 2;
    ctx.clearRect(0, 0, W, H);

    const startPx = selStart * W;
    const endPx = selEnd * W;

    // Fondo del tramo descartado
    ctx.fillStyle = '#1d1d22';
    ctx.fillRect(0, 0, startPx, H);
    ctx.fillRect(endPx, 0, W - endPx, H);

    // Onda
    const mid = H / 2;
    const n = peaks.length;
    for (let x = 0; x < W; x++) {
      const p = peaks[Math.floor((x / W) * n)] ?? 0;
      const h = Math.max(2, p * (H * 0.9));
      const inSel = x >= startPx && x <= endPx;
      ctx.fillStyle = inSel ? '#b8ff29' : '#3a3a44';
      ctx.fillRect(x, mid - h / 2, 1, h);
    }

    // Marcadores
    ctx.fillStyle = '#e8e8ec';
    ctx.fillRect(startPx - 1, 0, 2, H);
    ctx.fillRect(endPx - 1, 0, 2, H);
  }, [peaks, selStart, selEnd]);

  useEffect(() => { paint(); }, [paint]);

  useEffect(() => {
    if (duration && onSelection) {
      onSelection({
        trim_start_s: +(selStart * duration).toFixed(2),
        trim_end_s: selEnd >= 0.999 ? null : +(selEnd * duration).toFixed(2),
      });
    }
  }, [selStart, selEnd, duration, onSelection]);

  const xToRatio = (clientX) => {
    const rect = canvasRef.current.getBoundingClientRect();
    return Math.min(1, Math.max(0, (clientX - rect.left) / rect.width));
  };

  const onDown = (e) => {
    const r = xToRatio(e.clientX);
    // ¿cerca de un marcador? -> arrastrar ese; si no, arrastrar el más cercano
    dragRef.current = Math.abs(r - selStart) <= Math.abs(r - selEnd) ? 'start' : 'end';
  };
  const onMove = (e) => {
    if (!dragRef.current) return;
    const r = xToRatio(e.clientX);
    if (dragRef.current === 'start') setSelStart(Math.min(r, selEnd - 0.01));
    else setSelEnd(Math.max(r, selStart + 0.01));
  };
  const onUp = () => { dragRef.current = null; };

  if (error) return <p className="mono text-[10px] st-err">{error}</p>;
  if (!peaks) return <p className="mono text-[10px] text-[var(--faint)] animate-pulse">CARGANDO ONDA…</p>;

  return (
    <div className="flex flex-col gap-1.5">
      <canvas
        ref={canvasRef}
        className="w-full h-[72px] cursor-ew-resize select-none border border-[var(--line)]"
        onMouseDown={onDown}
        onMouseMove={onMove}
        onMouseUp={onUp}
        onMouseLeave={onUp}
      />
      <div className="flex items-center justify-between mono text-[9.5px] text-[var(--faint)]">
        <span>INICIO {duration ? (selStart * duration).toFixed(1) : '—'}s</span>
        <span>arrastra los marcadores para recortar</span>
        <span>FIN {duration ? (selEnd * duration).toFixed(1) : '—'}s</span>
      </div>
    </div>
  );
}
