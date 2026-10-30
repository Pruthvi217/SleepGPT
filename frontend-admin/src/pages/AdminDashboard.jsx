import { useEffect, useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import PatientSearch from "../components/PatientSearch";
import AdminPatientResults from "../components/AdminPatientResults";
import { Loading, ErrorBanner } from "../components/Feedback";
import { listPatients, getPatientDetail, getMlSummary, TOKEN_KEY } from "../services/api";
import { SESSION_KEY } from "./AdminLogin";

export default function AdminDashboard() {
  const navigate = useNavigate();
  const [patients, setPatients] = useState([]);
  const [selected, setSelected] = useState(null);
  const [mlLatest, setMlLatest] = useState({});
  const [loadingList, setLoadingList] = useState(true);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!sessionStorage.getItem(SESSION_KEY)) {
      navigate("/login");
      return;
    }
    refreshList();

    // Live queue: a patient's completed assessment is pushed into the
    // admin panel automatically, without requiring a manual refresh.
    const pollId = setInterval(() => refreshList({ silent: true }), 8000);
    return () => clearInterval(pollId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const refreshList = async (opts = {}) => {
    const { silent = false } = opts;
    if (!silent) setLoadingList(true);
    try {
      const data = await listPatients();
      setPatients(data.patients);
      try {
        setMlLatest((await getMlSummary()).latest || {});
      } catch {
        /* ML summary is optional for the list */
      }
    } catch (err) {
      if (!silent) setError(err.message);
    } finally {
      if (!silent) setLoadingList(false);
    }
  };

  const openPatient = async (patientId) => {
    setLoadingDetail(true);
    setError("");
    try {
      const detail = await getPatientDetail(patientId);
      setSelected(detail);
    } catch (err) {
      setError(err.message);
      setSelected(null);
    } finally {
      setLoadingDetail(false);
    }
  };

  const handleLogout = () => {
    sessionStorage.removeItem(SESSION_KEY);
    sessionStorage.removeItem(TOKEN_KEY);
    navigate("/login");
  };

  return (
    <div style={{ minHeight: "100vh", background: "var(--ink-950)" }}>
      <header
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          padding: "1.1rem 1.75rem",
          borderBottom: "1px solid var(--ink-700)",
        }}
      >
        <div>
          <span className="mono" style={{ color: "var(--teal-500)", fontSize: "0.75rem", letterSpacing: "0.08em" }}>
            SLEEPGPT
          </span>
          <h1 style={{ color: "#fff", fontSize: "1.15rem", margin: 0 }}>Admin Dashboard</h1>
        </div>
        <button className="btn btn-ghost" onClick={handleLogout} style={{ color: "var(--slate-400)" }}>
          Log out
        </button>
      </header>

      <div style={{ maxWidth: 1080, margin: "0 auto", padding: "2rem 1.75rem", display: "grid", gridTemplateColumns: "320px 1fr", gap: "1.75rem" }}>
        <div>
          <div className="card" style={{ background: "var(--ink-900)", border: "1px solid var(--ink-700)", marginBottom: "1.25rem" }}>
            <h3 style={{ color: "#fff", fontSize: "0.9rem", marginBottom: "0.9rem" }}>Search Patient</h3>
            <PatientSearch onSearch={openPatient} loading={loadingDetail} />
          </div>

          <div className="card" style={{ background: "var(--ink-900)", border: "1px solid var(--ink-700)" }}>
            <h3 style={{ color: "#fff", fontSize: "0.9rem", marginBottom: "0.75rem" }}>All Patients</h3>
            {loadingList && <Loading label="Loading patients…" />}
            {!loadingList && patients.length === 0 && (
              <p style={{ color: "var(--slate-400)", fontSize: "0.85rem" }}>No patients registered yet.</p>
            )}
            <div className="stack" style={{ gap: "0.4rem" }}>
              {patients.map((p) => (
                <button
                  key={p.patient_id}
                  onClick={() => openPatient(p.patient_id)}
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    background: "transparent",
                    border: "1px solid var(--ink-700)",
                    borderRadius: 8,
                    padding: "0.6rem 0.8rem",
                    color: "#fff",
                    cursor: "pointer",
                    textAlign: "left",
                  }}
                >
                  <span>
                    <div style={{ fontSize: "0.85rem" }}>{p.username}</div>
                    <div className="mono" style={{ fontSize: "0.72rem", color: "var(--slate-400)" }}>
                      {p.patient_id}
                      {mlLatest[p.patient_id] && ` · est. AHI ${mlLatest[p.patient_id].estimated_ahi}`}
                    </div>
                  </span>
                  <span
                    className="mono"
                    style={{
                      fontSize: "0.68rem",
                      color: !p.assessment_completed ? "var(--slate-400)" : p.result_visible ? "var(--sage-600)" : "var(--amber-600)",
                    }}
                  >
                    {!p.assessment_completed ? "IN PROGRESS" : p.result_visible ? "RELEASED" : "PENDING"}
                  </span>
                </button>
              ))}
            </div>
          </div>
        </div>

        <div className="card" style={{ background: "var(--ink-900)", border: "1px solid var(--ink-700)" }}>
          <ErrorBanner message={error} />
          {loadingDetail && <Loading label="Loading patient record…" />}
          {!loadingDetail && !selected && (
            <p style={{ color: "var(--slate-400)" }}>Search or select a patient to view their record.</p>
          )}
          {!loadingDetail && selected && (
            <AdminPatientResults patient={selected} onReleased={() => openPatient(selected.patient_id).then(refreshList)} />
          )}
        </div>
      </div>
    </div>
  );
}
