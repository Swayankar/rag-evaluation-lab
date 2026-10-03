export const CHUNKING = [
  {
    id: "fixed",
    label: "Fixed",
    hint: "500-token windows, 50 overlap (baseline)",
  },
  { id: "semantic", label: "Semantic", hint: "Splits where the topic changes" },
];

export const RETRIEVAL = [
  { id: "vector", label: "Vector", hint: "Embedding similarity" },
  {
    id: "bm25",
    label: "BM25",
    hint: "Keyword match, good for exact numbers/terms",
  },
  { id: "hybrid", label: "Hybrid", hint: "Vector + BM25 fused with RRF" },
  {
    id: "hybrid_rerank",
    label: "Hybrid + Rerank",
    hint: "Hybrid, then a cross-encoder reorders",
  },
];

export const keyOf = (chunking, retrieval) => `${chunking}|${retrieval}`;
export const parseKey = (key) => {
  const [chunking_strategy, retrieval_strategy] = key.split("|");
  return { chunking_strategy, retrieval_strategy };
};

export const ALL_KEYS = CHUNKING.flatMap((c) =>
  RETRIEVAL.map((r) => keyOf(c.id, r.id)),
);

export const EXPERIMENT_KEYS = [
  keyOf("fixed", "vector"),
  keyOf("semantic", "vector"),
  keyOf("fixed", "hybrid"),
  keyOf("semantic", "hybrid"),
  keyOf("semantic", "hybrid_rerank"),
];

export const labelFor = (chunking, retrieval) => {
  const c = CHUNKING.find((x) => x.id === chunking)?.label ?? chunking;
  const r = RETRIEVAL.find((x) => x.id === retrieval)?.label ?? retrieval;
  return `${c} + ${r}`;
};

export const EXAMPLE_QUESTIONS = [
  "How many weeks of paid parental leave are employees entitled to?",
  "What is the minimum password length required by the security policy?",
  "Above what dollar amount does an expense require an itemized receipt?",
];
