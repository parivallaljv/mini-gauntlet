// Shapes returned by the API (see backend/app/schemas.py).

export type ScanStatus = 'RUNNING' | 'COMPLETED' | 'FAILED';
export type FindingStatus = 'PASS' | 'FAIL' | 'CANNOT_SCAN';
export type Severity = 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW';

export const FINDING_STATUSES: FindingStatus[] = ['FAIL', 'CANNOT_SCAN', 'PASS'];
export const SEVERITIES: Severity[] = ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW'];
export const PROVIDERS = ['aws', 'azure', 'gcp'];

export type StatusCounts = Record<FindingStatus, number>;
export type SeverityCounts = Record<Severity, number>;

export interface ScanSummary {
  id: number;
  status: ScanStatus;
  started_at: string;
  finished_at: string | null;
  account_ids: string[] | null;
  score: number | null;
  counts: StatusCounts;
  error: string | null;
}

export interface AccountScore {
  account_id: string;
  provider: string | null;
  score: number | null;
  counts: StatusCounts;
}

export interface ScanDetail extends ScanSummary {
  fail_by_severity: SeverityCounts;
  accounts: AccountScore[];
}

export interface Finding {
  id: number;
  scan_id: number;
  check_id: string;
  title: string;
  provider: string;
  account_id: string;
  region: string | null;
  resource_id: string | null;
  status: FindingStatus;
  severity: Severity;
  details: string;
}

export interface FindingsPage {
  items: Finding[];
  total: number;
  page: number;
  page_size: number;
}

export interface FindingFilters {
  status: string;
  severity: string;
  provider: string;
  account_id: string;
}
