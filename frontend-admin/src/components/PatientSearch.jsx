import { useState } from "react";

export default function PatientSearch({ onSearch, loading }) {
  const [value, setValue] = useState("");

  const handleSubmit = (e) => {
    e.preventDefault();
    if (value.trim()) onSearch(value.trim());
  };

  return (
    <form onSubmit={handleSubmit} style={{ display: "flex", gap: "0.6rem" }}>
      <input
        value={value}
        onChange={(e) => setValue(e.target.value)}
        placeholder="Enter Patient ID (SGP-XXXXXX)"
        style={{
          flex: 1,
          padding: "0.7em 0.9em",
          borderRadius: "var(--radius-sm)",
          border: "1.5px solid var(--line)",
          fontFamily: "var(--font-mono)",
        }}
      />
      <button type="submit" className="btn btn-primary" disabled={loading}>
        {loading ? "Searching…" : "Search"}
      </button>
    </form>
  );
}
