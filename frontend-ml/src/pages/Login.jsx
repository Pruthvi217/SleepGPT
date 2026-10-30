import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { adminLogin } from "../services/api";
import { ErrorBanner } from "../components/Feedback";

export default function Login() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const navigate = useNavigate();

  const submit = async (e) => {
    e.preventDefault();
    setLoading(true); setError("");
    try { await adminLogin(username, password); navigate("/"); }
    catch (err) { setError(err.message); }
    finally { setLoading(false); }
  };

  return (
    <div className="center-screen" style={{ background: "var(--ink-950)" }}>
      <div style={{ width: "100%", maxWidth: 380 }}>
        <form className="card" onSubmit={submit} style={{ background: "var(--ink-900)", border: "1px solid var(--ink-700)" }}>
          <span className="mono" style={{ fontSize: "0.75rem", letterSpacing: "0.08em", color: "var(--teal-500)" }}>SLEEPGPT ML</span>
          <h2 style={{ color: "#fff", margin: "0.4rem 0 1.5rem" }}>ML Dashboard Login</h2>
          <ErrorBanner message={error} />
          <div className="field"><label htmlFor="u">Username</label>
            <input id="u" autoFocus value={username} onChange={(e) => setUsername(e.target.value)} /></div>
          <div className="field"><label htmlFor="p">Password</label>
            <input id="p" type="password" value={password} onChange={(e) => setPassword(e.target.value)} /></div>
          <button className="btn btn-primary btn-block" disabled={loading}>{loading ? "Signing in…" : "Sign in"}</button>
          <p style={{ color: "var(--slate-400)", fontSize: "0.78rem", marginTop: "1rem" }}>Uses the same administrator account as the Admin Dashboard.</p>
        </form>
      </div>
    </div>
  );
}
