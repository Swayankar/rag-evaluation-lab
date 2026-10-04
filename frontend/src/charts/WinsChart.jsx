import { useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  LabelList,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { SERIES_COLORS } from "../utils/evalMetrics.js";
import { metricLabel } from "../utils/experimentMeta.js";

const INK_SECONDARY = "#c3c2b7";
const INK_MUTED = "#898781";
const GRID = "#2c2c2a";
const BASELINE = "#383835";

function LabelTick({ x, y, payload }) {
  const [first, ...rest] = String(payload.value).split(" + ");
  const second = rest.join(" + ");
  return (
    <g transform={`translate(${x},${y})`}>
      <text textAnchor="middle" fontSize={11}>
        <tspan x={0} dy={14} fill={INK_SECONDARY}>
          {first}
        </tspan>
        {second && (
          <tspan x={0} dy={13} fill={INK_MUTED}>
            {second}
          </tspan>
        )}
      </text>
    </g>
  );
}

function Tip({ active, payload, total }) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return (
    <div className="chart-tip" style={{ maxWidth: 280 }}>
      <div className="chart-tip-title">{d.label}</div>
      <div className="chart-tip-row">
        <span>Metrics won</span>
        <span className="mono">
          {d.wins} of {total}
        </span>
      </div>
      {d.won.length > 0 && (
        <div className="muted small" style={{ marginTop: 6 }}>
          {d.won.map(metricLabel).join(", ")}
        </div>
      )}
    </div>
  );
}

export default function WinsChart({ ranking, total, won, labelOf }) {
  const [showTable, setShowTable] = useState(false);
  const step = Math.max(1, Math.ceil(total / 5));
  const data = ranking.map((r) => ({
    name: r.name,
    label: labelOf(r.name),
    wins: r.wins,
    won: won[r.name] ?? [],
  }));

  return (
    <div className="card">
      <div className="chart-head">
        <div>
          <div className="chart-title">Wins by experiment</div>
          <div className="muted small">
            On how many of the {total} metrics each experiment scored best
            (direction-aware: lower latency and hallucination win).
          </div>
        </div>
        <button
          type="button"
          className="link"
          onClick={() => setShowTable((s) => !s)}
        >
          {showTable ? "Show chart" : "Show table"}
        </button>
      </div>

      {showTable ? (
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Experiment</th>
                <th>Wins</th>
                <th>Best at</th>
              </tr>
            </thead>
            <tbody>
              {data.map((d) => (
                <tr key={d.name}>
                  <td>{d.label}</td>
                  <td className="mono">
                    {d.wins} / {total}
                  </td>
                  <td className="muted small">
                    {d.won.map(metricLabel).join(", ") || "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div
          role="img"
          aria-label="Bar chart of metrics won by each experiment"
          style={{ width: "100%", height: 260 }}
        >
          <ResponsiveContainer>
            <BarChart
              data={data}
              margin={{ top: 22, right: 8, left: -12, bottom: 8 }}
              barCategoryGap="30%"
            >
              <CartesianGrid
                vertical={false}
                stroke={GRID}
                strokeDasharray="0"
              />
              <XAxis
                dataKey="label"
                axisLine={{ stroke: BASELINE }}
                tickLine={false}
                interval={0}
                height={48}
                tick={<LabelTick />}
              />
              <YAxis
                domain={[0, Math.max(total, 1)]}
                ticks={Array.from(
                  { length: Math.floor(total / step) + 1 },
                  (_, i) => i * step,
                )}
                allowDecimals={false}
                axisLine={false}
                tickLine={false}
                tick={{ fill: INK_MUTED, fontSize: 11 }}
                width={40}
              />
              <Tooltip
                cursor={{ fill: "rgba(255,255,255,0.04)" }}
                content={<Tip total={total} />}
              />
              <Bar
                dataKey="wins"
                fill={SERIES_COLORS[0]}
                maxBarSize={24}
                radius={[4, 4, 0, 0]}
                isAnimationActive={false}
              >
                <LabelList
                  dataKey="wins"
                  position="top"
                  fill={INK_SECONDARY}
                  fontSize={11}
                />
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}
