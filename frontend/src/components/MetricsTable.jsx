import { Fragment, useState } from "react";
import { QUESTION_METRICS as Q } from "../constants/metrics.js";

const fmt = (v, digits = 2) =>
  v === null || v === undefined ? "—" : Number(v).toFixed(digits);

export default function MetricsTable({ results }) {
  const [open, setOpen] = useState(null);

  return (
    <div className="card" style={{ overflowX: "auto" }}>
      <div className="field-label" style={{ marginBottom: 8 }}>
        Per-question results
      </div>
      <table className="table">
        <thead>
          <tr>
            <th>Question</th>
            <th>Recall</th>
            <th>Prec.</th>
            <th>MRR</th>
            <th>Cite</th>
            <th>Correct</th>
            <th>Faithful</th>
            <th>Latency</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {results.map((r) => {
            const isOpen = open === r.question_id;
            const flagged = r.grounding_judge?.likely_hallucination;
            return (
              <Fragment key={r.question_id}>
                <tr
                  className={`clickable ${r.error ? "row-error" : ""}`}
                  onClick={() => setOpen(isOpen ? null : r.question_id)}
                >
                  <td>
                    <span className="badge">{r.question_id}</span> {r.question}
                  </td>
                  {r.error ? (
                    <td colSpan={7} className="error-text">
                      ❌ Generation failed: {r.error}
                    </td>
                  ) : (
                    <>
                      <td className="mono">{fmt(Q.recall.get(r))}</td>
                      <td className="mono">{fmt(Q.precision.get(r))}</td>
                      <td className="mono">{fmt(Q.mrr.get(r))}</td>
                      <td className="mono">{fmt(Q.citation.get(r))}</td>
                      <td className="mono">{fmt(Q.correctness.get(r), 0)}</td>
                      <td className="mono">
                        {fmt(Q.faithfulness.get(r), 0)}
                        {flagged && (
                          <span title="Judge flagged a possible hallucination">
                            {" "}
                            ⚠
                          </span>
                        )}
                      </td>
                      <td className="mono">
                        {r.system
                          ? `${Math.round(r.system.latency_ms)} ms`
                          : "—"}
                      </td>
                    </>
                  )}
                  <td>{isOpen ? "▾" : "▸"}</td>
                </tr>
                {isOpen && (
                  <tr>
                    <td colSpan={9} className="detail-cell">
                      {r.answer && (
                        <>
                          <div className="field-label">Answer</div>
                          <p className="answer-text" style={{ marginTop: 4 }}>
                            {r.answer}
                          </p>
                        </>
                      )}
                      {r.answer_judge?.rationale && (
                        <p className="small muted">
                          <b>Answer judge:</b> {r.answer_judge.rationale}
                        </p>
                      )}
                      {r.grounding_judge?.rationale && (
                        <p className="small muted">
                          <b>Grounding judge:</b> {r.grounding_judge.rationale}
                        </p>
                      )}
                      {r.citation && (
                        <p className="small muted">
                          <b>Citations:</b> {r.citation.num_citations} used
                          {r.citation.citation_accuracy === null &&
                          r.citation.num_citations === 0
                            ? " (accuracy undefined)"
                            : ""}
                        </p>
                      )}
                      {r.judge_error && (
                        <p className="small error-text">
                          Judge error: {r.judge_error}
                        </p>
                      )}
                    </td>
                  </tr>
                )}
              </Fragment>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
