export function Loading({ label = "Loading…" }) {
  return (
    <div className="stack" style={{ alignItems: "center", padding: "2rem 0", color: "var(--slate-400)" }}>
      <div
        aria-hidden="true"
        style={{
          width: 28,
          height: 28,
          borderRadius: "50%",
          border: "3px solid var(--paper-dim)",
          borderTopColor: "var(--teal-500)",
          animation: "spin 0.8s linear infinite",
        }}
      />
      <span style={{ fontSize: "0.85rem" }}>{label}</span>
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}

export function ErrorBanner({ message, onRetry }) {
  if (!message) return null;
  return (
    <div className="banner banner-error" role="alert">
      <span>⚠</span>
      <span style={{ flex: 1 }}>
        {message}
        {onRetry && (
          <>
            {"  "}
            <button className="btn-ghost" onClick={onRetry} style={{ padding: 0, textDecoration: "underline" }}>
              Try again
            </button>
          </>
        )}
      </span>
    </div>
  );
}
