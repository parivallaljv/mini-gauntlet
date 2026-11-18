import type { Finding } from '../types';
import { Badge } from './Badge';

/**
 * Every value here comes from the customer's cloud and is untrusted. JSX text is
 * always escaped by React, so a string like "<img onerror=...>" shows as text.
 */
export function FindingsTable({ findings }: { findings: Finding[] }) {
  if (findings.length === 0) {
    return <p className="empty">No findings match these filters.</p>;
  }
  return (
    <table className="findings">
      <thead>
        <tr>
          <th>Status</th>
          <th>Severity</th>
          <th>Check</th>
          <th>Provider</th>
          <th>Account</th>
          <th>Region</th>
          <th>Resource</th>
          <th>Details</th>
        </tr>
      </thead>
      <tbody>
        {findings.map((finding) => (
          <tr key={finding.id}>
            <td>
              <Badge value={finding.status} />
            </td>
            <td>
              <Badge value={finding.severity} />
            </td>
            <td>
              <div className="mono">{finding.check_id}</div>
              <div className="muted small">{finding.title}</div>
            </td>
            <td>{finding.provider}</td>
            <td className="mono small">{finding.account_id}</td>
            <td>{finding.region ?? '-'}</td>
            <td className="mono small">{finding.resource_id ?? '(whole account)'}</td>
            <td className="details">{finding.details}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
