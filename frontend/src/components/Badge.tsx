// Colored label for a scan status, finding status or severity.
// The class name comes from a fixed list, never from snapshot text.
const KNOWN = new Set([
  'RUNNING',
  'COMPLETED',
  'FAILED',
  'PASS',
  'FAIL',
  'CANNOT_SCAN',
  'CRITICAL',
  'HIGH',
  'MEDIUM',
  'LOW',
]);

export function Badge({ value }: { value: string }) {
  const variant = KNOWN.has(value) ? value.toLowerCase() : 'unknown';
  return <span className={`badge badge-${variant}`}>{value.replace('_', ' ')}</span>;
}
