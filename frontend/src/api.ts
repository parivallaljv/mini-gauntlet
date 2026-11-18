import type { FindingFilters, FindingsPage, ScanDetail, ScanSummary } from './types';

// Relative URL: the Vite dev server (and nginx in Docker) forwards /api to FastAPI.
const BASE = '/api';

export class ApiError extends Error {
  status: number | null;

  constructor(message: string, status: number | null = null) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(BASE + path, init);
  } catch {
    // fetch only rejects when there is no HTTP response at all.
    throw new ApiError('Cannot reach the API. Is the backend running?');
  }
  if (!response.ok) {
    let message = `Request failed with status ${response.status}`;
    try {
      const body = await response.json();
      if (typeof body.detail === 'string') message = body.detail;
    } catch {
      // Not JSON; keep the generic message.
    }
    throw new ApiError(message, response.status);
  }
  return (await response.json()) as T;
}

export function listScans(): Promise<ScanSummary[]> {
  return request('/scans');
}

export function getScan(id: number): Promise<ScanDetail> {
  return request(`/scans/${id}`);
}

export function startScan(): Promise<ScanSummary> {
  return request('/scans', { method: 'POST' });
}

export function listFindings(
  scanId: number,
  filters: FindingFilters,
  page: number,
  pageSize: number,
): Promise<FindingsPage> {
  const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
  for (const [name, value] of Object.entries(filters)) {
    if (value) params.set(name, value); // empty string means "any"
  }
  return request(`/scans/${scanId}/findings?${params}`);
}

export function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : 'Something went wrong';
}
