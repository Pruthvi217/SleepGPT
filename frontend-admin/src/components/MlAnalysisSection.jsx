const DISCLAIMER =
  "Research/informational use only. Not a clinical diagnosis. This ML-derived estimate is for research/informational use and is not a clinical diagnosis. " +
  "Model normalization requires validation against the original training-data statistics and real sensor data.";

const fmt = (iso) => (iso ? new Date(iso).toLocaleString() : "–");
const row = { display: "flex", justifyContent: "space-between", padding: "0.5rem 0", borderBottom: "1px solid var(--ink-700)" };

const ML_URL = import.meta.env.VITE_ML_DASHBOARD_URL || "http://localhost:5175";

export default function MlAnalysisSection({ latest, history, patientId }) {
  return (
    <div style={{ marginBottom: "1.75rem" }}>
      <h3 style={{ color: "#fff", fontSize: "0.95rem", letterSpacing: "0.04em", textTransform: "uppercase", marginBottom: "0.2rem" }}>
        Sleep Analysis (SpO₂)
      </h3>
      <div className="mono" style={{ color: "var(--amber-600)", fontSize: "0.72rem", marginBottom: "0.6rem" }}>
        Estimated AHI — Unvalidated
      </div>
      {!latest ? (
        <p style={{ color: "var(--slate-400)", fontSize: "0.9rem" }}>No ML analysis saved for this patient yet.</p>
      ) : (
        [
          ["Estimated AHI", `${latest.estimated_ahi} /h`],
          ["Detected events", latest.detected_events],
          ["Analysed duration", `${latest.sleep_duration_hours} h`],
          ["Average SpO₂", `${latest.average_spo2} %`],
          ["Minimum SpO₂", `${latest.minimum_spo2} %`],
          ["Latest analysis", fmt(latest.created_at)],
          ["Data source", latest.source],
          ["Model / normalization", `${latest.model_name} / ${latest.normalization_mode}`],
        ].map(([k, v]) => (
          <div key={k} style={row}>
            <span style={{ color: "var(--slate-400)", fontSize: "0.88rem" }}>{k}</span>
            <span className="mono" style={{ color: "#fff", fontSize: "0.88rem" }}>{String(v)}</span>
          </div>
        ))
      )}
      {history && history.length > 1 && (
        <details style={{ marginTop: "0.75rem" }}>
          <summary style={{ color: "var(--slate-400)", cursor: "pointer", fontSize: "0.85rem" }}>
            Analysis history ({history.length})
          </summary>
          {history.map((a) => (
            <div key={a.analysis_id} className="mono" style={{ ...row, fontSize: "0.78rem", color: "#fff" }}>
              <span>{fmt(a.created_at)} · {a.source}</span>
              <span>AHI {a.estimated_ahi} · {a.detected_events} ev · {a.sleep_duration_hours} h</span>
            </div>
          ))}
        </details>
      )}
      <p style={{ marginTop: "0.6rem" }}>
        <a href={ML_URL} target="_blank" rel="noreferrer" style={{ color: "var(--teal-500)", fontSize: "0.85rem" }}>
          Run a new analysis{patientId ? ` for ${patientId}` : ""} in the ML dashboard ↗
        </a>
      </p>
      <p style={{ color: "var(--slate-400)", fontSize: "0.78rem", marginTop: "0.6rem" }}>{DISCLAIMER}</p>
    </div>
  );
}
