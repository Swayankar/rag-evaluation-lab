export const SERIES_COLORS = ["#3987e5", "#d95926", "#199e70", "#c98500"];

export const CHUNK_SHORT = { fixed: "Fixed", semantic: "Semantic" };
export const RETRIEVAL_SHORT = {
  vector: "Vector",
  bm25: "BM25",
  hybrid: "Hybrid",
  hybrid_rerank: "Hybrid+Rerank",
};

export const CHART_GROUPS = [
  {
    id: "retrieval",
    title: "Retrieval quality",
    subtitle: "Were the right documents retrieved? 0–1, higher is better.",
    domain: [0, 1],
    decimals: 2,
    series: [
      { key: "avg_recall_at_k", label: "Recall@K" },
      { key: "avg_precision_at_k", label: "Precision@K" },
      { key: "avg_mrr", label: "MRR" },
    ],
  },
  {
    id: "answer",
    title: "Answer quality (LLM judge)",
    subtitle:
      "Scored 1–5 against the reference answer and the retrieved context, higher is better.",
    domain: [0, 5],
    decimals: 2,
    series: [
      { key: "avg_correctness", label: "Correctness" },
      { key: "avg_relevance", label: "Relevance" },
      { key: "avg_completeness", label: "Completeness" },
      { key: "avg_faithfulness", label: "Faithfulness" },
    ],
  },
  {
    id: "grounding",
    title: "Citations & hallucination",
    subtitle:
      "Citation accuracy: higher is better. Hallucination rate: lower is better. 0–1.",
    domain: [0, 1],
    decimals: 2,
    series: [
      { key: "avg_citation_accuracy", label: "Citation accuracy ↑" },
      { key: "hallucination_rate", label: "Hallucination rate ↓" },
    ],
  },
  {
    id: "latency",
    title: "Latency",
    subtitle:
      "Average seconds per question (retrieval + generation), lower is better.",
    domain: [0, "auto"],
    decimals: 2,
    series: [{ key: "avg_latency_s", label: "Seconds per question" }],
  },
];

export const TILE_METRICS = [
  {
    key: "avg_recall_at_k",
    label: "Best recall@K",
    direction: "higher",
    decimals: 2,
  },
  { key: "avg_mrr", label: "Best MRR", direction: "higher", decimals: 2 },
  {
    key: "avg_correctness",
    label: "Best correctness",
    direction: "higher",
    decimals: 2,
    suffix: " / 5",
  },
  {
    key: "avg_faithfulness",
    label: "Best faithfulness",
    direction: "higher",
    decimals: 2,
    suffix: " / 5",
  },
  {
    key: "hallucination_rate",
    label: "Lowest hallucination",
    direction: "lower",
    decimals: 2,
  },
  {
    key: "avg_latency_s",
    label: "Fastest",
    direction: "lower",
    decimals: 2,
    suffix: " s",
  },
];

export const AGGREGATE_COLUMNS = [
  "avg_recall_at_k",
  "avg_precision_at_k",
  "avg_mrr",
  "avg_citation_accuracy",
  "avg_correctness",
  "avg_relevance",
  "avg_completeness",
  "avg_faithfulness",
  "hallucination_rate",
  "avg_latency_ms",
  "avg_prompt_tokens",
  "num_questions",
  "num_errors",
  "num_judge_errors",
];

export const HEAT_METRICS = [
  {
    id: "recall",
    label: "Recall@K",
    scale: [0, 1],
    pick: (r) => r.retrieval?.recall_at_k ?? null,
  },
  {
    id: "mrr",
    label: "MRR",
    scale: [0, 1],
    pick: (r) => r.retrieval?.mrr ?? null,
  },
  {
    id: "correctness",
    label: "Correctness",
    scale: [1, 5],
    pick: (r) => r.answer_judge?.correctness ?? null,
  },
  {
    id: "faithfulness",
    label: "Faithfulness",
    scale: [1, 5],
    pick: (r) => r.grounding_judge?.faithfulness ?? null,
  },
  {
    id: "citation",
    label: "Citation accuracy",
    scale: [0, 1],
    pick: (r) => r.citation?.citation_accuracy ?? null,
  },
];

export function chartRows(results) {
  return results.map((r) => {
    const a = r.aggregate ?? {};
    return {
      name: r.name,
      chunking: r.chunking,
      retrieval: r.retrieval,
      ...a,
      avg_latency_s:
        typeof a.avg_latency_ms === "number"
          ? a.avg_latency_ms / 1000
          : undefined,
    };
  });
}

export const isNum = (v) => typeof v === "number" && Number.isFinite(v);

export function bestBy(rows, key, direction) {
  const valid = rows.filter((r) => isNum(r[key]));
  if (!valid.length) return null;
  return valid.reduce((a, b) =>
    (direction === "higher" ? b[key] > a[key] : b[key] < a[key]) ? b : a,
  );
}

export const prettyName = (name) => {
  const [c, ...rest] = name.split("_");
  const retrieval = rest.join("_");
  return `${CHUNK_SHORT[c] ?? c} + ${RETRIEVAL_SHORT[retrieval] ?? retrieval}`;
};
