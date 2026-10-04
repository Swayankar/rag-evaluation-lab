import { useState } from "react";
import { describeExperiments } from "../utils/experimentMeta.js";

export default function ExperimentRunPanel({
  configs,
  numQuestions,
  job,
  onStart,
  starting,
  onGoSetup,
  onGoQuestions,
  hasComparison,
}) {
  const [judges, setJudges] = useState(true);
  const running = job && (job.status === "queued" || job.status === "running");
  const meta = describeExperiments(
    configs.map((c) => c.name),
    configs,
  );
  const calls = configs.length * numQuestions * (judges ? 3 : 1);
  const pct = Math.round((job?.progress ?? 0) * 100);
  const canRun =
    configs.length > 0 && numQuestions > 0 && !running && !starting;

  return (
    <div className="card">
      <div className="field-label">Run all experiments</div>
      <div className="muted small" style={{ marginBottom: 10 }}>
        Every experiment answers every evaluation question; the results are
        compared and the comparison is saved. The same thing{" "}
        <span className="mono">scripts/compare_experiments.py</span> does, with
        progress.
      </div>

      <div className="chip-row" style={{ marginBottom: 6 }}>
        {configs.map((c) => (
          <span key={c.name} className="chip" title={c.name}>
            {meta.get(c.name)?.label ?? c.name}
          </span>
        ))}
        <button type="button" className="link" onClick={onGoSetup}>
          Edit experiments
        </button>
      </div>

      <div className="upload-row" style={{ marginBottom: 0 }}>
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
          {configs.length} experiment(s) × {numQuestions} question(s) ≈{" "}
          <b>{calls}</b> Groq calls
          {judges ? " (1 answer + 2 judge calls per question)" : ""}. They run
          one after another, so a free-tier rate limit can slow this down.
          {hasComparison && " This replaces the current comparison."}
        </div>
      )}

      <div className="run-bar" style={{ marginTop: 14 }}>
        <button
          type="button"
          className="btn btn-primary"
          disabled={!canRun}
          onClick={() => onStart({ run_llm_judges: judges })}
        >
          {running
            ? "Running…"
            : `Run ${configs.length} experiment${configs.length === 1 ? "" : "s"}`}
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
              <span className="error-text">Run failed: {job.error}</span>
            ) : job.status === "succeeded" ? (
              <span className="ok-text">
                Finished — {job.result?.ran?.length ?? 0} experiment(s)
                compared.
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
  );
}
