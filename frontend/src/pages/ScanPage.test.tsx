import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { jsonResponse, rdpFinding, scanDetail } from '../test/fixtures';
import { ScanPage } from './ScanPage';

function mockApi() {
  const fetchMock = vi.fn((url: string) => {
    if (url.startsWith('/api/scans/1/findings')) {
      return Promise.resolve(
        jsonResponse({ items: [rdpFinding], total: 30, page: 1, page_size: 25 }),
      );
    }
    if (url === '/api/scans/1') return Promise.resolve(jsonResponse(scanDetail));
    return Promise.resolve(jsonResponse({ detail: 'Scan 99 not found' }, 404));
  });
  vi.stubGlobal('fetch', fetchMock);
  return fetchMock;
}

describe('ScanPage', () => {
  it('shows the score, counts, per-account scores and findings', async () => {
    mockApi();
    render(<ScanPage scanId={1} />);

    expect(await screen.findByText('60.0')).toBeInTheDocument();
    expect(screen.getByText('58.3')).toBeInTheDocument();
    expect(screen.getByText('N/A')).toBeInTheDocument(); // account with nothing to score
    expect(await screen.findByText('allow-rdp-anywhere')).toBeInTheDocument();
    expect(screen.getByText('Page 1 of 2 (30 findings)')).toBeInTheDocument();
  });

  it('sends the chosen filters to the API and goes back to page 1', async () => {
    const fetchMock = mockApi();
    render(<ScanPage scanId={1} />);
    await screen.findByText('allow-rdp-anywhere');

    await userEvent.selectOptions(screen.getByLabelText('Status'), 'FAIL');
    await userEvent.selectOptions(screen.getByLabelText('Provider'), 'gcp');

    await waitFor(() => {
      const urls = fetchMock.mock.calls.map(([url]) => url);
      expect(urls).toContain('/api/scans/1/findings?page=1&page_size=25&status=FAIL&provider=gcp');
    });
  });

  it('shows "not found" for an unknown scan', async () => {
    mockApi();
    render(<ScanPage scanId={99} />);
    expect(await screen.findByRole('alert')).toHaveTextContent('Scan #99 was not found.');
  });
});
