/** A score, or "N/A" when there was nothing to score. */
export function formatScore(score: number | null): string {
  return score === null ? 'N/A' : score.toFixed(1);
}

/** An ISO timestamp shown in the viewer's own time zone and locale. */
export function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString();
}

/** Time between two ISO timestamps, e.g. "3.0 s" or "2 min 05 s"; "-" while unfinished. */
export function formatDuration(startIso: string, endIso: string | null): string {
  if (!endIso) return '-';
  const seconds = (Date.parse(endIso) - Date.parse(startIso)) / 1000;
  if (Number.isNaN(seconds) || seconds < 0) return '-';
  if (seconds < 60) return `${seconds.toFixed(1)} s`;
  const minutes = Math.floor(seconds / 60);
  const rest = Math.round(seconds % 60);
  return `${minutes} min ${String(rest).padStart(2, '0')} s`;
}
