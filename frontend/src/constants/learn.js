export const PIPELINE = [
  {
    lane: "Indexing",
    laneHint: "Happens once per document set, whenever you rebuild the index.",
    steps: [
      {
        id: "parse",
        title: "Read & clean",
        short: "PDF → clean text + metadata",
        detail: [
          "Each PDF is read page by page and the text is tidied (control characters, runs of spaces and blank lines removed). Every piece of text keeps its metadata: document id and name, department, year (taken from the file name) and page number.",
          "That metadata travels with every chunk, so an answer can later cite exactly which document and page it came from.",
        ],
        link: { to: "/documents", label: "See your documents" },
      },
      {
        id: "chunk",
        title: "Chunk",
        short: "Fixed or semantic pieces",
        detail: [
          "Documents are cut into chunks small enough to retrieve precisely. The lab builds two versions of the same library so you can compare them.",
          "Fixed chunking slices every {fixed} tokens with {overlap} tokens of overlap (the baseline). Semantic chunking embeds the sentences and starts a new chunk where the topic changes.",
        ],
        link: { to: "/documents", label: "Rebuild the index" },
      },
      {
        id: "embed",
        title: "Embed & index",
        short: "Vectors + keyword index",
        detail: [
          "Every chunk becomes a vector (a list of numbers capturing its meaning) stored in a vector index, and also goes into a keyword (BM25) index.",
          "If the embedding model can't load, the backend falls back to a simple hashing embedder so it keeps working. The badge in the top bar warns you when that happens, because scores from the fallback don't measure real semantic search.",
        ],
        link: null,
      },
    ],
  },
  {
    lane: "Answering",
    laneHint: "Happens for every question you ask.",
    steps: [
      {
        id: "retrieve",
        title: "Retrieve",
        short: "Find the top-K chunks",
        detail: [
          "The question is matched against the index using the strategy you picked: vector, BM25, hybrid or hybrid + rerank. The result is the top-K most relevant chunks.",
          "This is the step the experiments vary the most, and the one that decides whether the model even gets a chance to answer correctly.",
        ],
        link: { to: "/playground", label: "Try it in the Playground" },
      },
      {
        id: "prompt",
        title: "Build the prompt",
        short: "Question + context + rules",
        detail: [
          "The retrieved chunks are numbered and placed in a prompt together with the question and instructions: answer only from the context, cite the chunks you used, and say so if the answer isn't there.",
        ],
        link: null,
      },
      {
        id: "llm",
        title: "Answer with citations",
        short: "Groq LLM → answer + sources",
        detail: [
          "The language model (Groq) writes the answer. Citations in the answer are parsed and checked against the chunks that were actually retrieved, so a made-up source is dropped rather than shown.",
        ],
        link: { to: "/playground", label: "Ask a question" },
      },
    ],
  },
  {
    lane: "Measuring",
    laneHint: 'Turns "it feels better" into numbers.',
    steps: [
      {
        id: "score",
        title: "Score",
        short: "Retrieval, answer, grounding, system",
        detail: [
          "Every evaluation question has the documents that should be found (and optionally a reference answer). Each strategy answers all of them and is scored on retrieval, answer quality, grounding and speed.",
          "Retrieval and citation scores are computed directly. Answer quality and faithfulness come from an LLM judge, so treat them as a careful second opinion, not ground truth.",
        ],
        link: { to: "/evaluation", label: "Open Evaluation" },
      },
      {
        id: "compare",
        title: "Compare",
        short: "Same questions, side by side",
        detail: [
          "Experiments run several chunking × retrieval setups against the same questions, so any difference comes from the strategy and not from the questions.",
        ],
        link: { to: "/experiments", label: "Open Experiments" },
      },
      {
        id: "recommend",
        title: "Recommend",
        short: "Which setup wins, and where",
        detail: [
          "For each metric the best experiment is marked (lower is better for latency and hallucinations). The experiment that is best on the most metrics is recommended, along with where it is weakest.",
          "It's a rule of thumb. If one metric matters more to you, pick for that one.",
        ],
        link: { to: "/experiments", label: "See the recommendation" },
      },
    ],
  },
];

export const CHUNKING_INFO = [
  {
    id: "fixed",
    title: "Fixed chunking",
    tag: "Baseline",
    how: "Slices the text every {fixed} tokens, with {overlap} tokens of overlap so a sentence on the boundary isn't lost.",
    good: "Predictable, fast, and uniform in size.",
    watch:
      "Can cut through the middle of a topic, splitting an answer across two chunks.",
  },
  {
    id: "semantic",
    title: "Semantic chunking",
    tag: "Experiment",
    how: "Embeds neighbouring sentences and starts a new chunk where the similarity drops sharply, within a minimum and maximum size.",
    good: "Chunks follow the document's own sections, so one chunk tends to hold one idea.",
    watch:
      "Slower to build, sizes vary, and it depends on the quality of the embeddings.",
  },
];

export const RETRIEVAL_INFO = [
  {
    id: "vector",
    title: "Vector",
    how: "Compares the meaning of the question with the meaning of each chunk.",
    good: 'Finds paraphrases: "time off for a new baby" matches "parental leave".',
    watch: "Can miss exact terms, numbers and codes.",
  },
  {
    id: "bm25",
    title: "BM25",
    how: "Classic keyword scoring: rewards chunks that contain the question's rare words.",
    good: "Exact numbers, names and policy codes.",
    watch: "Blind to synonyms and rewording.",
  },
  {
    id: "hybrid",
    title: "Hybrid",
    how: "Runs vector and BM25, then merges the two ranked lists with Reciprocal Rank Fusion.",
    good: "Covers both kinds of question; usually a safe default.",
    watch:
      "Two searches instead of one, and the fused order can still put a good chunk too low.",
  },
  {
    id: "hybrid_rerank",
    title: "Hybrid + rerank",
    how: "Takes the hybrid candidates and has a cross-encoder model re-read each one against the question to reorder them.",
    good: "Best at putting the right chunk first (higher MRR).",
    watch:
      "Slowest. If the reranker can't load, it silently behaves like plain hybrid, and the badge warns you.",
  },
];

export const EXPERIMENT_PLAN = [
  {
    n: 1,
    combo: "Fixed + Vector",
    asks: "The baseline everything else is compared with.",
  },
  {
    n: 2,
    combo: "Semantic + Vector",
    asks: "Does semantic chunking beat fixed chunking? (compare with 1)",
  },
  {
    n: 3,
    combo: "Fixed + Hybrid",
    asks: "Does adding keyword search help? (compare with 1)",
  },
  {
    n: 4,
    combo: "Semantic + Hybrid",
    asks: "Do semantic chunks and hybrid search add up? (compare with 2 and 3)",
  },
  {
    n: 5,
    combo: "Semantic + Hybrid + Rerank",
    asks: "Is the reranker worth its extra latency? (compare with 4)",
  },
];

export const METRIC_GROUPS = [
  {
    title: "Retrieval",
    blurb:
      "Did the right documents come back? No LLM involved, so these are exact and repeatable.",
    metrics: [
      {
        name: "Recall@K",
        scale: "0–1 · higher",
        text: "Of the documents that should be found, the share that appear in the top K.",
      },
      {
        name: "Precision@K",
        scale: "0–1 · higher",
        text: "Of the top K results, the share that come from a relevant document.",
      },
      {
        name: "MRR",
        scale: "0–1 · higher",
        text: "1 divided by the rank of the first relevant result: 1.0 if it's first, 0.5 if second, 0 if absent.",
      },
    ],
  },
  {
    title: "Answer quality",
    blurb: "An LLM judge reads the answer next to the reference answer.",
    metrics: [
      {
        name: "Correctness",
        scale: "1–5 · higher",
        text: "Does the answer state the same facts as the reference answer?",
      },
      {
        name: "Relevance",
        scale: "1–5 · higher",
        text: "Does it actually address the question that was asked?",
      },
      {
        name: "Completeness",
        scale: "1–5 · higher",
        text: "Does it cover everything the reference answer does?",
      },
    ],
  },
  {
    title: "Grounding",
    blurb: "Is the answer backed by what was retrieved?",
    metrics: [
      {
        name: "Faithfulness",
        scale: "1–5 · higher",
        text: "Is every claim supported by the retrieved text? (Judged against the context, not against the truth.)",
      },
      {
        name: "Hallucination rate",
        scale: "0–1 · lower",
        text: "The share of answers the judge flagged as likely to contain invented content.",
      },
      {
        name: "Citation accuracy",
        scale: "0–1 · higher",
        text: "Of the sources the answer cited, the share that point at a relevant document.",
      },
    ],
  },
  {
    title: "System",
    blurb: "What it costs to get the answer.",
    metrics: [
      {
        name: "Latency",
        scale: "ms · lower",
        text: "Average time per question for retrieval plus generation.",
      },
      {
        name: "Prompt tokens",
        scale: "count · lower",
        text: "Approximate size of the prompt sent to the model. Bigger prompts cost more.",
      },
    ],
  },
];

export const CAVEATS = [
  "Small question sets are noisy. With 5 questions, one lucky or unlucky answer moves an average a lot. Write more questions before trusting a small gap.",
  "Relevance is judged at document level: a result counts if it comes from a document you listed, even if it isn't the exact passage.",
  "LLM-judge scores (correctness, faithfulness, hallucination) are another model's opinion. Skim the per-question detail when a number surprises you.",
  "Faithfulness checks the answer against the retrieved text. An answer can be faithful to the wrong context and still be wrong, so read it together with recall and correctness.",
  "Only compare runs made on the same questions, the same index and real embeddings. The app flags when they weren't.",
];
