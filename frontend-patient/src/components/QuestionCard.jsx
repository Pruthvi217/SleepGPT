import { useState } from "react";

export default function QuestionCard({ question, onSubmit, submitting }) {
  const [value, setValue] = useState("");
  const [touched, setTouched] = useState(false);

  const handleSubmit = (e) => {
    e.preventDefault();
    setTouched(true);
    if (value === "" || value === null || value === undefined) return;
    onSubmit(value);
    setValue("");
    setTouched(false);
  };

  const isEmpty = value === "" || value === null || value === undefined;

  return (
    <form onSubmit={handleSubmit}>
      <h2 style={{ fontSize: "1.4rem", marginBottom: "1.4rem" }}>{question.question}</h2>

      {question.type === "yes_no" && (
        <div className="stack" style={{ flexDirection: "row", gap: "0.75rem", marginBottom: "1.4rem" }}>
          {["Yes", "No"].map((opt) => (
            <button
              key={opt}
              type="button"
              className={value === opt ? "btn btn-primary" : "btn btn-secondary"}
              style={{ flex: 1 }}
              onClick={() => setValue(opt)}
            >
              {opt}
            </button>
          ))}
        </div>
      )}

      {(question.type === "choice" || question.type === "scale") && (
        <div className="stack" style={{ marginBottom: "1.4rem" }}>
          {question.options.map((opt) => (
            <button
              key={opt}
              type="button"
              className={value === opt ? "btn btn-primary btn-block" : "btn btn-secondary btn-block"}
              style={{ justifyContent: "flex-start", textAlign: "left" }}
              onClick={() => setValue(opt)}
            >
              {opt}
            </button>
          ))}
        </div>
      )}

      {question.type === "number" && (
        <div className="field" style={{ marginBottom: "1.4rem" }}>
          <label htmlFor="q-number">
            Enter a value{question.unit ? ` (${question.unit})` : ""}
          </label>
          <input
            id="q-number"
            type="number"
            autoFocus
            value={value}
            min={question.min}
            max={question.max}
            onChange={(e) => setValue(e.target.value)}
          />
          {(question.min !== undefined || question.max !== undefined) && (
            <span className="field-hint">
              Valid range: {question.min ?? "–"} to {question.max ?? "–"}
            </span>
          )}
        </div>
      )}

      {(question.type === "text" || question.type === "time") && (
        <div className="field" style={{ marginBottom: "1.4rem" }}>
          <label htmlFor="q-text">Your answer</label>
          <input
            id="q-text"
            type={question.type === "time" ? "time" : "text"}
            autoFocus
            value={value}
            onChange={(e) => setValue(e.target.value)}
          />
        </div>
      )}

      {touched && isEmpty && <p className="field-error">Please answer to continue.</p>}

      <button type="submit" className="btn btn-primary btn-block" disabled={submitting}>
        {submitting ? "Saving…" : "Continue →"}
      </button>
    </form>
  );
}
