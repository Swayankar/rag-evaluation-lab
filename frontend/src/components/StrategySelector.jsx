import {
  ALL_KEYS,
  CHUNKING,
  EXPERIMENT_KEYS,
  RETRIEVAL,
  keyOf,
} from "../constants/strategies.js";

export default function StrategySelector({
  selected,
  onChange,
  disabled,
  title = "Strategies to run",
  description = "Pick one for a normal answer, or several to compare them side by side.",
}) {
  const toggle = (key) => {
    const next = selected.includes(key)
      ? selected.filter((k) => k !== key)
      : [...selected, key];
    onChange(next);
  };

  return (
    <div className="card strategy-selector">
      <div className="strategy-head">
        <div>
          <div className="field-label">{title}</div>
          <div className="muted small">{description}</div>
        </div>
        <div className="presets">
          <button
            type="button"
            className="chip chip-ghost"
            onClick={() => onChange(EXPERIMENT_KEYS)}
            disabled={disabled}
          >
            5 experiments
          </button>
          <button
            type="button"
            className="chip chip-ghost"
            onClick={() => onChange(ALL_KEYS)}
            disabled={disabled}
          >
            All 8
          </button>
          <button
            type="button"
            className="chip chip-ghost"
            onClick={() => onChange([])}
            disabled={disabled}
          >
            Clear
          </button>
        </div>
      </div>

      <div className="strategy-grid">
        <div />
        {RETRIEVAL.map((r) => (
          <div key={r.id} className="grid-col-head" title={r.hint}>
            {r.label}
          </div>
        ))}
        {CHUNKING.map((c) => (
          <Row
            key={c.id}
            chunk={c}
            selected={selected}
            toggle={toggle}
            disabled={disabled}
          />
        ))}
      </div>
    </div>
  );
}

function Row({ chunk, selected, toggle, disabled }) {
  return (
    <>
      <div className="grid-row-head" title={chunk.hint}>
        {chunk.label}
        <span className="muted small">chunking</span>
      </div>
      {RETRIEVAL.map((r) => {
        const key = keyOf(chunk.id, r.id);
        const on = selected.includes(key);
        return (
          <button
            key={key}
            type="button"
            className={`cell ${on ? "cell-on" : ""}`}
            onClick={() => toggle(key)}
            disabled={disabled}
            aria-pressed={on}
          >
            {on ? "✓" : ""}
          </button>
        );
      })}
    </>
  );
}
