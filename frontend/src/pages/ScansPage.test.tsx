import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { completedScan, jsonResponse } from '../test/fixtures';
import { ScansPage } from './ScansPage';

describe('ScansPage', () => {
  it('lists scans with their score, and "N/A" when there is nothing to score', async () => {
    const failedScan = {
      ...completedScan,
      id: 2,
      status: 'FAILED',
      finished_at: '2026-11-19T10:00:00.500+00:00',
      score: null,
      counts: { PASS: 0, FAIL: 0, CANNOT_SCAN: 0 },
      error: 'FileNotFoundError: inventory.json',
    };
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse([failedScan, completedScan])));

    render(<ScansPage />);

    expect(await screen.findByText('Scan #1')).toBeInTheDocument();
    expect(screen.getByText('60.0')).toBeInTheDocument();
    expect(screen.getByText('N/A')).toBeInTheDocument();
    expect(screen.getByText('3.0 s')).toBeInTheDocument();
    expect(screen.getByText('0.5 s')).toBeInTheDocument();
    expect(screen.getByText('FileNotFoundError: inventory.json')).toBeInTheDocument();
  });

  it('shows an error with a retry button when the API is down', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')));

    render(<ScansPage />);

    expect(await screen.findByRole('alert')).toHaveTextContent('Cannot reach the API');
    expect(screen.getByRole('button', { name: 'Retry' })).toBeInTheDocument();
  });

  it('shows an empty state when there are no scans', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse([])));
    render(<ScansPage />);
    expect(await screen.findByText(/No scans yet/)).toBeInTheDocument();
  });

  it('starts a scan with POST /api/scans and shows it', async () => {
    const running = { ...completedScan, status: 'RUNNING', finished_at: null, score: null };
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse([])) // first load
      .mockResolvedValueOnce(jsonResponse(running, 202)) // POST
      .mockResolvedValue(jsonResponse([running])); // reloads
    vi.stubGlobal('fetch', fetchMock);

    render(<ScansPage />);
    await screen.findByText(/No scans yet/);
    await userEvent.click(screen.getByRole('button', { name: 'Run scan' }));

    expect(await screen.findByText('RUNNING')).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith('/api/scans', { method: 'POST' });
  });

  it('polls while a scan is running, until it finishes', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const running = { ...completedScan, status: 'RUNNING', finished_at: null, score: null };
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse([running]))
      .mockResolvedValue(jsonResponse([completedScan]));
    vi.stubGlobal('fetch', fetchMock);

    render(<ScansPage />);
    await screen.findByText('RUNNING');
    await vi.advanceTimersByTimeAsync(1600);

    await waitFor(() => expect(screen.getByText('COMPLETED')).toBeInTheDocument());
    const callsWhenDone = fetchMock.mock.calls.length;
    await vi.advanceTimersByTimeAsync(5000);
    expect(fetchMock.mock.calls.length).toBe(callsWhenDone); // polling stopped
  });
});
