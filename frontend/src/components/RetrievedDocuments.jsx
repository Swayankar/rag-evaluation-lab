import { useState } from "react";

export default function RetrievedDocuments({
  chunks,
  citedIndices,
  activeIndex,
  onActivate,
  idPrefix,
}) {
  const [open, setOpen] = useState({});

  return (
    <div className="sources">
      <div className="field-label">Retrieved sources ({chunks.length})</div>
      <div className="muted small" style={{ marginBottom: 8 }}>
        Scores use each strategy's own scale (cosine, RRF, BM25, cross-encoder),
        so compare ranks, not raw values across strategies.
      </div>
      {chunks.map((c, i) => {
        const n = i + 1;
        const cited = citedIndices.has(n);
        const expanded = !!open[c.chunk_id];
        return (
          <div
            key={c.chunk_id}
            id={`${idPrefix}-src-${n}`}
            className={`source ${activeIndex === n ? "source-active" : ""}`}
            onMouseEnter={() => onActivate(n)}
            onMouseLeave={() => onActivate(null)}
          >
            <div className="source-head">
              <span className={`cite-num ${cited ? "cite-num-used" : ""}`}>
                {n}
              </span>
              <span className="source-title">{c.document_name}</span>
              <span className="badge">{c.department}</span>
              <span className="muted small">p.{c.page}</span>
              {cited && <span className="badge badge-ok">cited</span>}
              <span className="mono small score">{c.score.toFixed(3)}</span>
            </div>
            <p className={`source-text ${expanded ? "" : "clamp"}`}>{c.text}</p>
            <button
              type="button"
              className="link"
              onClick={() =>
                setOpen((o) => ({ ...o, [c.chunk_id]: !expanded }))
              }
            >
              {expanded ? "Show less" : "Show full chunk"}
            </button>
          </div>
        );
      })}
    </div>
  );
}
