import { useEffect, useState } from 'react';

export type Route = { page: 'scans' } | { page: 'scan'; scanId: number };

/** "#/scans/7" -> the scan page for scan 7; anything else -> the scans list. */
export function parseHash(hash: string): Route {
  const match = /^#\/scans\/(\d+)$/.exec(hash);
  return match ? { page: 'scan', scanId: Number(match[1]) } : { page: 'scans' };
}

export function scanHref(scanId: number): string {
  return `#/scans/${scanId}`;
}

/**
 * Tiny hash-based router: two pages don't need a routing library.
 * Hash URLs also work behind any static file server without rewrite rules.
 */
export function useHashRoute(): Route {
  const [route, setRoute] = useState(() => parseHash(window.location.hash));
  useEffect(() => {
    const onChange = () => setRoute(parseHash(window.location.hash));
    window.addEventListener('hashchange', onChange);
    return () => window.removeEventListener('hashchange', onChange);
  }, []);
  return route;
}
