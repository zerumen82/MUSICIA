const RUNNING = new Set(['queued', 'running']);

export function runningJob(jobs) {
  return (jobs ?? []).find((job) => RUNNING.has(job?.status)) ?? null;
}

export function latestJob(jobs) {
  let best = null;
  let stamp = '';
  for (const job of jobs ?? []) {
    const created = String(job?.created_at ?? '');
    if (best == null || created > stamp) {
      best = job;
      stamp = created;
    }
  }
  return best;
}

export function headerWatchText(job, percent) {
  if (!job) return '';
  const name = job.output_name || String(job.prompt ?? '').slice(0, 40) || 'Trabajo';
  if (RUNNING.has(job.status)) return percent != null ? `${name} · ${percent}%` : name;
  if (job.status === 'failed' || job.status === 'cancelled') {
    return `${name} · ${job.error || job.phase || 'No se completó'}`;
  }
  return `${name} · ${job.phase || 'Lista'}`;
}
