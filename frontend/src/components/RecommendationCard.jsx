import { metricLabel } from "../utils/experimentMeta.js";

const CONFIDENCE = {
  clear: { text: "Clear lead", cls: "badge-ok" },
  narrow: { text: "Narrow lead", cls: "badge-warn" },
  tie: { text: "Tie on wins", cls: "badge-warn" },
  single: { text: "Only one experiment", cls: "" },
};

export default function RecommendationCard({ rec, labelOf, stale }) {
  if (!rec) return null;
  const conf = CONFIDENCE[rec.confidence] ?? CONFIDENCE.single;
  const label = labelOf(rec.name);

  return (
    <div className="card reco" aria-label="Recommended strategy">
      <div>
        <div className="field-label">Recommended strategy</div>
        <div className="reco-title">{label}</div>
        {label !== rec.name && (
          <div className="mono muted small">{rec.name}</div>
        )}

        <p className="reco-summary">{rec.summary}</p>

        {rec.strengths.length > 0 && (
          <div className="chip-row">
            <span className="muted small">Best at</span>
            {rec.strengths.map((m) => (
              <span key={m} className="chip chip-ok">
                ✓ {metricLabel(m)}
              </span>
            ))}
          </div>
        )}
        {rec.weaknesses.length > 0 && (
          <div className="chip-row">
            <span className="muted small">Worst at</span>
            {rec.weaknesses.map((m) => (
              <span key={m} className="chip chip-warn">
                ⚠ {metricLabel(m)}
              </span>
            ))}
          </div>
        )}

        <p className="muted small reco-foot">
          Based on how many metrics each experiment wins. That's a rule of
          thumb, not a verdict: if one metric matters more to you (say,
          hallucinations over speed), read the table below and pick for that.
          {stale &&
            " These results were produced on an older version of the questions."}
        </p>
      </div>

      <div className="reco-side">
        <div className="reco-stat">
          {rec.wins}
          <span className="muted"> / {rec.total_metrics}</span>
        </div>
        <div className="muted small">metrics won</div>
        <span
          className={`badge ${conf.cls}`}
          style={{ marginLeft: 0, marginTop: 8 }}
        >
          {conf.text}
        </span>
        {rec.runner_up && (
          <div className="muted small" style={{ marginTop: 8 }}>
            Next: {labelOf(rec.runner_up.name)} ({rec.runner_up.wins})
          </div>
        )}
      </div>
    </div>
  );
}
