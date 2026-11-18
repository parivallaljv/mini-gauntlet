import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { rdpFinding, XSS_DETAILS } from '../test/fixtures';
import { FindingsTable } from './FindingsTable';

describe('FindingsTable', () => {
  it('renders an <img onerror> description as plain text, not HTML', () => {
    const alertSpy = vi.fn();
    vi.stubGlobal('alert', alertSpy);

    const { container } = render(<FindingsTable findings={[rdpFinding]} />);

    // The exact string is visible as text...
    expect(screen.getByText(XSS_DETAILS)).toBeInTheDocument();
    // ...and no element was created from it, so nothing can run.
    expect(container.querySelector('img')).toBeNull();
    expect(alertSpy).not.toHaveBeenCalled();
  });

  it('shows the finding fields and marks account-level findings', () => {
    const accountLevel = { ...rdpFinding, id: 11, resource_id: null, region: null };
    render(<FindingsTable findings={[rdpFinding, accountLevel]} />);

    expect(screen.getAllByText('GCP-VPC-01')).toHaveLength(2);
    expect(screen.getByText('allow-rdp-anywhere')).toBeInTheDocument();
    expect(screen.getByText('(whole account)')).toBeInTheDocument();
    expect(screen.getAllByText('CRITICAL')).toHaveLength(2);
  });

  it('shows an empty state when nothing matches', () => {
    render(<FindingsTable findings={[]} />);
    expect(screen.getByText('No findings match these filters.')).toBeInTheDocument();
  });
});
