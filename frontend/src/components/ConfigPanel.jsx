import { useEffect, useRef, useState } from "react";
import { api } from "../services/api.js";

function Row({ label, value }) {
  return (
    <div className="cfg-row">
      <span className="muted">{label}</span>
      <span className="mono small">{value}</span>
    </div>
  );
}

export function ConfigPanel({ config }) {
  const emb = config.embeddings;
  const embActive = emb.active.length
    ? emb.active.join(", ")
    : "not loaded yet (loads on first query)";
  return (
    <div className="cfg">
      {config.warnings.map((w) => (
        <div key={w} className="notice notice-warn">
          ⚠ {w}
        </div>
      ))}
      <Row label="LLM" value={`${config.llm.provider} · ${config.llm.model}`} />
      <Row
        label="API key"
        value={config.llm.api_key_configured ? "configured" : "MISSING"}
      />
      <Row
        label="Embeddings (configured)"
        value={`${emb.configured_backend} · ${emb.model_name}`}
      />
      <Row label="Embeddings (active)" value={embActive} />
      <Row
        label="Reranker (active)"
        value={config.reranker.active.join(", ") || "not loaded yet"}
      />
      <Row label="Tokenizer" value={config.tokenizer} />
      <Row
        label="Fixed chunking"
        value={`${config.chunking.fixed_chunk_size} tok / ${config.chunking.fixed_chunk_overlap} overlap`}
      />
      <Row
        label="Semantic chunking"
        value={`p${config.chunking.semantic_breakpoint_percentile} · ${config.chunking.semantic_min_chunk_tokens}–${config.chunking.semantic_max_chunk_tokens} tok`}
      />
      <Row
        label="LangSmith tracing"
        value={
          config.tracing.langsmith_enabled
            ? `on · ${config.tracing.project}`
            : "off"
        }
      />
      <Row
        label="Loaded pipelines"
        value={config.loaded_pipelines.join(", ") || "none yet"}
      />
    </div>
  );
}

export function ConfigBadge() {
  const [config, setConfig] = useState(null);
  const [error, setError] = useState(false);
  const [open, setOpen] = useState(false);
  const box = useRef(null);

  const load = () =>
    api
      .config()
      .then((c) => {
        setConfig(c);
        setError(false);
      })
      .catch(() => setError(true));

  useEffect(() => {
    load();
  }, []);
  useEffect(() => {
    const close = (e) =>
      box.current && !box.current.contains(e.target) && setOpen(false);
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, []);

  const warn = config?.warnings.length > 0;
  const label = error
    ? "API offline"
    : !config
      ? "…"
      : warn
        ? `${config.warnings.length} warning${config.warnings.length > 1 ? "s" : ""}`
        : "System OK";
  const cls = error ? "dot-err" : warn ? "dot-warn" : "dot-ok";

  return (
    <div className="cfg-badge" ref={box}>
      <button
        type="button"
        className="chip"
        onClick={() => {
          setOpen((o) => !o);
          load();
        }}
      >
        <span className={`dot ${cls}`} /> {label}
      </button>
      {open && config && (
        <div className="popover card">
          <div className="field-label" style={{ marginBottom: 8 }}>
            System configuration
          </div>
          <ConfigPanel config={config} />
        </div>
      )}
    </div>
  );
}
