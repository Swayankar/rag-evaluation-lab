import { useState } from "react";
import StrategySelector from "./StrategySelector.jsx";
import { EXPERIMENT_KEYS, parseKey } from "../constants/strategies.js";

export default function EvalRunPanel({
  numQuestions,
  job,
  onStart,
  starting,
  onGoQuestions,
}) {
  const [selected, setSelected] = useState(EXPERIMENT_KEYS);
  const [topK, setTopK] = useState(5);
  const [judges, setJudges] = useState(true);

  const running = job && (job.status === "queued" || job.status === "running");
  const callsPerQuestion = judges ? 3 : 1;
  const totalCalls = selected.length * numQuestions * callsPerQuestion;
  const pct = Math.round((job?.progress ?? 0) * 100);
  const canRun =
    selected.length > 0 && numQuestions > 0 && !running && !starting;

  return (
    <div className="page" style={{ gap: 16 }}>
      <StrategySelector
        selected={selected}
        onChange={setSelected}
        disabled={running}
        title="Strategies to evaluate"
        description="Each selected strategy answers every question; results are saved and appear on the Results tab."
      />

      <div className="card">
        <div className="field-label">Options</div>
        <div className="upload-row" style={{ marginBottom: 0 }}>
          <label className="muted small">
            Top-K
            <select
              value={topK}
              onChange={(e) => setTopK(Number(e.target.value))}
              disabled={running}
            >
              {[1, 3, 5, 8, 10].map((k) => (
                <option key={k} value={k}>
                  {k}
                </option>
              ))}
            </select>
          </label>
          <label className="check">
            <input
              type="checkbox"
              checked={judges}
              onChange={(e) => setJudges(e.target.checked)}
              disabled={running}
            />
            Use LLM judges (correctness, relevance, completeness, faithfulness)
          </label>
        </div>

        {numQuestions === 0 ? (
          <div className="notice notice-warn" style={{ marginTop: 12 }}>
            There are no evaluation questions yet.{" "}
            <button type="button" className="link" onClick={onGoQuestions}>
              Add some →
            </button>
          </div>
        ) : (
          <div className="muted small" style={{ marginTop: 12 }}>
            {selected.length} strateg{selected.length === 1 ? "y" : "ies"} ×{" "}
            {numQuestions} question(s) ≈ <b>{totalCalls}</b> Groq calls
            {judges ? " (1 answer + 2 judge calls per question)" : ""}. Runs one
            after another, so a free-tier rate limit can slow it down.
          </div>
        )}

        <div className="run-bar" style={{ marginTop: 14 }}>
          <button
            type="button"
            className="btn btn-primary"
            disabled={!canRun}
            onClick={() =>
              onStart({
                strategies: selected.map(parseKey),
                top_k: topK,
                run_llm_judges: judges,
              })
            }
          >
            {running ? "Running…" : `Run evaluation (${selected.length})`}
          </button>
        </div>

        {job && (
          <div className="progress-wrap">
            <div className="progress">
              <div
                className={`progress-bar ${job.status === "failed" ? "progress-failed" : ""}`}
                style={{ width: `${pct}%` }}
              />
            </div>
            <div className="small muted">
              {job.status === "failed" ? (
                <span className="error-text">
                  Evaluation failed: {job.error}
                </span>
              ) : job.status === "succeeded" ? (
                <span className="ok-text">
                  Finished — {job.result?.ran?.length ?? 0} strategy run(s)
                  saved.
                </span>
              ) : (
                `${pct}% · ${job.message || "Starting…"}`
              )}
            </div>
            {job.status === "succeeded" &&
              Object.entries(job.result?.skipped ?? {}).map(([name, why]) => (
                <div
                  key={name}
                  className="notice notice-warn"
                  style={{ marginTop: 8 }}
                >
                  <b>{name}</b> was skipped: {why}
                </div>
              ))}
          </div>
        )}
      </div>
    </div>
  );
}
