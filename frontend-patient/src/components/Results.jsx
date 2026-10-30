import RiskBadge from "./RiskBadge";
import BreathWave from "./BreathWave";

function ScoreRow({ label, value, max, risk }) {
  return (
    <div
      style={{
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
        padding: "0.85rem 0",
        borderBottom: "1px solid var(--line)",
      }}
    >
      <span style={{ fontWeight: 600 }}>{label}</span>
      <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
        <span className="mono">
          {value ?? "–"}
          {max ? ` / ${max}` : ""}
        </span>
        <RiskBadge risk={risk} />
      </div>
    </div>
  );
}

export default function Results({ patientId, data, onLogout }) {
  if (!data.completed) {
    return (
      <div className="stack" style={{ alignItems: "center", textAlign: "center", padding: "1rem 0" }}>
        <h2>Assessment not yet completed</h2>
        <p>Please continue your assessment to see results.</p>
      </div>
    );
  }

  if (!data.result_visible) {
    return (
      <div className="stack" style={{ alignItems: "center", textAlign: "center", padding: "1.5rem 0" }}>
        <BreathWave width={200} height={26} />
        <h2>Assessment completed</h2>
        <p>
          Your assessment has been submitted for review. Please wait for the
          administrator to release your results, then check back here.
        </p>
        <button className="btn btn-secondary" onClick={onLogout}>
          Log out
        </button>
      </div>
    );
  }

  const { results, rag_analysis, summary } = data;

  const handlePrint = () => window.print();

  return (
    <div className="stack" style={{ gap: "1.5rem" }} id="report-root">
      <div className="print-only" style={{ display: "none" }}>
        <h1 style={{ fontSize: "1.3rem" }}>SleepGPT — Sleep Apnea Screening Report</h1>
        <p>Patient ID: {patientId}</p>
      </div>

      <div>
        <span className="muted" style={{ fontSize: "0.85rem", fontWeight: 600 }}>
          PATIENT ID: {patientId}
        </span>
        <h2 style={{ marginTop: "0.3rem" }}>Assessment Results</h2>
        <RiskBadge risk={results.overall_risk} label="Overall" />
      </div>

      <div className="card" style={{ padding: "1.25rem 1.5rem" }}>
        <ScoreRow label="BMI" value={results.bmi} />
        <ScoreRow label="STOP-BANG" value={results.stopbang.score} max={8} risk={results.stopbang.risk} />
        <ScoreRow label="Berlin Questionnaire" value={results.berlin.positive_categories} max={3} risk={results.berlin.risk} />
        <ScoreRow label="NoSAS" value={results.nosas.score} max={17} risk={results.nosas.risk} />
        <ScoreRow label="Epworth (ESS)" value={results.ess.score} max={24} risk={results.ess.risk} />
      </div>

      <div>
        <h3 style={{ fontSize: "1.05rem" }}>AI Summary</h3>
        <p>{rag_analysis.overall_interpretation}</p>
        <p>
          <strong>Main risk factors: </strong>
          {rag_analysis.main_risk_factors}
        </p>
      </div>

      <div>
        <h3 style={{ fontSize: "1.05rem" }}>Recommended Next Step</h3>
        <p>{rag_analysis.recommended_next_step}</p>
      </div>

      <div className="banner banner-info">
        <span>ℹ</span>
        <span>{results.disclaimer}</span>
      </div>

      <div style={{ display: "flex", gap: "0.75rem" }}>
        <button className="btn btn-primary" onClick={handlePrint}>
          Download Report
        </button>
        <button className="btn btn-secondary" onClick={onLogout}>
          Logout
        </button>
      </div>
    </div>
  );
}
