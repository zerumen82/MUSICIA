/** Absolute source time is shared across A/B; every track uses the same interval. */
export function comparisonBounds(interval, durations) {
  const known = durations.filter((duration) => Number.isFinite(duration) && duration > 0);
  const duration = known.length ? Math.min(...known) : null;
  const requestedStart = Number(interval?.start ?? 0);
  const requestedEnd = interval?.end == null || interval.end === '' ? duration : Number(interval.end);
  const start = Number.isFinite(requestedStart) ? Math.max(0, requestedStart) : 0;
  const end = Number.isFinite(requestedEnd) ? (duration == null ? requestedEnd : Math.min(duration, requestedEnd)) : duration;
  return { start, end, duration, valid: end != null && end > start };
}

export function comparisonPosition(time, bounds) {
  return Number.isFinite(time) && time >= bounds.start && time < bounds.end ? time : bounds.start;
}

/** Changes the source of one player; metadata must be ready before seek/play. */
export function switchComparisonSource(player, url, position, playing, getBounds, onError) {
  let active = true;
  player.pause();
  const ready = () => {
    const bounds = getBounds();
    if (!active || !bounds.valid) return;
    player.currentTime = comparisonPosition(position, bounds);
    if (typeof playing === 'function' ? playing() : playing) player.play().catch((error) => { if (active) onError(error); });
  };
  player.addEventListener('loadedmetadata', ready, { once: true });
  player.src = url;
  player.load();
  return () => { active = false; player.removeEventListener('loadedmetadata', ready); };
}
