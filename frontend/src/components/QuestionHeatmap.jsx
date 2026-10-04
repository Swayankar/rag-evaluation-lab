import { useMemo, useState } from "react";
import { HEAT_METRICS, isNum, prettyName } from "../utils/evalMetrics.js";

const RAMP = [
  "#0d366b",
  "#104281",
  "#184f95",
  "#1c5cab",
  "#256abf",
  "#2a78d6",
  "#3987e5",
  "#5598e7",
  "#6da7ec",
  "#86b6ef",
];

function colorFor(value, [min, max]) {
  const t = Math.max(0, Math.min(1, (value - min) / (max - min || 1)));
  const idx = Math.round(t * (RAMP.length - 1));
  return { bg: RAMP[idx], fg: idx >= 6 ? "#0b0b0b" : "#ffffff" };
}

export default function QuestionHeatmap({
  names,
  details,
  labelOf = prettyName,
}) {
  const [metricId, setMetricId] = useState("correctness");
  const [hardestFirst, setHardestFirst] = useState(true);
  const metric = HEAT_METRICS.find((m) => m.id === metricId);

  const { rows, loaded } = useMemo(() => {
    const loadedNames = names.filter((n) => details[n]);
    const byQuestion = new Map();
    loadedNames.forEach((name) => {
      (details[name].results ?? []).forEach((r) => {
        if (!byQuestion.has(r.question_id))
          byQuestion.set(r.question_id, {
            id: r.question_id,
            question: r.question,
            cells: {},
          });
        byQuestion.get(r.question_id).cells[name] = r.error
          ? { error: r.error }
          : { value: metric.pick(r), r };
      });
    });
    const list = [...byQuestion.values()].map((q) => {
      const vals = Object.values(q.cells)
        .map((c) => c.value)
        .filter(isNum);
      return {
        ...q,
        avg: vals.length ? vals.reduce((a, b) => a + b, 0) / vals.length : null,
      };
    });
    if (hardestFirst)
      list.sort((a, b) => (a.avg ?? Infinity) - (b.avg ?? Infinity));
    return { rows: list, loaded: loadedNames };
  }, [names, details, metric, hardestFirst]);

  if (names.length === 0) return null;

  return (
    <div className="card">
      <div className="chart-head">
        <div>
          <div className="chart-title">Per-question results</div>
          <div className="muted small">
            Spot the questions that trip strategies up. Hover a cell for the
            judge's rationale.
          </div>
        </div>
        <div className="presets">
          <select
            value={metricId}
            onChange={(e) => setMetricId(e.target.value)}
            aria-label="Metric"
          >
            {HEAT_METRICS.map((m) => (
              <option key={m.id} value={m.id}>
                {m.label}
              </option>
            ))}
          </select>
          <label className="check">
            <input
              type="checkbox"
              checked={hardestFirst}
              onChange={(e) => setHardestFirst(e.target.checked)}
            />
            Hardest first
          </label>
        </div>
      </div>

      {loaded.length < names.length && (
        <div className="muted small">Loading per-question detail…</div>
      )}

      <div className="table-wrap">
        <table className="heat">
          <thead>
            <tr>
              <th className="q">Question</th>
              {loaded.map((n) => (
                <th key={n}>{labelOf(n)}</th>
              ))}
              <th>Avg</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((q) => (
              <tr key={q.id}>
                <td className="q" title={q.question}>
                  <span className="mono muted small">{q.id}</span>{" "}
                  {q.question.length > 64
                    ? q.question.slice(0, 64) + "…"
                    : q.question}
                </td>
                {loaded.map((n) => {
                  const c = q.cells[n];
                  if (!c)
                    return (
                      <td key={n} className="cell-none">
                        —
                      </td>
                    );
                  if (c.error)
                    return (
                      <td key={n} className="cell-none" title={c.error}>
                        error
                      </td>
                    );
                  if (!isNum(c.value))
                    return (
                      <td
                        key={n}
                        className="cell-none"
                        title="Not measured for this run"
                      >
                        —
                      </td>
                    );
                  const { bg, fg } = colorFor(c.value, metric.scale);
                  const rationale =
                    c.r.answer_judge?.rationale ||
                    c.r.grounding_judge?.rationale ||
                    "";
                  return (
                    <td
                      key={n}
                      className="cell-v"
                      style={{ background: bg, color: fg }}
                      title={rationale || undefined}
                    >
                      {Number.isInteger(c.value) ? c.value : c.value.toFixed(2)}
                    </td>
                  );
                })}
                <td className="avg mono">
                  {isNum(q.avg) ? q.avg.toFixed(2) : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="heat-legend" style={{ marginTop: 12 }}>
        {metric.scale[0]} <span className="heat-ramp" /> {metric.scale[1]}
        <span>
          · "—" = not measured, "error" = the pipeline failed on that question
        </span>
      </div>
    </div>
  );
}
