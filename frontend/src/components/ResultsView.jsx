import { useEffect, useMemo, useState } from "react";
import EvaluationChart from "../charts/EvaluationChart.jsx";
import QuestionHeatmap from "./QuestionHeatmap.jsx";
import { api } from "../services/api.js";
import { downloadCsv } from "../utils/csv.js";
import {
  AGGREGATE_COLUMNS,
  CHART_GROUPS,
  TILE_METRICS,
  bestBy,
  chartRows,
  isNum,
  prettyName,
} from "../utils/evalMetrics.js";

export default function ResultsView({ results, onDelete, onGoRun }) {
  const [excluded, setExcluded] = useState(() => new Set());
  const [details, setDetails] = useState({});
  const [error, setError] = useState(null);

  const selected = useMemo(
    () => results.filter((r) => !excluded.has(r.name)),
    [results, excluded],
  );
  const rows = useMemo(() => chartRows(selected), [selected]);

  useEffect(() => {
    let cancelled = false;
    selected.forEach((r) => {
      const stamp = details[r.name]?._modified;
      if (stamp === r.modified) return;
      api
        .evalResult(r.name)
        .then(
          (d) =>
            !cancelled &&
            setDetails((prev) => ({
              ...prev,
              [r.name]: { ...d, _modified: r.modified },
            })),
        )
        .catch((e) => !cancelled && setError(e.message));
    });
    return () => {
      cancelled = true;
    };
  }, [selected]);

  const toggle = (name) =>
    setExcluded((prev) => {
      const next = new Set(prev);
      next.has(name) ? next.delete(name) : next.add(name);
      return next;
    });

  if (results.length === 0) {
    return (
      <div className="card empty">
        <h3>No evaluation results yet</h3>
        <p className="muted">
          Run an evaluation to see charts comparing your strategies.
        </p>
        <button
          type="button"
          className="btn btn-primary"
          onClick={onGoRun}
          style={{ marginTop: 12 }}
        >
          Run an evaluation
        </button>
      </div>
    );
  }

  const fallbackRuns = selected.filter(
    (r) => r.meta?.embedder === "HashingEmbedder",
  );
  const noopRerank = selected.filter(
    (r) => r.meta?.reranker === "NoOpReranker",
  );
  const stale = selected.filter((r) => r.dataset_match === false);

  const exportSummary = () =>
    downloadCsv(
      "evaluation-summary.csv",
      selected.map((r) => ({
        strategy: r.name,
        chunking: r.chunking,
        retrieval: r.retrieval,
        top_k: r.meta?.top_k,
        embedder: r.meta?.embedder,
        reranker: r.meta?.reranker,
        llm_judges: r.meta?.llm_judges,
        ran_at: r.meta?.ran_at ?? r.modified,
        ...r.aggregate,
      })),
      [
        "strategy",
        "chunking",
        "retrieval",
        "top_k",
        "embedder",
        "reranker",
        "llm_judges",
        "ran_at",
        ...AGGREGATE_COLUMNS,
      ],
    );

  const exportPerQuestion = () => {
    const out = [];
    selected.forEach((r) => {
      (details[r.name]?.results ?? []).forEach((q) =>
        out.push({
          strategy: r.name,
          question_id: q.question_id,
          question: q.question,
          recall_at_k: q.retrieval?.recall_at_k,
          precision_at_k: q.retrieval?.precision_at_k,
          mrr: q.retrieval?.mrr,
          citation_accuracy: q.citation?.citation_accuracy,
          num_citations: q.citation?.num_citations,
          correctness: q.answer_judge?.correctness,
          relevance: q.answer_judge?.relevance,
          completeness: q.answer_judge?.completeness,
          faithfulness: q.grounding_judge?.faithfulness,
          likely_hallucination: q.grounding_judge?.likely_hallucination,
          latency_ms: q.system?.latency_ms,
          answer: q.answer,
          error: q.error ?? q.judge_error,
        }),
      );
    });
    downloadCsv("evaluation-per-question.csv", out, [
      "strategy",
      "question_id",
      "question",
      "recall_at_k",
      "precision_at_k",
      "mrr",
      "citation_accuracy",
      "num_citations",
      "correctness",
      "relevance",
      "completeness",
      "faithfulness",
      "likely_hallucination",
      "latency_ms",
      "answer",
      "error",
    ]);
  };

  return (
    <div className="page" style={{ gap: 16 }}>
      {fallbackRuns.length > 0 && (
        <div className="notice notice-warn">
          ⚠ {fallbackRuns.map((r) => prettyName(r.name)).join(", ")} used the{" "}
          <b>HashingEmbedder fallback</b>, not real embeddings, so those
          retrieval scores don't reflect real semantic search quality.
        </div>
      )}
      {noopRerank.length > 0 && (
        <div className="notice notice-warn">
          ⚠ {noopRerank.map((r) => prettyName(r.name)).join(", ")} ran with the
          no-op reranker fallback, so it behaved like plain hybrid.
        </div>
      )}
      {stale.length > 0 && (
        <div className="notice notice-warn">
          ⚠ {stale.map((r) => prettyName(r.name)).join(", ")} ran on an{" "}
          <b>older version of the questions</b>. Comparing them with newer runs
          isn't apples to apples — re-run them.
        </div>
      )}
      {error && <div className="notice notice-error">{error}</div>}

      <div className="tiles">
        {TILE_METRICS.map((m) => {
          const best = bestBy(rows, m.key, m.direction);
          if (!best) return null;
          return (
            <div key={m.key} className="tile">
              <div className="tile-label">{m.label}</div>
              <div className="tile-value">
                {best[m.key].toFixed(m.decimals)}
                <span className="muted small">{m.suffix}</span>
              </div>
              <div className="tile-sub">{prettyName(best.name)}</div>
            </div>
          );
        })}
      </div>

      <div className="chart-grid">
        {CHART_GROUPS.map((g) => (
          <EvaluationChart
            key={g.id}
            title={g.title}
            subtitle={g.subtitle}
            rows={rows}
            series={g.series}
            domain={g.domain}
            decimals={g.decimals}
          />
        ))}
      </div>

      <QuestionHeatmap names={selected.map((r) => r.name)} details={details} />

      <div className="card">
        <div className="summary-head">
          <div>
            <div className="field-label">Saved runs</div>
            <div className="muted small">
              Untick a run to hide it from the charts. {selected.length} of{" "}
              {results.length} shown.
            </div>
          </div>
          <div className="presets">
            <button
              type="button"
              className="btn btn-secondary"
              onClick={exportSummary}
            >
              Export summary CSV
            </button>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={exportPerQuestion}
              disabled={selected.some((r) => !details[r.name])}
            >
              Export per-question CSV
            </button>
          </div>
        </div>
        <div className="table-wrap">
          <table className="table runs-table">
            <thead>
              <tr>
                <th />
                <th>Strategy</th>
                <th>Ran</th>
                <th>Top-K</th>
                <th>Questions</th>
                <th>Embedder</th>
                <th>Judges</th>
                <th>Notes</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {results.map((r) => (
                <tr key={r.name}>
                  <td>
                    <input
                      type="checkbox"
                      checked={!excluded.has(r.name)}
                      onChange={() => toggle(r.name)}
                      aria-label={`Show ${r.name}`}
                    />
                  </td>
                  <td>{prettyName(r.name)}</td>
                  <td className="muted small">
                    {new Date(r.meta?.ran_at ?? r.modified).toLocaleString()}
                  </td>
                  <td className="mono">{r.meta?.top_k ?? "—"}</td>
                  <td className="mono">{r.aggregate?.num_questions ?? "—"}</td>
                  <td className="mono small">{r.meta?.embedder ?? "—"}</td>
                  <td>{r.meta ? (r.meta.llm_judges ? "on" : "off") : "—"}</td>
                  <td>
                    {r.dataset_match === false && (
                      <span className="warn-text">older questions </span>
                    )}
                    {isNum(r.aggregate?.num_errors) &&
                      r.aggregate.num_errors > 0 && (
                        <span className="warn-text">
                          {r.aggregate.num_errors} failed{" "}
                        </span>
                      )}
                    {r.meta?.embedder === "HashingEmbedder" && (
                      <span className="warn-text">hashing fallback</span>
                    )}
                  </td>
                  <td>
                    <button
                      type="button"
                      className="icon-btn"
                      title="Delete this saved run"
                      onClick={() =>
                        window.confirm(
                          `Delete the saved run for ${prettyName(r.name)}?`,
                        ) && onDelete(r.name)
                      }
                    >
                      🗑
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
