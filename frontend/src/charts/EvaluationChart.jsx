import { useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  CHUNK_SHORT,
  RETRIEVAL_SHORT,
  SERIES_COLORS,
  isNum,
  prettyName,
} from "../utils/evalMetrics.js";

const INK_SECONDARY = "#c3c2b7";
const INK_MUTED = "#898781";
const GRID = "#2c2c2a";
const BASELINE = "#383835";

function StrategyTick({ x, y, payload, byName }) {
  const row = byName[payload.value];
  return (
    <g transform={`translate(${x},${y})`}>
      <text textAnchor="middle" fontSize={11}>
        <tspan x={0} dy={14} fill={INK_SECONDARY}>
          {CHUNK_SHORT[row?.chunking] ?? row?.chunking}
        </tspan>
        <tspan x={0} dy={13} fill={INK_MUTED}>
          {RETRIEVAL_SHORT[row?.retrieval] ?? row?.retrieval}
        </tspan>
      </text>
    </g>
  );
}

function Tip({ active, payload, series, decimals, labelOf }) {
  if (!active || !payload?.length) return null;
  const name = payload[0].payload.name;
  return (
    <div className="chart-tip">
      <div className="chart-tip-title">{labelOf(name)}</div>
      {series.map((s) => {
        const v = payload[0].payload[s.key];
        return (
          <div key={s.key} className="chart-tip-row">
            <span>
              <span className="swatch" style={{ background: s.color }} />{" "}
              {s.label}
            </span>
            <span className="mono">{isNum(v) ? v.toFixed(decimals) : "—"}</span>
          </div>
        );
      })}
    </div>
  );
}

export default function EvaluationChart({
  title,
  subtitle,
  rows,
  series,
  domain = [0, "auto"],
  decimals = 2,
  labelOf = prettyName,
}) {
  const [showTable, setShowTable] = useState(false);
  const shown = series
    .map((s, i) => ({ ...s, color: SERIES_COLORS[i % SERIES_COLORS.length] }))
    .filter((s) => rows.some((r) => isNum(r[s.key])));
  if (shown.length === 0) return null;

  const byName = Object.fromEntries(rows.map((r) => [r.name, r]));
  const width = Math.max(1, rows.length);

  return (
    <div className="card">
      <div className="chart-head">
        <div>
          <div className="chart-title">{title}</div>
          <div className="muted small">{subtitle}</div>
        </div>
        <button
          type="button"
          className="link"
          onClick={() => setShowTable((s) => !s)}
        >
          {showTable ? "Show chart" : "Show table"}
        </button>
      </div>

      {shown.length > 1 && (
        <div className="legend">
          {shown.map((s) => (
            <span key={s.key} className="legend-item">
              <span className="swatch" style={{ background: s.color }} />
              {s.label}
            </span>
          ))}
        </div>
      )}

      {showTable ? (
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Strategy</th>
                {shown.map((s) => (
                  <th key={s.key}>{s.label}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.name}>
                  <td>{labelOf(r.name)}</td>
                  {shown.map((s) => (
                    <td key={s.key} className="mono">
                      {isNum(r[s.key]) ? r[s.key].toFixed(decimals) : "—"}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div
          role="img"
          aria-label={`${title}: grouped bar chart by strategy`}
          style={{ width: "100%", height: 280 }}
        >
          <ResponsiveContainer>
            <BarChart
              data={rows}
              margin={{ top: 10, right: 8, left: -8, bottom: 8 }}
              barGap={2}
              barCategoryGap={width > 4 ? "18%" : "30%"}
            >
              <CartesianGrid
                vertical={false}
                stroke={GRID}
                strokeDasharray="0"
              />
              <XAxis
                dataKey="name"
                axisLine={{ stroke: BASELINE }}
                tickLine={false}
                interval={0}
                height={48}
                tick={<StrategyTick byName={byName} />}
              />
              <YAxis
                domain={domain}
                ticks={domain[1] === 5 ? [0, 1, 2, 3, 4, 5] : undefined}
                axisLine={false}
                tickLine={false}
                tick={{ fill: INK_MUTED, fontSize: 11 }}
                width={44}
              />
              <Tooltip
                cursor={{ fill: "rgba(255,255,255,0.04)" }}
                content={
                  <Tip series={shown} decimals={decimals} labelOf={labelOf} />
                }
              />
              {shown.map((s) => (
                <Bar
                  key={s.key}
                  dataKey={s.key}
                  fill={s.color}
                  maxBarSize={24}
                  radius={[4, 4, 0, 0]}
                  isAnimationActive={false}
                />
              ))}
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}
