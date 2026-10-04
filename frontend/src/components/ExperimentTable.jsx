import {
  formatMetric,
  metricLabel,
  metricsWon,
  sortMetrics,
} from "../utils/experimentMeta.js";

export default function ExperimentTable({ comparison, labelOf }) {
  const rows = sortMetrics(comparison.metrics);
  const won = metricsWon(comparison);

  return (
    <div className="table-wrap">
      <table className="table cmp-table">
        <thead>
          <tr>
            <th>Metric</th>
            {comparison.experiments.map((n) => (
              <th key={n} title={n}>
                {labelOf(n)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((m) => (
            <tr key={m.metric}>
              <td>
                {metricLabel(m.metric)}{" "}
                <span
                  className="muted small"
                  title={
                    m.direction === "lower"
                      ? "Lower is better"
                      : "Higher is better"
                  }
                >
                  {m.direction === "lower" ? "↓" : "↑"}
                </span>
              </td>
              {comparison.experiments.map((n) => {
                const v = m.values?.[n];
                const best = m.best === n;
                return (
                  <td key={n} className={`mono ${best ? "cell-best" : ""}`}>
                    {formatMetric(m.metric, v)}
                    {best && (
                      <span
                        className="star"
                        title="Best on this metric"
                        aria-label="best"
                      >
                        {" "}
                        ★
                      </span>
                    )}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
        <tfoot>
          <tr>
            <td>Metrics won</td>
            {comparison.experiments.map((n) => (
              <td key={n} className="mono">
                {won[n].length} / {comparison.metrics.length}
              </td>
            ))}
          </tr>
        </tfoot>
      </table>
    </div>
  );
}
