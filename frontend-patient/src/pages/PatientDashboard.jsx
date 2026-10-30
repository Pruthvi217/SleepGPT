import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import PatientLogin from "../components/PatientLogin";
import Assessment from "../components/Assessment";
import Results from "../components/Results";
import { Loading, ErrorBanner } from "../components/Feedback";
import { clearSession, getResults, loginPatient } from "../services/api";
import BreathWave from "../components/BreathWave";
import SleepAnalysisPanel from "../components/SleepAnalysisPanel";

const STORAGE_KEY = "sleepgpt_patient_id";

const STAGE = { LOGIN: "login", ASSESSMENT: "assessment", RESULTS: "results" };

export default function PatientDashboard() {
  const [patientId, setPatientId] = useState(() => localStorage.getItem(STORAGE_KEY) || "");
  const [stage, setStage] = useState(patientId ? null : STAGE.LOGIN);
  const [resultsData, setResultsData] = useState(null);
  const [loading, setLoading] = useState(Boolean(patientId));
  const [error, setError] = useState("");

  const resolveStageFor = async (id) => {
    setLoading(true);
    setError("");
    try {
      const info = await loginPatient(id);
      if (!info.assessment_completed) {
        setStage(STAGE.ASSESSMENT);
      } else {
        const results = await getResults(id);
        setResultsData(results);
        setStage(STAGE.RESULTS);
      }
    } catch (err) {
      setError(err.message);
      setStage(STAGE.LOGIN);
      localStorage.removeItem(STORAGE_KEY);
      setPatientId("");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (patientId && stage === null) {
      resolveStageFor(patientId);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleLoggedIn = (id) => {
    localStorage.setItem(STORAGE_KEY, id);
    setPatientId(id);
    resolveStageFor(id);
  };

  const handleAssessmentCompleted = async () => {
    try {
      const results = await getResults(patientId);
      setResultsData(results);
    } catch {
      setResultsData({ completed: true, result_visible: false });
    }
    setStage(STAGE.RESULTS);
  };

  const handleLogout = () => {
    localStorage.removeItem(STORAGE_KEY);
    clearSession();
    setPatientId("");
    setResultsData(null);
    setError("");
    setStage(STAGE.LOGIN);
  };

  return (
    <div className="center-screen">
      <div style={{ width: "100%", maxWidth: 480 }}>
        <div style={{ textAlign: "center", marginBottom: "1.75rem" }}>
          <Link to="/" style={{ textDecoration: "none" }}>
            <span className="mono muted" style={{ fontSize: "0.8rem", letterSpacing: "0.06em" }}>
              SLEEPGPT
            </span>
          </Link>
        </div>

        <div className="card">
          {loading && <Loading label="Loading your account…" />}
          {!loading && error && stage === STAGE.LOGIN && <ErrorBanner message={error} />}

          {!loading && stage === STAGE.LOGIN && (
            <>
              <div style={{ textAlign: "center", marginBottom: "1.5rem" }}>
                <BreathWave />
              </div>
              <PatientLogin onLoggedIn={handleLoggedIn} />
            </>
          )}

          {!loading && stage === STAGE.ASSESSMENT && (
            <Assessment patientId={patientId} onCompleted={handleAssessmentCompleted} />
          )}

          {!loading && stage === STAGE.RESULTS && resultsData && (
            <Results patientId={patientId} data={resultsData} onLogout={handleLogout} />
          )}
        </div>

        {!loading && stage === STAGE.RESULTS && resultsData && <SleepAnalysisPanel patientId={patientId} />}
      </div>
    </div>
  );
}
