import { useCallback, useEffect, useState } from 'react';
import { errorMessage, listScans, startScan } from '../api';
import { Badge } from '../components/Badge';
import { ErrorMessage } from '../components/ErrorMessage';
import { formatDateTime, formatDuration, formatScore } from '../format';
import type { ScanSummary } from '../types';
import { usePolling } from '../usePolling';
import { scanHref } from '../useHashRoute';

export function ScansPage() {
  const [scans, setScans] = useState<ScanSummary[] | null>(null); // null = not loaded yet
  const [error, setError] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);

  const load = useCallback(async () => {
    try {
      setScans(await listScans());
      setError(null);
    } catch (e) {
      setError(errorMessage(e));
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  // Keep refreshing while any scan is still running.
  const anyRunning = scans?.some((scan) => scan.status === 'RUNNING') ?? false;
  usePolling(load, anyRunning);

  async function handleRunScan() {
    setStarting(true);
    try {
      await startScan();
      await load();
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setStarting(false);
    }
  }

  return (
    <section>
      <div className="page-header">
        <h1>Scans</h1>
        <button type="button" onClick={handleRunScan} disabled={starting}>
          {starting ? 'Starting...' : 'Run scan'}
        </button>
      </div>

      {error && <ErrorMessage message={error} onRetry={load} />}
      {scans === null && !error && <p className="muted">Loading scans...</p>}
      {scans?.length === 0 && <p className="empty">No scans yet. Click "Run scan" to start one.</p>}

      {scans && scans.length > 0 && (
        <table>
          <thead>
            <tr>
              <th>Scan</th>
              <th>Status</th>
              <th>Started</th>
              <th>Duration</th>
              <th className="num">Score</th>
              <th className="num">PASS</th>
              <th className="num">FAIL</th>
              <th className="num">CANNOT SCAN</th>
            </tr>
          </thead>
          <tbody>
            {scans.map((scan) => (
              <tr key={scan.id}>
                <td>
                  <a href={scanHref(scan.id)}>Scan #{scan.id}</a>
                </td>
                <td>
                  <Badge value={scan.status} />
                  {scan.error && <div className="muted small">{scan.error}</div>}
                </td>
                <td>{formatDateTime(scan.started_at)}</td>
                <td>{formatDuration(scan.started_at, scan.finished_at)}</td>
                <td className="num strong">{formatScore(scan.score)}</td>
                <td className="num">{scan.counts.PASS}</td>
                <td className="num">{scan.counts.FAIL}</td>
                <td className="num">{scan.counts.CANNOT_SCAN}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
