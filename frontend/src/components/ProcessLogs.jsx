import React, { useEffect, useState } from 'react';
import { Clipboard } from 'lucide-react';
import { api, actionError, JOB_POLL_INTERVAL_MS } from '../api';
import { currentProcessLogStreams } from '../process_log_view';

const LABELS = {
  engine_stdout: 'Salida del motor',
  engine_stderr: 'Error del motor',
  api_stderr: 'Error de la API',
};

/** Texto tal cual de los ficheros. La frase corta del progreso no se sustituye. */
export default function ProcessLogs({ open, onClose }) {
  const [streams, setStreams] = useState([]);
  const [error, setError] = useState('');
  const [copied, setCopied] = useState(new Set());

  useEffect(() => {
    if (!open) return undefined;
    let active = true;
    const load = async () => {
      try {
        const data = await api.processLogs();
        if (!active) return;
        setStreams(currentProcessLogStreams(data.streams ?? []));
        setError('');
      } catch (failure) {
        if (active) setError(actionError(failure.message) ?? '');
      }
    };
    void load();
    const timer = setInterval(() => { void load(); }, JOB_POLL_INTERVAL_MS);
    return () => { active = false; clearInterval(timer); };
  }, [open]);

  useEffect(() => {
    if (!open) return undefined;
    const onKey = (event) => {
      if (event.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  const copiar = async (id, texto) => {
    try {
      await navigator.clipboard.writeText(texto);
      setCopied((prev) => new Set([...prev, id]));
      setTimeout(() => setCopied((prev) => {
        const siguiente = new Set(prev);
        siguiente.delete(id);
        return siguiente;
      }), 1500);
    } catch {
      /* El navegador puede bloquear el portapapeles sin interacción del usuario. */
    }
  };

  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 bg-black/80 flex items-center justify-center p-6" role="presentation" onClick={onClose}>
      <div role="dialog" aria-modal="true" aria-label="Salida y error del proceso" data-process-logs
        className="w-full max-w-4xl max-h-[85vh] overflow-y-auto bg-[var(--surface)] border border-[var(--line)] p-5 flex flex-col gap-4"
        onClick={(event) => event.stopPropagation()}>
        <div className="flex items-center justify-between gap-3">
          <p className="text-[13px] text-[var(--text)]">Salida y error de la ejecución actual.</p>
          <button type="button" onClick={onClose} className="btn btn-ghost h-8 px-3">CERRAR</button>
        </div>
        {error && <p role="alert" className="mono text-[11px] st-err">{error}</p>}
        {streams.map((stream) => (
          <section key={stream.id} className="flex flex-col gap-1">
            <div className="flex items-center justify-between gap-2">
              <span className="label">{LABELS[stream.id] || stream.id}</span>
              {stream.present && stream.text && (
                <button type="button" onClick={() => copiar(stream.id, stream.text)}
                  className="btn btn-ghost h-6 px-2 text-[10px]">
                  {copied.has(stream.id) ? 'COPIADO' : 'COPIAR'}
                </button>
              )}
            </div>
            <pre className="mono text-[11px] whitespace-pre-wrap break-words max-h-56 overflow-y-auto border border-[var(--line)] p-3 text-[var(--text)]">
              {stream.present ? (stream.text || 'Este fichero existe y todavía no tiene líneas.') : 'Este fichero todavía no existe.'}
            </pre>
          </section>
        ))}
      </div>
    </div>
  );
}
