import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import * as api from "../services/api";
import { ErrorBanner, Loading } from "../components/Feedback";

const DISCLAIMER =
  "Research/informational use only. Not a clinical diagnosis. This ML-derived estimate is for research/informational use and is not a clinical diagnosis. " +
  "Model normalization requires validation against the original training-data statistics and real sensor data.";

const card = { background: "var(--ink-900)", border: "1px solid var(--ink-700)", marginBottom: "1.25rem" };
const h3 = { color: "#fff", fontSize: "0.9rem", marginBottom: "0.8rem" };
const muted = { color: "var(--slate-400)", fontSize: "0.85rem" };
const fmt = (iso) => (iso ? new Date(iso).toLocaleString() : "–");

function Chart({ points }) {
  if (!points?.length) return null;
  const W = 640, H = 120, ys = points.map((p) => p.spo2);
  const lo = Math.min(...ys) - 1, hi = Math.max(...ys) + 1;
  const d = points.map((p, i) => `${(i / Math.max(1, points.length - 1)) * W},${H - ((p.spo2 - lo) / (hi - lo)) * H}`).join(" ");
  return (
    <svg viewBox={`0 0 ${W} ${H}`} style={{ width: "100%", height: 120, background: "var(--ink-950)", borderRadius: 8 }}>
      <polyline points={d} fill="none" stroke="var(--teal-500)" strokeWidth="1.2" />
      <text x="4" y="12" fill="#8b97a8" fontSize="10">{hi.toFixed(0)}%</text>
      <text x="4" y={H - 4} fill="#8b97a8" fontSize="10">{lo.toFixed(0)}%</text>
    </svg>
  );
}

function Preview({ p }) {
  if (!p) return null;
  return (
    <div style={{ marginTop: "1rem" }}>
      {p.errors?.length > 0 && (
        <div className="banner banner-error" role="alert"><div>{p.errors.map((e, i) => <div key={i}>{e}</div>)}</div></div>
      )}
      {p.start && (
        <>
          <p style={muted}>
            {p.rows_total} rows · {fmt(p.start)} → {fmt(p.end)} · {p.duration_minutes} min · SpO₂ avg {p.average_spo2}% / min {p.minimum_spo2}% / max {p.maximum_spo2}%
            {p.median_interval_s != null && ` · median interval ${p.median_interval_s}s`}
          </p>
          <Chart points={p.chart} />
          <p style={{ ...muted, fontSize: "0.75rem" }}>
            Model input: {p.model_input.window_samples}-sample windows ({p.model_input.window_seconds}s @ {p.model_input.sample_rate_hz} Hz); the series is resampled to 8 Hz.
            {p.dropped && Object.values(p.dropped).some((n) => n > 0) && ` Dropped: ${JSON.stringify(p.dropped)}`}
          </p>
        </>
      )}
    </div>
  );
}

function ResultCard({ r }) {
  const items = [
    ["Estimated AHI", `${r.estimated_ahi} /h`], ["Detected events", r.detected_events],
    ["Analysed duration", `${r.sleep_duration_hours} h`], ["Average SpO₂", `${r.average_spo2} %`],
    ["Minimum SpO₂", `${r.minimum_spo2} %`], ["Maximum SpO₂", `${r.maximum_spo2} %`],
    ["Analysed samples", `${r.analysed_samples} @ ${r.sampling_rate_hz} Hz (windows ${r.windows_analysed}/${r.windows_total}, apnea ${r.windows_apnea})`],
    ["Source", r.source], ["Patient ID", r.patient_id], ["Model", `${r.model_name} (${r.model_version})`],
    ["Normalization", `${r.normalization_mode} — ${r.validation_status}`],
    ["Analysed window", `${fmt(r.analysis_start)} → ${fmt(r.analysis_end)}`], ["Saved at", fmt(r.created_at)],
  ];
  return (
    <div className="card" style={{ ...card, borderColor: "var(--teal-500)" }}>
      <div className="mono" style={{ color: "var(--amber-600)", fontSize: "0.75rem" }}>Estimated AHI — Unvalidated</div>
      <div className="mono" style={{ color: "#fff", fontSize: "2rem", margin: "0.3rem 0 0.8rem" }}>{r.estimated_ahi} <span style={{ fontSize: "0.9rem", color: "var(--slate-400)" }}>events/hour</span></div>
      {items.map(([k, v]) => (
        <div key={k} style={{ display: "flex", justifyContent: "space-between", padding: "0.4rem 0", borderBottom: "1px solid var(--ink-700)" }}>
          <span style={muted}>{k}</span><span className="mono" style={{ color: "#fff", fontSize: "0.82rem", textAlign: "right", maxWidth: "65%" }}>{String(v)}</span>
        </div>
      ))}
      {r.warnings?.map((w, i) => <p key={i} style={{ color: "var(--amber-600)", fontSize: "0.78rem", marginTop: "0.5rem" }}>⚠ {w}</p>)}
      <p style={{ ...muted, fontSize: "0.78rem", marginTop: "0.6rem" }}>{DISCLAIMER}</p>
    </div>
  );
}

export default function MlDashboard() {
  const navigate = useNavigate();
  const [health, setHealth] = useState(null);
  const [patients, setPatients] = useState([]);
  const [pid, setPid] = useState("");
  const [source, setSource] = useState("manual");
  const [file, setFile] = useState(null);
  const [device, setDevice] = useState("");
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [preview, setPreview] = useState(null);
  const [sensors, setSensors] = useState(null);
  const [result, setResult] = useState(null);
  const [history, setHistory] = useState([]);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState({ message: "", details: [] });
  const fileRef = useRef(null);

  const fail = (e) => setError({ message: e.message, details: e.details || [] });

  useEffect(() => {
    if (!api.hasSession()) { navigate("/login"); return; }
    api.getHealth().then(setHealth).catch(fail);
    api.listPatients().then((d) => setPatients(d.patients)).catch(fail);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const loadHistory = (id) => api.getHistory(id).then((d) => setHistory(d.history)).catch(fail);
  const reset = () => { setPreview(null); setResult(null); setSensors(null); setError({ message: "", details: [] }); };

  const pickPatient = (id) => { setPid(id); reset(); setHistory([]); if (id) loadHistory(id); };

  const ubBody = () => ({
    start: new Date(start).toISOString(), end: new Date(end).toISOString(), device_label: device.trim() || null,
  });

  const wrap = (label, fn) => async () => {
    setBusy(label); setError({ message: "", details: [] });
    try { await fn(); } catch (e) { fail(e); } finally { setBusy(""); }
  };

  const doPreview = wrap("preview", async () => {
    setResult(null);
    setPreview(source === "manual" ? await api.previewManual(pid, file) : await api.previewUbidots(pid, ubBody()));
  });
  const doSensors = wrap("sensors", async () => {
    const b = ubBody(); setSensors(await api.getSensorData(pid, b.start, b.end, b.device_label));
  });
  const doRun = wrap("run", async () => {
    const r = source === "manual" ? await api.runManual(pid, file) : await api.runUbidots(pid, ubBody());
    setResult(r); await loadHistory(pid);
  });

  const ready = pid && (source === "manual" ? file : start && end);

  return (
    <div style={{ minHeight: "100vh", background: "var(--ink-950)" }}>
      <header style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "1.1rem 1.75rem", borderBottom: "1px solid var(--ink-700)" }}>
        <div>
          <span className="mono" style={{ color: "var(--teal-500)", fontSize: "0.75rem", letterSpacing: "0.08em" }}>SLEEPGPT</span>
          <h1 style={{ color: "#fff", fontSize: "1.15rem", margin: 0 }}>ML Dashboard — SomnNET SpO₂</h1>
        </div>
        <button className="btn btn-ghost" style={{ color: "var(--slate-400)" }} onClick={() => { api.clearSession(); navigate("/login"); }}>Log out</button>
      </header>

      <div style={{ maxWidth: 1080, margin: "0 auto", padding: "2rem 1.75rem" }}>
        <div className="banner banner-warn" style={{ marginBottom: "1.25rem" }}>
          <span>⚠</span>
          <span><strong>Estimated AHI — Unvalidated.</strong> {DISCLAIMER}
            {health && ` Model: ${health.model_loaded ? "loaded (CPU)" : "NOT loaded"} · normalization mode: ${health.normalization_mode} · Ubidots: ${health.ubidots_configured ? "configured" : "token not set"}.`}
          </span>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "340px 1fr", gap: "1.75rem" }}>
          <div>
            <div className="card" style={card}>
              <h3 style={h3}>1 · Patient (existing SGP-XXXXXX)</h3>
              <div className="field"><select value={pid} onChange={(e) => pickPatient(e.target.value)}>
                <option value="">Select a patient…</option>
                {patients.map((p) => <option key={p.patient_id} value={p.patient_id}>{p.patient_id} — {p.username}</option>)}
              </select></div>
              {patients.length === 0 && <p style={{ ...muted, marginTop: "0.6rem" }}>No patients yet. Patients register in the patient app.</p>}
            </div>

            <div className="card" style={card}>
              <h3 style={h3}>2 · Data source</h3>
              <div style={{ display: "flex", gap: "0.5rem", marginBottom: "1rem" }}>
                {["manual", "ubidots"].map((s) => (
                  <button key={s} className={`btn ${source === s ? "btn-primary" : "btn-secondary"}`} onClick={() => { setSource(s); setPreview(null); setResult(null); }}>
                    {s === "manual" ? "Manual CSV" : "Ubidots"}
                  </button>
                ))}
              </div>

              {source === "manual" ? (
                <div className="field">
                  <label htmlFor="csv">CSV with columns: timestamp,spo2</label>
                  <input id="csv" ref={fileRef} type="file" accept=".csv,text/csv" onChange={(e) => { setFile(e.target.files[0] || null); setPreview(null); setResult(null); }} />
                </div>
              ) : (
                <>
                  <div className="field"><label htmlFor="dev">Device label (blank = server default)</label>
                    <input id="dev" value={device} placeholder="esp32_health_monitor" onChange={(e) => setDevice(e.target.value)} /></div>
                  <div className="field"><label htmlFor="st">Start (your local time)</label>
                    <input id="st" type="datetime-local" value={start} onChange={(e) => setStart(e.target.value)} /></div>
                  <div className="field"><label htmlFor="en">End (your local time)</label>
                    <input id="en" type="datetime-local" value={end} onChange={(e) => setEnd(e.target.value)} /></div>
                  <p style={{ ...muted, fontSize: "0.75rem" }}>Ubidots has one shared device; you are choosing which patient this session belongs to. Max 48 h.</p>
                </>
              )}

              <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap", marginTop: "0.8rem" }}>
                <button className="btn btn-secondary" disabled={!ready || busy} onClick={doPreview}>{busy === "preview" ? "Loading…" : "Preview / validate"}</button>
                {source === "ubidots" && <button className="btn btn-secondary" disabled={!ready || busy} onClick={doSensors}>{busy === "sensors" ? "Loading…" : "All sensor data"}</button>}
                <button className="btn btn-primary" disabled={!ready || busy || (preview && !preview.valid)} onClick={doRun}>{busy === "run" ? "Running model…" : "Run & save analysis"}</button>
              </div>
            </div>
          </div>

          <div>
            {(error.message) && (
              <div className="banner banner-error" role="alert" style={{ marginBottom: "1rem" }}>
                <div><strong>{error.message}</strong>{error.details.map((d, i) => <div key={i} style={{ fontSize: "0.82rem" }}>{d}</div>)}</div>
              </div>
            )}
            {busy && <Loading label={busy === "run" ? "Running the pretrained SomnNET model on CPU…" : "Working…"} />}
            {!busy && preview && <div className="card" style={card}><h3 style={h3}>Preview</h3><Preview p={preview} /></div>}
            {sensors && (
              <div className="card" style={card}>
                <h3 style={h3}>Ubidots sensor data — {sensors.device_label}</h3>
                {Object.entries(sensors.variables).map(([k, v]) => (
                  <div key={k} className="mono" style={{ color: "#fff", fontSize: "0.82rem", padding: "0.3rem 0" }}>{k}: {v.count} points{v.count ? "" : " (none)"}</div>
                ))}
                <p style={{ ...muted, fontSize: "0.75rem" }}>Only SpO₂ feeds the SomnNET model; the other variables are retained for future models.</p>
              </div>
            )}
            {!busy && result && <ResultCard r={result} />}

            <div className="card" style={card}>
              <h3 style={h3}>Analysis history{pid ? ` — ${pid}` : ""}</h3>
              {!pid && <p style={muted}>Select a patient.</p>}
              {pid && history.length === 0 && <p style={muted}>No analyses saved for this patient.</p>}
              {history.map((a) => (
                <div key={a.analysis_id} className="mono" style={{ display: "flex", justifyContent: "space-between", gap: "1rem", padding: "0.45rem 0", borderBottom: "1px solid var(--ink-700)", fontSize: "0.78rem", color: a.status === "failed" ? "var(--coral-600)" : "#fff" }}>
                  <span>{fmt(a.created_at)} · {a.source}</span>
                  <span style={{ textAlign: "right" }}>
                    {a.status === "failed" ? `FAILED: ${a.error_message}` : `AHI ${a.estimated_ahi} · ${a.detected_events} ev · ${a.sleep_duration_hours} h · SpO₂ ${a.average_spo2}/${a.minimum_spo2} · ${a.normalization_mode}`}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
