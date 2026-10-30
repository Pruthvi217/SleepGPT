import { useState } from "react";
import RiskBadge from "./RiskBadge";
import { releaseResults } from "../services/api";
import MlAnalysisSection from "./MlAnalysisSection";

function DataRow({ label, value }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", padding: "0.6rem 0", borderBottom: "1px solid var(--ink-700)" }}>
      <span style={{ color: "var(--slate-400)", fontSize: "0.88rem" }}>{label}</span>
      <span className="mono" style={{ color: "#fff", fontSize: "0.88rem", textAlign: "right", maxWidth: "60%" }}>
        {String(value ?? "–")}
      </span>
    </div>
  );
}

function Section({ title, children }) {
  return (
    <div style={{ marginBottom: "1.75rem" }}>
      <h3 style={{ color: "#fff", fontSize: "0.95rem", letterSpacing: "0.04em", textTransform: "uppercase", marginBottom: "0.75rem" }}>
        {title}
      </h3>
      {children}
    </div>
  );
}

export default function AdminPatientResults({ patient, onReleased }) {
  const [releasing, setReleasing] = useState(false);
  const [error, setError] = useState("");

  const handleRelease = async () => {
    setReleasing(true);
    setError("");
    try {
      await releaseResults(patient.patient_id);
      onReleased();
    } catch (err) {
      setError(err.message);
    } finally {
      setReleasing(false);
    }
  };

  const { results, rag_analysis, summary, answers } = patient;

  return (
    <div>
      <Section title="Patient Information">
        <DataRow label="Username" value={patient.username} />
        <DataRow label="Patient ID" value={patient.patient_id} />
        <DataRow
          label="Assessment Status"
          value={patient.assessment_completed ? "Completed" : "In progress"}
        />
      </Section>

      <MlAnalysisSection latest={patient.ml_latest} history={patient.ml_history} patientId={patient.patient_id} />

      {patient.assessment_completed ? (
        <>
          <Section title="Questionnaire Results">
            <DataRow label="BMI" value={results.bmi} />
            <DataRow label="STOP-BANG" value={`${results.stopbang.score} / 8 — ${results.stopbang.risk}`} />
            <DataRow label="Berlin" value={`${results.berlin.positive_categories} / 3 — ${results.berlin.risk}`} />
            <DataRow label="NoSAS" value={`${results.nosas.score} / 17 — ${results.nosas.risk}`} />
            <DataRow label="ESS" value={`${results.ess.score} / 24 — ${results.ess.risk}`} />
            <div style={{ marginTop: "1rem" }}>
              <RiskBadge risk={results.overall_risk} label="Overall risk" />
            </div>
          </Section>

          <Section title="Patient Answers">
            <div style={{ maxHeight: 220, overflowY: "auto" }}>
              {Object.entries(answers)
                .sort((a, b) => Number(a[0]) - Number(b[0]))
                .map(([qid, val]) => (
                  <DataRow key={qid} label={`Q${qid}`} value={String(val)} />
                ))}
            </div>
          </Section>

          <Section title="AI / RAG Analysis">
            <p style={{ color: "var(--slate-400)", fontSize: "0.9rem" }}>
              {rag_analysis.overall_interpretation}
            </p>
            <p style={{ color: "var(--slate-400)", fontSize: "0.9rem" }}>
              <strong style={{ color: "#fff" }}>Risk factors: </strong>
              {rag_analysis.main_risk_factors}
            </p>
            <p style={{ color: "var(--slate-400)", fontSize: "0.9rem" }}>
              <strong style={{ color: "#fff" }}>Concerns: </strong>
              {rag_analysis.questionnaire_concerns}
            </p>
            {rag_analysis.possible_contributing_factors && (
              <p style={{ color: "var(--slate-400)", fontSize: "0.9rem" }}>
                <strong style={{ color: "#fff" }}>Possible contributing factors: </strong>
                {rag_analysis.possible_contributing_factors}
              </p>
            )}
            {rag_analysis.preventive_measures && (
              <p style={{ color: "var(--slate-400)", fontSize: "0.9rem" }}>
                <strong style={{ color: "#fff" }}>Preventive measures: </strong>
                {rag_analysis.preventive_measures}
              </p>
            )}
            <p style={{ color: "var(--slate-400)", fontSize: "0.9rem" }}>
              <strong style={{ color: "#fff" }}>Next step: </strong>
              {rag_analysis.recommended_next_step}
            </p>
            <p className="mono" style={{ color: "var(--teal-500)", fontSize: "0.75rem" }}>
              Source: {
                rag_analysis.generation_method === "rag_llm"
                  ? "Knowledge-base RAG + LLM"
                  : rag_analysis.knowledge_base_used
                  ? "Rule-based fallback (knowledge base retrieved, but Ollama/LLM was unavailable)"
                  : "Rule-based fallback (no relevant knowledge-base documents retrieved)"
              }
            </p>
            {rag_analysis.sources && rag_analysis.sources.length > 0 && (
              <p className="mono" style={{ color: "var(--slate-400)", fontSize: "0.72rem", marginTop: "0.4rem" }}>
                Cited: {rag_analysis.sources.join(", ")}
              </p>
            )}
          </Section>

          <Section title="Patient Summary">
            <p style={{ color: "var(--slate-400)", fontSize: "0.9rem" }}>{summary?.ai_summary}</p>
          </Section>

          <Section title="Result Visibility">
            {error && <p className="field-error">{error}</p>}
            <div style={{ display: "flex", alignItems: "center", gap: "1rem" }}>
              <span
                className="mono"
                style={{
                  fontSize: "0.8rem",
                  color: patient.result_visible ? "var(--sage-600)" : "var(--amber-600)",
                }}
              >
                ● {patient.result_visible ? "Visible to Patient" : "Hidden from Patient"}
              </span>
              {!patient.result_visible && (
                <button className="btn btn-primary" onClick={handleRelease} disabled={releasing}>
                  {releasing ? "Releasing…" : "Show Results to Patient"}
                </button>
              )}
            </div>
          </Section>

          <Section title="Future Sensor Data">
            <div style={{ display: "flex", gap: "0.6rem", flexWrap: "wrap" }}>
              {["SpO₂", "Heart Rate", "Respiration", "Snoring", "Airflow", "Body Position"].map((s) => (
                <span
                  key={s}
                  className="mono"
                  style={{
                    fontSize: "0.75rem",
                    padding: "0.3rem 0.6rem",
                    borderRadius: 6,
                    border: "1px solid var(--ink-700)",
                    color: "var(--slate-400)",
                  }}
                >
                  {s}
                </span>
              ))}
            </div>
            <p style={{ color: "var(--slate-400)", fontSize: "0.85rem", marginTop: "0.6rem" }}>
              Currently unavailable — no cloud sensor is connected for this patient.
            </p>
          </Section>
        </>
      ) : (
        <p style={{ color: "var(--slate-400)" }}>
          This patient has not yet completed their assessment.
        </p>
      )}
    </div>
  );
}
