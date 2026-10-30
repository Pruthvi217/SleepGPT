import { Link } from "react-router-dom";
import BreathWave from "../components/BreathWave";

export default function Welcome() {
  return (
    <div className="center-screen">
      <div style={{ width: "100%", maxWidth: 460, textAlign: "center" }}>
        <BreathWave width={280} height={34} />
        <h1 style={{ fontSize: "2.4rem", marginTop: "0.75rem" }}>Welcome to SleepGPT</h1>
        <p style={{ maxWidth: 380, margin: "0 auto 2rem" }}>
          A sleep apnea screening and clinical decision-support assistant.
          Answer a short questionnaire and a clinician will review your results.
        </p>

        <div className="stack" style={{ gap: "0.75rem" }}>
          <Link to="/assessment" className="btn btn-primary btn-block">
            New User
          </Link>
          <Link to="/assessment" className="btn btn-secondary btn-block">
            Existing User
          </Link>
        </div>

        <p className="muted" style={{ fontSize: "0.78rem", marginTop: "2.5rem" }}>
          SleepGPT is a screening tool, not a diagnostic device.
        </p>
      </div>
    </div>
  );
}
