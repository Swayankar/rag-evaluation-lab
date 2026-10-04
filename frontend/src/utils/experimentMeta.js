import { CHUNK_SHORT, RETRIEVAL_SHORT, isNum } from "./evalMetrics.js";

const NAME_RE = /(fixed|semantic)_(hybrid_rerank|hybrid|vector|bm25)/;

export function describeExperiments(names, configs = [], details = {}) {
  const byConfig = new Map(configs.map((c) => [c.name, c]));
  const out = new Map();

  names.forEach((name) => {
    const meta = details[name]?.meta ?? {};
    const cfg = byConfig.get(name) ?? {};
    const guess = NAME_RE.exec(name);
    const chunking =
      meta.chunking_strategy ?? cfg.chunking_strategy ?? guess?.[1] ?? null;
    const retrieval =
      meta.retrieval_strategy ?? cfg.retrieval_strategy ?? guess?.[2] ?? null;
    const top_k = meta.top_k ?? cfg.top_k ?? null;
    const base =
      chunking && retrieval
        ? `${CHUNK_SHORT[chunking] ?? chunking} + ${RETRIEVAL_SHORT[retrieval] ?? retrieval}`
        : name;
    out.set(name, { name, chunking, retrieval, top_k, label: base, base });
  });

  const groups = new Map();
  out.forEach((d) => groups.set(d.base, [...(groups.get(d.base) ?? []), d]));
  groups.forEach((list) => {
    if (list.length < 2) return;
    const distinctK = new Set(list.map((d) => d.top_k)).size === list.length;
    list.forEach((d) => {
      d.label =
        distinctK && d.top_k != null
          ? `${d.base} · top-${d.top_k}`
          : `${d.base} (${d.name})`;
    });
  });
  return out;
}

// --- metrics ---------------------------------------------------------------

export const METRIC_INFO = {
  avg_recall_at_k: { label: "Recall@K", group: 0, decimals: 3 },
  avg_precision_at_k: { label: "Precision@K", group: 0, decimals: 3 },
  avg_mrr: { label: "MRR", group: 0, decimals: 3 },
  avg_correctness: { label: "Correctness (1–5)", group: 1, decimals: 2 },
  avg_relevance: { label: "Relevance (1–5)", group: 1, decimals: 2 },
  avg_completeness: { label: "Completeness (1–5)", group: 1, decimals: 2 },
  avg_faithfulness: { label: "Faithfulness (1–5)", group: 1, decimals: 2 },
  avg_citation_accuracy: { label: "Citation accuracy", group: 2, decimals: 3 },
  hallucination_rate: { label: "Hallucination rate", group: 2, decimals: 3 },
  avg_latency_ms: { label: "Latency (ms)", group: 3, decimals: 0 },
  avg_prompt_tokens: { label: "Prompt tokens", group: 3, decimals: 0 },
};

export const metricLabel = (m) =>
  METRIC_INFO[m]?.label ?? m.replace(/^avg_/, "").replace(/_/g, " ");

export function formatMetric(metric, value) {
  if (!isNum(value)) return "—";
  return value.toFixed(METRIC_INFO[metric]?.decimals ?? 3);
}

export const sortMetrics = (rows) =>
  [...rows].sort(
    (a, b) =>
      (METRIC_INFO[a.metric]?.group ?? 9) - (METRIC_INFO[b.metric]?.group ?? 9),
  );

export function rowsFromComparison(comparison, meta) {
  if (!comparison) return [];
  return comparison.experiments.map((name) => {
    const row = {
      name,
      chunking: meta.get(name)?.chunking,
      retrieval: meta.get(name)?.retrieval,
    };
    comparison.metrics.forEach((m) => {
      if (name in (m.values ?? {})) row[m.metric] = m.values[name];
    });
    if (isNum(row.avg_latency_ms))
      row.avg_latency_s = row.avg_latency_ms / 1000;
    return row;
  });
}

export function metricsWon(comparison) {
  const won = Object.fromEntries(comparison.experiments.map((n) => [n, []]));
  comparison.metrics.forEach((m) => {
    if (m.best in won) won[m.best].push(m.metric);
  });
  return won;
}

// --- CSV -------------------------------------------------------------------

export function comparisonCsv(comparison, meta) {
  const labels = comparison.experiments.map((n) => meta.get(n)?.label ?? n);
  const columns = ["metric", "direction", "best", ...labels];
  const rows = sortMetrics(comparison.metrics).map((m) => {
    const row = {
      metric: m.metric,
      direction: m.direction,
      best: meta.get(m.best)?.label ?? m.best,
    };
    comparison.experiments.forEach((n, i) => {
      row[labels[i]] = m.values?.[n];
    });
    return row;
  });
  const wins = metricsWon(comparison);
  rows.push({
    metric: "WINS (metrics each experiment is best on)",
    direction: "",
    best: "",
    ...Object.fromEntries(
      comparison.experiments.map((n, i) => [labels[i], wins[n].length]),
    ),
  });
  return { rows, columns };
}
