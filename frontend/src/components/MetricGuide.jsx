import { CAVEATS, METRIC_GROUPS } from "../constants/learn.js";

export default function MetricGuide() {
  return (
    <div className="page" style={{ gap: 16 }}>
      <div className="info-grid info-grid-2">
        {METRIC_GROUPS.map((g) => (
          <div key={g.title} className="card info-card">
            <h3>{g.title}</h3>
            <p className="muted small">{g.blurb}</p>
            <dl className="metric-list">
              {g.metrics.map((m) => (
                <div key={m.name} className="metric-item">
                  <dt>
                    {m.name} <span className="badge">{m.scale}</span>
                  </dt>
                  <dd className="muted">{m.text}</dd>
                </div>
              ))}
            </dl>
          </div>
        ))}
      </div>

      <div className="card">
        <div className="field-label">Reading the results honestly</div>
        <ul className="caveats">
          {CAVEATS.map((c) => (
            <li key={c}>{c}</li>
          ))}
        </ul>
      </div>
    </div>
  );
}
