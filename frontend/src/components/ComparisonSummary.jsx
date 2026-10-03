import { downloadCsv } from "../utils/csv.js";
import { labelFor } from "../constants/strategies.js";

const topDoc = (item) =>
  item.result?.retrieved_chunks?.[0]?.document_name ?? null;

export default function ComparisonSummary({ data }) {
  const rows = data.results;
  const ok = rows.filter((r) => r.result);
  const maxLatency = Math.max(1, ...ok.map((r) => r.result.latency_ms));
  const fastest = ok.length
    ? ok.reduce((a, b) => (a.result.latency_ms <= b.result.latency_ms ? a : b))
    : null;

  const counts = {};
  ok.forEach((r) => {
    const d = topDoc(r);
    if (d) counts[d] = (counts[d] || 0) + 1;
  });
  const majorityDoc = Object.entries(counts).sort(
    (a, b) => b[1] - a[1],
  )[0]?.[0];

  const exportCsv = () => {
    downloadCsv(
      "strategy-comparison.csv",
      rows.map((r) => ({
        strategy: r.strategy_name,
        chunking: r.chunking_strategy,
        retrieval: r.retrieval_strategy,
        latency_ms: r.result ? Math.round(r.result.latency_ms) : "",
        num_citations: r.result?.citations.length ?? "",
        num_sources: r.result?.retrieved_chunks.length ?? "",
        top_source: topDoc(r) ?? "",
        answer: r.result?.answer ?? "",
        error: r.error ?? "",
      })),
      [
        "strategy",
        "chunking",
        "retrieval",
        "latency_ms",
        "num_citations",
        "num_sources",
        "top_source",
        "answer",
        "error",
      ],
    );
  };

  return (
    <div className="card">
      <div className="summary-head">
        <div>
          <div className="field-label">Comparison</div>
          <div className="muted small">
            {ok.length} of {rows.length} strategies answered ·{" "}
            {(data.total_latency_ms / 1000).toFixed(1)}s total
            {majorityDoc && counts[majorityDoc] > 1 && (
              <>
                {" "}
                · {counts[majorityDoc]} agree on top source <b>{majorityDoc}</b>
              </>
            )}
          </div>
        </div>
        <button type="button" className="btn btn-secondary" onClick={exportCsv}>
          Export CSV
        </button>
      </div>

      <table className="table">
        <thead>
          <tr>
            <th>Strategy</th>
            <th>Latency</th>
            <th>Cited</th>
            <th>Top source</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.strategy_name} className={r.error ? "row-error" : ""}>
              <td>{labelFor(r.chunking_strategy, r.retrieval_strategy)}</td>
              {r.result ? (
                <>
                  <td>
                    <div className="bar-cell">
                      <div
                        className="bar"
                        style={{
                          width: `${(r.result.latency_ms / maxLatency) * 100}%`,
                        }}
                      />
                      <span className="mono small">
                        {(r.result.latency_ms / 1000).toFixed(2)}s
                        {fastest === r && ok.length > 1 && (
                          <span className="badge badge-ok">fastest</span>
                        )}
                      </span>
                    </div>
                  </td>
                  <td>{r.result.citations.length}</td>
                  <td>
                    {topDoc(r)}
                    {topDoc(r) === majorityDoc && counts[majorityDoc] > 1 && (
                      <span className="agree"> ✓</span>
                    )}
                  </td>
                </>
              ) : (
                <td colSpan={3} className="error-text">
                  {r.error}
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
