import { useState } from "react";

export default function RebuildPanel({ index, job, onStart, starting }) {
  const [chunking, setChunking] = useState({ fixed: true, semantic: true });
  const running = job && (job.status === "queued" || job.status === "running");
  const selected = Object.keys(chunking).filter((k) => chunking[k]);
  const pct = Math.round((job?.progress ?? 0) * 100);

  return (
    <div className="card">
      <div className="summary-head">
        <div>
          <div className="field-label">Search index</div>
          <div className="muted small">
            {index.fixed_built
              ? `${index.total_chunks} chunks (fixed)`
              : "Not built yet"}
            {index.semantic_built
              ? " · semantic built"
              : " · semantic not built"}
            {index.last_built &&
              ` · last built ${new Date(index.last_built).toLocaleString()}`}
          </div>
        </div>
        <div className="presets">
          {["fixed", "semantic"].map((c) => (
            <label key={c} className="check">
              <input
                type="checkbox"
                checked={chunking[c]}
                disabled={running}
                onChange={(e) =>
                  setChunking((s) => ({ ...s, [c]: e.target.checked }))
                }
              />
              {c}
            </label>
          ))}
          <button
            type="button"
            className="btn btn-primary"
            disabled={running || starting || selected.length === 0}
            onClick={() => onStart(selected)}
          >
            {running ? "Rebuilding…" : "Rebuild index"}
          </button>
        </div>
      </div>

      {index.stale && !running && (
        <div className="notice notice-warn">
          <b>The index is out of date.</b> {index.reasons.join(" · ")}. Rebuild
          to apply your changes — until then, answers still come from the old
          index.
        </div>
      )}

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
              <span className="error-text">Rebuild failed: {job.error}</span>
            ) : job.status === "succeeded" ? (
              <span className="ok-text">
                Done — {job.result?.documents ?? 0} documents
                {job.result?.chunks &&
                  Object.entries(job.result.chunks).map(
                    ([k, v]) => ` · ${v} ${k} chunks`,
                  )}
              </span>
            ) : (
              `${pct}% · ${job.message || "Starting…"}`
            )}
          </div>
        </div>
      )}
    </div>
  );
}
