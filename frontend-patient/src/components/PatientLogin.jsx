import { useState } from "react";
import { registerPatient, loginPatient } from "../services/api";
import { ErrorBanner } from "./Feedback";
import BreathWave from "./BreathWave";

const MODE = { CHOOSE: "choose", NEW: "new", EXISTING: "existing", REGISTERED: "registered" };

export default function PatientLogin({ onLoggedIn }) {
  const [mode, setMode] = useState(MODE.CHOOSE);
  const [username, setUsername] = useState("");
  const [patientIdInput, setPatientIdInput] = useState("");
  const [newPatientId, setNewPatientId] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleRegister = async (e) => {
    e.preventDefault();
    if (!username.trim()) return;
    setLoading(true);
    setError("");
    try {
      const data = await registerPatient(username.trim());
      setNewPatientId(data.patient_id);
      setMode(MODE.REGISTERED);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleLogin = async (e) => {
    e.preventDefault();
    if (!patientIdInput.trim()) return;
    setLoading(true);
    setError("");
    try {
      const data = await loginPatient(patientIdInput.trim());
      onLoggedIn(data.patient_id);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  if (mode === MODE.CHOOSE) {
    return (
      <div className="stack" style={{ gap: "0.75rem" }}>
        <button className="btn btn-primary btn-block" onClick={() => setMode(MODE.NEW)}>
          New User
        </button>
        <button className="btn btn-secondary btn-block" onClick={() => setMode(MODE.EXISTING)}>
          Existing User
        </button>
      </div>
    );
  }

  if (mode === MODE.NEW) {
    return (
      <form onSubmit={handleRegister}>
        <ErrorBanner message={error} />
        <div className="field">
          <label htmlFor="username">Enter Username</label>
          <input id="username" autoFocus value={username} onChange={(e) => setUsername(e.target.value)} placeholder="e.g. John" />
        </div>
        <button type="submit" className="btn btn-primary btn-block" disabled={loading}>
          {loading ? "Registering…" : "Register"}
        </button>
        <button type="button" className="btn btn-ghost" onClick={() => setMode(MODE.CHOOSE)} style={{ marginTop: "0.5rem" }}>
          ← Back
        </button>
      </form>
    );
  }

  if (mode === MODE.EXISTING) {
    return (
      <form onSubmit={handleLogin}>
        <ErrorBanner message={error} />
        <div className="field">
          <label htmlFor="patientId">Enter Patient ID</label>
          <input
            id="patientId"
            autoFocus
            value={patientIdInput}
            onChange={(e) => setPatientIdInput(e.target.value)}
            placeholder="SGP-XXXXXX"
          />
        </div>
        <button type="submit" className="btn btn-primary btn-block" disabled={loading}>
          {loading ? "Logging in…" : "Login"}
        </button>
        <button type="button" className="btn btn-ghost" onClick={() => setMode(MODE.CHOOSE)} style={{ marginTop: "0.5rem" }}>
          ← Back
        </button>
      </form>
    );
  }

  if (mode === MODE.REGISTERED) {
    return (
      <div className="stack" style={{ alignItems: "center", textAlign: "center" }}>
        <BreathWave width={200} height={26} />
        <h2>Registration Successful</h2>
        <p className="muted" style={{ marginBottom: "0.2rem" }}>Your Patient ID</p>
        <div
          className="mono"
          style={{
            fontSize: "1.6rem",
            fontWeight: 600,
            background: "var(--teal-tint)",
            color: "var(--teal-700)",
            padding: "0.5rem 1.2rem",
            borderRadius: "var(--radius-md)",
            letterSpacing: "0.03em",
          }}
        >
          {newPatientId}
        </div>
        <p style={{ maxWidth: 340 }}>
          <strong>Important:</strong> Save this ID. You will need it to log in
          again and to check your results later.
        </p>
        <button className="btn btn-primary btn-block" onClick={() => onLoggedIn(newPatientId)}>
          Start Assessment
        </button>
      </div>
    );
  }

  return null;
}
