import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { adminLogin } from "../services/api";
import { ErrorBanner } from "../components/Feedback";

export const SESSION_KEY = "sleepgpt_admin_session";

export default function AdminLogin() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      await adminLogin(username, password);
      sessionStorage.setItem(SESSION_KEY, username);
      navigate("/");
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="center-screen" style={{ background: "var(--ink-950)" }}>
      <div style={{ width: "100%", maxWidth: 380 }}>
        <div className="card" style={{ background: "var(--ink-900)", border: "1px solid var(--ink-700)" }}>
          <span className="mono" style={{ fontSize: "0.75rem", letterSpacing: "0.08em", color: "var(--teal-500)" }}>
            SLEEPGPT ADMIN
          </span>
          <h2 style={{ color: "#fff", marginTop: "0.4rem", marginBottom: "1.5rem" }}>Administrator Login</h2>

          <ErrorBanner message={error} />

          <form onSubmit={handleSubmit}>
            <div className="field">
              <label htmlFor="admin-username" style={{ color: "var(--slate-400)" }}>
                Username
              </label>
              <input id="admin-username" autoFocus value={username} onChange={(e) => setUsername(e.target.value)} />
            </div>
            <div className="field">
              <label htmlFor="admin-password" style={{ color: "var(--slate-400)" }}>
                Password
              </label>
              <input id="admin-password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
            </div>
            <button type="submit" className="btn btn-primary btn-block" disabled={loading}>
              {loading ? "Logging in…" : "Login"}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
