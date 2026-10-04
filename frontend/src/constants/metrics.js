export const METRICS = {
  avg_recall_at_k: {
    label: "Recall@K",
    scale: "unit",
    hint: "Of the documents that should have been retrieved, the fraction that appeared in the top K.",
  },
  avg_precision_at_k: {
    label: "Precision@K",
    scale: "unit",
    hint: "Of the top K documents retrieved, the fraction that were actually relevant.",
  },
  avg_mrr: {
    label: "MRR",
    scale: "unit",
    hint: "1 / rank of the first relevant document, averaged over questions. 1.0 means it was always first.",
  },
  avg_citation_accuracy: {
    label: "Citation accuracy",
    scale: "unit",
    hint: "Of the sources the answer cited, the fraction that came from a relevant document. Undefined (skipped) when nothing was cited.",
  },
  avg_correctness: {
    label: "Correctness",
    scale: "five",
    hint: "LLM judge: does the answer state the same facts as the reference answer? (1–5)",
  },
  avg_relevance: {
    label: "Relevance",
    scale: "five",
    hint: "LLM judge: does the answer address the question asked? (1–5)",
  },
  avg_completeness: {
    label: "Completeness",
    scale: "five",
    hint: "LLM judge: does the answer cover everything the reference does? (1–5)",
  },
  avg_faithfulness: {
    label: "Faithfulness",
    scale: "five",
    hint: "LLM judge: is every claim supported by the retrieved context? Checks against what was retrieved, not ground truth. (1–5)",
  },
  hallucination_rate: {
    label: "Hallucination rate",
    scale: "unit",
    lower: true,
    hint: "Share of answers the judge flagged as containing invented information.",
  },
  avg_latency_ms: {
    label: "Latency",
    scale: "ms",
    lower: true,
    hint: "Average end-to-end time per question (retrieval + generation).",
  },
  avg_prompt_tokens: {
    label: "Prompt tokens",
    scale: "count",
    lower: true,
    hint: "Average approximate prompt size sent to the LLM.",
  },
};

export const METRIC_GROUPS = [
  {
    title: "Retrieval",
    keys: ["avg_recall_at_k", "avg_precision_at_k", "avg_mrr"],
  },
  {
    title: "Answer quality",
    subtitle: "LLM judge, 1–5",
    keys: ["avg_correctness", "avg_relevance", "avg_completeness"],
  },
  {
    title: "Grounding",
    keys: ["avg_faithfulness", "hallucination_rate", "avg_citation_accuracy"],
  },
  { title: "System", keys: ["avg_latency_ms", "avg_prompt_tokens"] },
];

export function formatMetric(key, value) {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  const scale = METRICS[key]?.scale;
  if (scale === "ms")
    return value >= 1000
      ? `${(value / 1000).toFixed(2)} s`
      : `${Math.round(value)} ms`;
  if (scale === "count") return Math.round(value).toLocaleString();
  if (scale === "five") return value.toFixed(2);
  return value.toFixed(2);
}

export const QUESTION_METRICS = {
  recall: { label: "Recall", get: (r) => r.retrieval?.recall_at_k },
  precision: { label: "Precision", get: (r) => r.retrieval?.precision_at_k },
  mrr: { label: "MRR", get: (r) => r.retrieval?.mrr },
  citation: {
    label: "Citation acc.",
    get: (r) => r.citation?.citation_accuracy,
  },
  correctness: {
    label: "Correctness",
    get: (r) => r.answer_judge?.correctness,
  },
  relevance: { label: "Relevance", get: (r) => r.answer_judge?.relevance },
  completeness: {
    label: "Completeness",
    get: (r) => r.answer_judge?.completeness,
  },
  faithfulness: {
    label: "Faithfulness",
    get: (r) => r.grounding_judge?.faithfulness,
  },
  latency: { label: "Latency (ms)", get: (r) => r.system?.latency_ms },
};

export const shortRunName = (name) =>
  name.replace(/^experiment_\d+_/, "").replace(/_/g, " ");
