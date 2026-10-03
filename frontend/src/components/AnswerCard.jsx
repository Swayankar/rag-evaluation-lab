import { useId, useMemo, useState } from "react";
import RetrievedDocuments from "./RetrievedDocuments.jsx";
import { labelFor } from "../constants/strategies.js";

function renderAnswer(text, nSources, activeIndex, onActivate, idPrefix) {
  return text.split(/(\[\d+\])/g).map((part, i) => {
    const m = part.match(/^\[(\d+)\]$/);
    if (!m) return part;
    const n = Number(m[1]);
    if (n < 1 || n > nSources) return part;
    return (
      <button
        key={i}
        type="button"
        className={`cite ${activeIndex === n ? "cite-active" : ""}`}
        onMouseEnter={() => onActivate(n)}
        onMouseLeave={() => onActivate(null)}
        onClick={() =>
          document
            .getElementById(`${idPrefix}-src-${n}`)
            ?.scrollIntoView({ behavior: "smooth", block: "center" })
        }
      >
        {n}
      </button>
    );
  });
}

export default function AnswerCard({ result, compact = false }) {
  const idPrefix = useId().replace(/:/g, "");
  const [activeIndex, setActiveIndex] = useState(null);
  const [showSources, setShowSources] = useState(!compact);

  const chunks = result.retrieved_chunks;
  const citedIndices = useMemo(() => {
    const ids = new Set(result.citations.map((c) => c.chunk_id));
    return new Set(
      chunks
        .map((c, i) => (ids.has(c.chunk_id) ? i + 1 : null))
        .filter(Boolean),
    );
  }, [result, chunks]);

  const title = labelFor(result.chunking_strategy, result.retrieval_strategy);

  return (
    <div className="card answer-card">
      <div className="answer-head">
        <div className="strategy-tags">
          <span className="badge badge-chunk">{result.chunking_strategy}</span>
          <span
            className={`badge badge-ret badge-${result.retrieval_strategy}`}
          >
            {result.retrieval_strategy}
          </span>
        </div>
        <div className="answer-meta">
          <span className="mono small">
            {(result.latency_ms / 1000).toFixed(2)}s
          </span>
          <span className="muted small">{result.citations.length} cited</span>
        </div>
      </div>
      {compact && <h3 className="answer-title">{title}</h3>}

      <p className="answer-text">
        {renderAnswer(
          result.answer,
          chunks.length,
          activeIndex,
          setActiveIndex,
          idPrefix,
        )}
      </p>

      {result.citations.length === 0 && (
        <div className="notice notice-warn">
          No [n] citations in this answer. The model may not have followed the
          citation instruction, or decided the context didn't answer the
          question.
        </div>
      )}

      {compact && (
        <button
          type="button"
          className="link"
          onClick={() => setShowSources((s) => !s)}
        >
          {showSources ? "Hide sources" : `Show ${chunks.length} sources`}
        </button>
      )}
      {showSources && (
        <RetrievedDocuments
          chunks={chunks}
          citedIndices={citedIndices}
          activeIndex={activeIndex}
          onActivate={setActiveIndex}
          idPrefix={idPrefix}
        />
      )}
    </div>
  );
}
