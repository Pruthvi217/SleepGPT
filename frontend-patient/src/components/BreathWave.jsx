/**
 * BreathWave — the app's one recurring signature: a respiration-style
 * sine trace. Used as a quiet divider on the patient side and as a
 * mini "readout" accent under score numbers on the admin side.
 */
export default function BreathWave({ width = 240, height = 28, color = "var(--teal-500)", opacity = 0.55 }) {
  const points = [];
  const cycles = 3;
  const steps = 80;
  for (let i = 0; i <= steps; i++) {
    const x = (i / steps) * width;
    const t = (i / steps) * cycles * Math.PI * 2;
    const y = height / 2 + Math.sin(t) * (height / 2 - 3) * Math.exp(-((i / steps - 0.5) ** 2) * 0.5);
    points.push(`${x.toFixed(1)},${y.toFixed(1)}`);
  }
  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} aria-hidden="true" style={{ display: "block" }}>
      <polyline points={points.join(" ")} fill="none" stroke={color} strokeWidth="1.75" strokeLinecap="round" opacity={opacity} />
    </svg>
  );
}
