import { useState } from "react";
import { Link } from "react-router-dom";
import { PIPELINE } from "../constants/learn.js";

const ALL_STEPS = PIPELINE.flatMap((lane) =>
  lane.steps.map((s) => ({ ...s, lane: lane.lane })),
);

export default function HowItWorks({ config }) {
  const [activeId, setActiveId] = useState(ALL_STEPS[0].id);
  const idx = ALL_STEPS.findIndex((s) => s.id === activeId);
  const active = ALL_STEPS[idx];

  const fill = (text) =>
    text
      .replace("{fixed}", config?.chunking?.fixed_chunk_size ?? 500)
      .replace("{overlap}", config?.chunking?.fixed_chunk_overlap ?? 50);

  return (
    <div className="card">
      <div className="pipeline">
        {PIPELINE.map((lane, li) => (
          <div key={lane.lane} className="lane">
            <div className="lane-head">
              <span className="lane-num">{li + 1}</span>
              <div>
                <div className="lane-title">{lane.lane}</div>
                <div className="muted small">{lane.laneHint}</div>
              </div>
            </div>
            <div className="lane-steps">
              {lane.steps.map((s, si) => (
                <div key={s.id} className="lane-item">
                  <button
                    type="button"
                    className={`pstep ${s.id === activeId ? "pstep-on" : ""}`}
                    aria-pressed={s.id === activeId}
                    onClick={() => setActiveId(s.id)}
                  >
                    <span className="pstep-title">{s.title}</span>
                    <span className="pstep-short">{s.short}</span>
                  </button>
                  {si < lane.steps.length - 1 && (
                    <span className="parrow" aria-hidden>
                      →
                    </span>
                  )}
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>

      <div className="pdetail" aria-live="polite">
        <div className="pdetail-head">
          <div>
            <div className="field-label">
              {active.lane} · step {idx + 1} of {ALL_STEPS.length}
            </div>
            <h3>{active.title}</h3>
          </div>
          <div className="presets">
            <button
              type="button"
              className="btn btn-ghost"
              disabled={idx === 0}
              onClick={() => setActiveId(ALL_STEPS[idx - 1].id)}
            >
              ← Back
            </button>
            <button
              type="button"
              className="btn btn-secondary"
              disabled={idx === ALL_STEPS.length - 1}
              onClick={() => setActiveId(ALL_STEPS[idx + 1].id)}
            >
              Next →
            </button>
          </div>
        </div>
        {active.detail.map((p) => (
          <p key={p} className="pdetail-text">
            {fill(p)}
          </p>
        ))}
        {active.link && (
          <Link to={active.link.to} className="link">
            {active.link.label} →
          </Link>
        )}
      </div>
    </div>
  );
}
