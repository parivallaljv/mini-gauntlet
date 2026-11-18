export function ErrorMessage({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="error" role="alert">
      <span>{message}</span>
      {onRetry && (
        <button type="button" className="secondary" onClick={onRetry}>
          Retry
        </button>
      )}
    </div>
  );
}
