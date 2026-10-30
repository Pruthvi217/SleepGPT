import { useEffect, useState } from "react";
import { startAssessment, submitAnswer } from "../services/api";
import QuestionCard from "./QuestionCard";
import ProgressBar from "./ProgressBar";
import { Loading, ErrorBanner } from "./Feedback";

export default function Assessment({ patientId, onCompleted }) {
  const [question, setQuestion] = useState(null);
  const [progress, setProgress] = useState({ answered: 0, estimated_total: 35 });
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  const loadNext = async () => {
    setError("");
    setLoading(true);
    try {
      const data = await startAssessment(patientId);
      if (data.completed) {
        onCompleted();
        return;
      }
      setQuestion(data.next_question);
      setProgress(data.progress || progress);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadNext();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [patientId]);

  const handleAnswer = async (value) => {
    setSubmitting(true);
    setError("");
    try {
      const result = await submitAnswer(patientId, question.id, value);
      if (result.completed) {
        onCompleted();
        return;
      }
      setQuestion(result.next_question);
      setProgress(result.progress || progress);
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: "0.6rem" }}>
        <span className="muted" style={{ fontSize: "0.85rem", fontWeight: 600, letterSpacing: "0.02em" }}>
          SLEEP APNEA SCREENING
        </span>
        <span className="mono muted" style={{ fontSize: "0.8rem" }}>
          {progress.answered} of ~{progress.estimated_total}
        </span>
      </div>
      <ProgressBar answered={progress.answered} total={progress.estimated_total} />

      <div style={{ marginTop: "1.6rem" }}>
        <ErrorBanner message={error} onRetry={loadNext} />
        {loading && <Loading label="Loading your next question…" />}
        {!loading && question && (
          <QuestionCard key={question.id} question={question} onSubmit={handleAnswer} submitting={submitting} />
        )}
      </div>
    </div>
  );
}
