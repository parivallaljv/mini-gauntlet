import { useCallback, useEffect, useState } from 'react';
import { ApiError, errorMessage, getScan, listFindings } from '../api';
import { Badge } from '../components/Badge';
import { ErrorMessage } from '../components/ErrorMessage';
import { FindingsTable } from '../components/FindingsTable';
import { Pagination } from '../components/Pagination';
import { formatDateTime, formatDuration, formatScore } from '../format';
import {
  FINDING_STATUSES,
  PROVIDERS,
  SEVERITIES,
  type FindingFilters,
  type FindingsPage,
  type ScanDetail,
} from '../types';
import { usePolling } from '../usePolling';

const PAGE_SIZE = 25;
const NO_FILTERS: FindingFilters = { status: '', severity: '', provider: '', account_id: '' };

export function ScanPage({ scanId }: { scanId: number }) {
  const [scan, setScan] = useState<ScanDetail | null>(null);
  const [scanError, setScanError] = useState<string | null>(null);
  const [filters, setFilters] = useState<FindingFilters>(NO_FILTERS);
  const [page, setPage] = useState(1);
  const [findings, setFindings] = useState<FindingsPage | null>(null);
  const [findingsError, setFindingsError] = useState<string | null>(null);
  const [retryCount, setRetryCount] = useState(0);

  const loadScan = useCallback(async () => {
    try {
      setScan(await getScan(scanId));
      setScanError(null);
    } catch (e) {
      const notFound = e instanceof ApiError && e.status === 404;
      setScanError(notFound ? `Scan #${scanId} was not found.` : errorMessage(e));
    }
  }, [scanId]);

  useEffect(() => {
    void loadScan();
  }, [loadScan]);
  usePolling(loadScan, scan?.status === 'RUNNING');

  // Load the findings page once the scan is done, and whenever filters or page change.
  const scanStatus = scan?.status;
  useEffect(() => {
    if (scanStatus !== 'COMPLETED') return;
    let ignore = false; // drop a response that arrives after the filters changed again
    listFindings(scanId, filters, page, PAGE_SIZE)
      .then((result) => {
        if (ignore) return;
        setFindings(result);
        setFindingsError(null);
      })
      .catch((e) => {
        if (!ignore) setFindingsError(errorMessage(e));
      });
    return () => {
      ignore = true;
    };
  }, [scanId, scanStatus, filters, page, retryCount]);

  function updateFilter(name: keyof FindingFilters, value: string) {
    setFilters((current) => ({ ...current, [name]: value }));
    setPage(1); // a new filter starts again at the first page
  }

  return (
    <section>
      <p>
        <a href="#/">&larr; All scans</a>
      </p>

      {scanError && <ErrorMessage message={scanError} onRetry={loadScan} />}
      {!scan && !scanError && <p className="muted">Loading scan...</p>}

      {scan && (
        <>
          <div className="page-header">
            <h1>
              Scan #{scan.id} <Badge value={scan.status} />
            </h1>
            <span className="muted">
              Started {formatDateTime(scan.started_at)} &middot; Duration{' '}
              {formatDuration(scan.started_at, scan.finished_at)}
            </span>
          </div>

          {scan.status === 'RUNNING' && (
            <p className="notice">Scan is running. This page updates automatically.</p>
          )}
          {scan.status === 'FAILED' && (
            <ErrorMessage message={`Scan failed: ${scan.error ?? 'unknown error'}`} />
          )}
          {scan.status === 'COMPLETED' && <Summary scan={scan} />}

          {scan.status === 'COMPLETED' && (
            <>
              <h2>Findings</h2>
              <div className="filters">
                <FilterSelect
                  label="Status"
                  value={filters.status}
                  options={FINDING_STATUSES}
                  onChange={(v) => updateFilter('status', v)}
                />
                <FilterSelect
                  label="Severity"
                  value={filters.severity}
                  options={SEVERITIES}
                  onChange={(v) => updateFilter('severity', v)}
                />
                <FilterSelect
                  label="Provider"
                  value={filters.provider}
                  options={PROVIDERS}
                  onChange={(v) => updateFilter('provider', v)}
                />
                <FilterSelect
                  label="Account"
                  value={filters.account_id}
                  options={scan.accounts.map((a) => a.account_id)}
                  onChange={(v) => updateFilter('account_id', v)}
                />
              </div>

              {findingsError && (
                <ErrorMessage message={findingsError} onRetry={() => setRetryCount((n) => n + 1)} />
              )}
              {!findings && !findingsError && <p className="muted">Loading findings...</p>}
              {findings && (
                <>
                  <FindingsTable findings={findings.items} />
                  <Pagination
                    page={findings.page}
                    pageSize={findings.page_size}
                    total={findings.total}
                    onChange={setPage}
                  />
                </>
              )}
            </>
          )}
        </>
      )}
    </section>
  );
}

function Summary({ scan }: { scan: ScanDetail }) {
  return (
    <>
      <div className="cards">
        <div className="card">
          <div className="card-label">Posture score</div>
          <div className="score">{formatScore(scan.score)}</div>
        </div>
        <div className="card">
          <div className="card-label">Findings by status</div>
          {FINDING_STATUSES.map((status) => (
            <div className="count-row" key={status}>
              <Badge value={status} />
              <span>{scan.counts[status]}</span>
            </div>
          ))}
        </div>
        <div className="card">
          <div className="card-label">FAIL by severity</div>
          {SEVERITIES.map((severity) => (
            <div className="count-row" key={severity}>
              <Badge value={severity} />
              <span>{scan.fail_by_severity[severity]}</span>
            </div>
          ))}
        </div>
      </div>

      <h2>Score per account</h2>
      <table>
        <thead>
          <tr>
            <th>Account</th>
            <th>Provider</th>
            <th className="num">Score</th>
            <th className="num">PASS</th>
            <th className="num">FAIL</th>
            <th className="num">CANNOT SCAN</th>
          </tr>
        </thead>
        <tbody>
          {scan.accounts.map((account) => (
            <tr key={account.account_id}>
              <td className="mono">{account.account_id}</td>
              <td>{account.provider ?? '-'}</td>
              <td className="num strong">{formatScore(account.score)}</td>
              <td className="num">{account.counts.PASS}</td>
              <td className="num">{account.counts.FAIL}</td>
              <td className="num">{account.counts.CANNOT_SCAN}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}

interface FilterSelectProps {
  label: string;
  value: string;
  options: string[];
  onChange: (value: string) => void;
}

function FilterSelect({ label, value, options, onChange }: FilterSelectProps) {
  return (
    <label>
      {label}
      <select value={value} onChange={(e) => onChange(e.target.value)}>
        <option value="">All</option>
        {options.map((option) => (
          <option key={option} value={option}>
            {option}
          </option>
        ))}
      </select>
    </label>
  );
}
