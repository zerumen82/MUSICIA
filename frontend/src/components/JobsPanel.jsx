import React, { useEffect, useState } from 'react';
import { Loader2, AlertTriangle, Play, Pause, CheckCircle2, Layers } from 'lucide-react';
import { api, JOB_POLL_INTERVAL_MS } from '../api';

const fmt = (s) => `${Math.floor(s / 60)}:${String(Math.round(s % 60)).padStart(2, '0')}`;

const STATUS_UI = {
  queued: { label: 'EN COLA', cls: 'text-[var(--warn)]' },
  running: { label: 'CREANDO', cls: 'text-[var(--acc)]' },
  succeeded: { label: 'LISTA', cls: 'st-ok' },
  failed: { label: 'ERROR', cls: 'st-err' },
};

/**
 * Cola de trabajos de la sesión (backend /music/jobs) + comparador A/B:
 * marca hasta 2 pistas terminadas y las reproduce juntas para comparar.
 */
export default function JobsPanel() {
  const [jobs, setJobs] = useState([]);
  const [playing, setPlaying] = useState(null); // job_id
  const [abMarks, setAbMarks] = useState([]); // hasta 2 job_ids marcados

  useEffect(() => {
    let cancelled = false;
    const tick = async () => {
      try {
        const data = await api.musicJobs();
        if (!cancelled) setJobs(data.items ?? []);
      } catch {
        /* silencioso: el panel es secundario */
      }
    };
    void tick();
    const t = setInterval(tick, JOB_POLL_INTERVAL_MS);
    return () => { cancelled = true; clearInterval(t); };
  }, []);

  const toggleMark = (jobId) => {
    setAbMarks((cur) => {
      if (cur.includes(jobId)) return cur.filter((x) => x !== jobId);
      if (cur.length >= 2) return [cur[1], jobId];
      return [...cur, jobId];
    });
  };

  const active = jobs.filter((j) => j.status === 'queued' || j.status === 'running');
  const done = jobs.filter((j) => j.status === 'succeeded').slice(0, 8);

  if (jobs.length === 0) return null;

  return (
    <div className="flex flex-col gap-2 border-t border-[var(--line)] pt-4">
      <div className="flex items-center gap-3">
        <Layers size={13} className="text-[var(--muted)]" />
        <span className="label">COLA DE TRABAJOS · {active.length} activos</span>
        {abMarks.length === 2 && (
          <span className="mono text-[9px] text-[var(--acc)] tracking-[0.1em]">A/B LISTO PARA COMPARAR</span>
        )}
      </div>

      {active.map((job) => (
        <div key={job.job_id} className="flex items-center gap-3 py-1.5">
          <Loader2 size={11} className="text-[var(--acc)] animate-spin shrink-0" />
          <span className={`mono text-[10px] tracking-[0.1em] shrink-0 ${STATUS_UI[job.status]?.cls}`}>
            {STATUS_UI[job.status]?.label}
          </span>
          <span className="num text-[13px] shrink-0">
            {Math.floor((job.elapsed_seconds ?? 0) / 60)}:{String(Math.round((job.elapsed_seconds ?? 0) % 60)).padStart(2, '0')}
          </span>
          <span className="text-[12px] text-zinc-300 truncate flex-1 min-w-0">{job.phase || job.prompt}</span>
        </div>
      ))}

      {done.length > 0 && (
        <div className="flex flex-col">
          {done.map((job) => {
            const isPlaying = playing === job.job_id;
            const markIdx = abMarks.indexOf(job.job_id);
            return (
              <React.Fragment key={job.job_id}>
              <div className="flex items-center gap-3 py-1.5 border-b border-[var(--line)]">
                <button onClick={() => setPlaying(isPlaying ? null : job.job_id)}
                  className={`w-6 h-6 rounded-[3px] flex items-center justify-center shrink-0 border ${isPlaying ? 'bg-[var(--acc)] border-[var(--acc)]' : 'border-[var(--line-strong)]'}`}>
                  {isPlaying ? <Pause size={9} className="text-[#0c0f04]" fill="currentColor" />
                    : <Play size={9} className="text-[var(--muted)]" fill="currentColor" />}
                </button>
                <button onClick={() => toggleMark(job.job_id)} title="Marcar para comparar A/B (máx. 2)"
                  className={`mono text-[9px] w-5 h-5 shrink-0 border flex items-center justify-center transition-colors ${
                    markIdx >= 0 ? 'border-[var(--acc)] bg-[var(--acc-dim)] text-[var(--acc)]' : 'border-[var(--line)] text-[var(--faint)] hover:border-[var(--line-strong)]'
                  }`}>
                  {markIdx >= 0 ? String.fromCharCode(65 + markIdx) : '·'}
                </button>
                <span className="text-[11.5px] text-zinc-300 truncate flex-1 min-w-0">{job.prompt}</span>
                {job.duration_seconds && (
                  <span className="mono text-[9.5px] text-[var(--faint)] shrink-0">{fmt(job.duration_seconds)}</span>
                )}
                <a href={api.audioUrl(job.output_name)} download
                  className="mono text-[9px] text-[var(--faint)] hover:text-[var(--acc)] shrink-0">MP3</a>
              </div>
              {isPlaying && job.output_name && (
                <audio key={job.job_id} controls autoPlay src={api.audioUrl(job.output_name)}
                  className="player" onEnded={() => setPlaying(null)} />
              )}
              </React.Fragment>
            );
          })}
        </div>
      )}

      {abMarks.length > 0 && (
        <div className="flex flex-col gap-2 pt-1">
          {abMarks.map((jobId, i) => {
            const job = jobs.find((j) => j.job_id === jobId);
            if (!job?.output_name) return null;
            return (
              <div key={jobId} className="flex items-center gap-3">
                <span className="mono text-[10px] text-[var(--acc)] w-4">{String.fromCharCode(65 + i)}</span>
                <audio key={jobId} controls src={api.audioUrl(job.output_name)} className="player flex-1" />
              </div>
            );
          })}
        </div>
      )}

      {jobs.some((j) => j.status === 'failed') && (
        <div className="flex items-center gap-2">
          <AlertTriangle size={11} className="st-err" />
          <span className="mono text-[10px] st-err">
            {jobs.filter((j) => j.status === 'failed').length} trabajo(s) fallaron — revisa el prompt o reintenta
          </span>
        </div>
      )}
    </div>
  );
}
