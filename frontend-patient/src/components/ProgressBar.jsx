export default function ProgressBar({ answered, total }) {
  const pct = total > 0 ? Math.min(100, Math.round((answered / total) * 100)) : 0;
  return (
    <div style={{ marginBottom: "0.4rem" }}>
      <div
        role="progressbar"
        aria-valuenow={pct}
        aria-valuemin={0}
        aria-valuemax={100}
        style={{
          height: 8,
          borderRadius: 999,
          background: "var(--paper-dim)",
          overflow: "hidden",
        }}
      >
        <div
          style={{
            height: "100%",
            width: `${pct}%`,
            background: "var(--teal-600)",
            borderRadius: 999,
            transition: "width 0.25s ease",
          }}
        />
      </div>
    </div>
  );
}
