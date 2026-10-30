import { useEffect, useState } from "react";
import { getMlLatest, getMlHistory, askChat } from "../services/api";

export const ML_DISCLAIMER =
  "Research/informational use only. Not a clinical diagnosis. This ML-derived estimate is for research/informational use and is not a clinical diagnosis. " +
  "Model normalization requires validation against the original training-data statistics and real sensor data.";

function Metric({ label, value, unit }) {
  return (
    <div style={{ padding: "0.6rem 0.75rem", border: "1px solid var(--line)", borderRadius: 8 }}>
      <div className="muted" style={{ fontSize: "0.72rem" }}>{label}</div>
      <div className="mono" style={{ fontSize: "1.05rem", fontWeight: 600 }}>
        {value ?? "–"}{value != null && unit ? ` ${unit}` : ""}
      </div>
    </div>
  );
}

const fmt = (iso) => (iso ? new Date(iso).toLocaleString() : "–");

export default function SleepAnalysisPanel({ patientId }) {
  const [latest, setLatest] = useState(undefined); // undefined = loading, null = none
  const [history, setHistory] = useState([]);
  const [error, setError] = useState("");
  const [answer, setAnswer] = useState("");
  const [asking, setAsking] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [l, h] = await Promise.all([getMlLatest(patientId), getMlHistory(patientId)]);
        if (!cancelled) { setLatest(l.latest); setHistory(h.history); }
      } catch (e) {
        if (!cancelled) { setError(e.message); setLatest(null); }
      }
    })();
    return () => { cancelled = true; };
  }, [patientId]);

  const explain = async () => {
    setAsking(true); setAnswer("");
    try {
      const r = await askChat(patientId, "Please explain my latest Estimated AHI and SpO2 sleep analysis result in simple terms.");
      setAnswer(r.response);
    } catch (e) { setAnswer(e.message); } finally { setAsking(false); }
  };

  return (
    <div className="card" style={{ marginTop: "1.25rem" }}>
      <h3 style={{ fontSize: "1.05rem", marginBottom: "0.2rem" }}>Sleep Analysis (SpO₂)</h3>
      <div className="mono" style={{ fontSize: "0.72rem", color: "var(--amber-600)", marginBottom: "0.75rem" }}>
        Estimated AHI — Unvalidated
      </div>
      {error && <p className="field-error">{error}</p>}
      {latest === undefined && !error && <p className="muted">Loading…</p>}
      {latest === null && !error && (
        <p className="muted">No ML sleep analysis is available for your Patient ID yet.</p>
      )}
      {latest && (
        <>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.5rem" }}>
            <Metric label="Estimated AHI" value={latest.estimated_ahi} unit="/h" />
            <Metric label="Detected events" value={latest.detected_events} />
            <Metric label="Analysed duration" value={latest.sleep_duration_hours} unit="h" />
            <Metric label="Average SpO₂" value={latest.average_spo2} unit="%" />
            <Metric label="Minimum SpO₂" value={latest.minimum_spo2} unit="%" />
            <Metric label="Data source" value={latest.source} />
          </div>
          <p className="muted" style={{ fontSize: "0.78rem", marginTop: "0.6rem" }}>
            Analysis date: {fmt(latest.created_at)} · {latest.model_name} · normalization: {latest.normalization_mode}
          </p>
          <button className="btn btn-secondary" onClick={explain} disabled={asking} style={{ marginTop: "0.5rem" }}>
            {asking ? "Asking…" : "Explain my result"}
          </button>
          {answer && <p style={{ marginTop: "0.75rem", whiteSpace: "pre-wrap" }}>{answer}</p>}
        </>
      )}
      {history.length > 1 && (
        <div style={{ marginTop: "1rem" }}>
          <h4 style={{ fontSize: "0.9rem" }}>History</h4>
          {history.map((a) => (
            <div key={a.analysis_id} className="mono" style={{ fontSize: "0.78rem", display: "flex", justifyContent: "space-between", padding: "0.3rem 0", borderBottom: "1px solid var(--line)" }}>
              <span>{fmt(a.created_at)} · {a.source}</span>
              <span>AHI {a.estimated_ahi}</span>
            </div>
          ))}
        </div>
      )}
      <div className="banner banner-info" style={{ marginTop: "1rem" }}>
        <span>ℹ</span>
        <span>{ML_DISCLAIMER}</span>
      </div>
    </div>
  );
}
