import { useEffect } from 'react';

export const POLL_INTERVAL_MS = 1500;

/** Call `callback` every POLL_INTERVAL_MS while `active` is true. */
export function usePolling(callback: () => void, active: boolean): void {
  useEffect(() => {
    if (!active) return;
    const timer = window.setInterval(callback, POLL_INTERVAL_MS);
    return () => window.clearInterval(timer); // stop when inactive or unmounted
  }, [callback, active]);
}
