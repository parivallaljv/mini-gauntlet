import type { Finding, ScanDetail, ScanSummary } from '../types';

/** A fake fetch Response carrying a JSON body. */
export function jsonResponse(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  } as Response;
}

export const completedScan: ScanSummary = {
  id: 1,
  status: 'COMPLETED',
  started_at: '2026-11-19T10:00:00.000+00:00',
  finished_at: '2026-11-19T10:00:03.020+00:00',
  account_ids: ['123456789012'],
  score: 60,
  counts: { PASS: 27, FAIL: 18, CANNOT_SCAN: 4 },
  error: null,
};

export const scanDetail: ScanDetail = {
  ...completedScan,
  fail_by_severity: { CRITICAL: 7, HIGH: 8, MEDIUM: 2, LOW: 1 },
  accounts: [
    {
      account_id: '123456789012',
      provider: 'aws',
      score: 58.3,
      counts: { PASS: 14, FAIL: 10, CANNOT_SCAN: 0 },
    },
    {
      account_id: 'example-corp-gcp',
      provider: 'gcp',
      score: null,
      counts: { PASS: 0, FAIL: 0, CANNOT_SCAN: 2 },
    },
  ],
};

export const XSS_DETAILS =
  "Rule allows tcp port 3389 from 0.0.0.0/0, exposing RDP (3389). Rule description: <img src=x onerror=alert('untrusted-input')> temporary rule for vendor support";

export const rdpFinding: Finding = {
  id: 10,
  scan_id: 1,
  check_id: 'GCP-VPC-01',
  title: "Firewall rule doesn't expose SSH or RDP to the internet",
  provider: 'gcp',
  account_id: 'example-corp-gcp',
  region: 'global',
  resource_id: 'allow-rdp-anywhere',
  status: 'FAIL',
  severity: 'CRITICAL',
  details: XSS_DETAILS,
};
