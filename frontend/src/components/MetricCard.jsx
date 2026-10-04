import { METRICS, formatMetric } from "../constants/metrics.js";

export default function MetricCard({ metric, value }) {
  const def = METRICS[metric];
  const missing = value === null || value === undefined;
  const fraction = missing
    ? 0
    : def.scale === "five"
      ? (value - 1) / 4
      : def.scale === "unit"
        ? value
        : null;

  return (
    <div className="metric-card" title={def.hint}>
      <div className="metric-label">
        {def.label}
        {def.lower && <span className="muted small"> · lower is better</span>}
      </div>
      <div className="metric-value">
        {formatMetric(metric, value)}
        {!missing && def.scale === "five" && (
          <span className="muted small"> / 5</span>
        )}
      </div>
      {fraction !== null && (
        <div className="metric-bar">
          <div
            className="metric-bar-fill"
            style={{ width: `${Math.max(0, Math.min(1, fraction)) * 100}%` }}
          />
        </div>
      )}
      {missing && <div className="muted small">not recorded</div>}
    </div>
  );
}
