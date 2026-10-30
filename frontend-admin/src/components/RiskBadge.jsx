const RISK_CLASS = {
  "Low risk": "risk-low",
  "Intermediate risk": "risk-intermediate",
  "High risk": "risk-high",
};

export default function RiskBadge({ risk, label }) {
  const cls = RISK_CLASS[risk] || "risk-unknown";
  return (
    <span className={`risk-badge ${cls}`}>
      {label ? `${label}: ${risk || "N/A"}` : risk || "N/A"}
    </span>
  );
}
