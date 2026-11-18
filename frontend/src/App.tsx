import { ScanPage } from './pages/ScanPage';
import { ScansPage } from './pages/ScansPage';
import { useHashRoute } from './useHashRoute';

export function App() {
  const route = useHashRoute();
  return (
    <div className="app">
      <header className="topbar">
        <a href="#/" className="brand">
          Mini Gauntlet
        </a>
        <span className="muted">Cloud posture scanner</span>
      </header>
      <main>
        {/* key: a different scan ID gets a fresh page with fresh state */}
        {route.page === 'scan' ? (
          <ScanPage key={route.scanId} scanId={route.scanId} />
        ) : (
          <ScansPage />
        )}
      </main>
    </div>
  );
}
