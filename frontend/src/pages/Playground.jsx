import { useEffect, useRef, useState } from "react";
import QuestionInput from "../components/QuestionInput.jsx";
import StrategySelector from "../components/StrategySelector.jsx";
import AnswerCard from "../components/AnswerCard.jsx";
import ComparisonSummary from "../components/ComparisonSummary.jsx";
import { api } from "../services/api.js";
import { keyOf, parseKey } from "../constants/strategies.js";

const STORAGE_KEY = "rag-lab:playground";

function loadPrefs() {
  try {
    const p = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "{}");
    return {
      selected: Array.isArray(p.selected)
        ? p.selected
        : [keyOf("fixed", "vector")],
      topK: p.topK ?? 5,
    };
  } catch {
    return { selected: [keyOf("fixed", "vector")], topK: 5 };
  }
}

export default function Playground() {
  const prefs = useRef(loadPrefs()).current;
  const [question, setQuestion] = useState("");
  const [selected, setSelected] = useState(prefs.selected);
  const [topK, setTopK] = useState(prefs.topK);

  const [loading, setLoading] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [error, setError] = useState(null);
  const [single, setSingle] = useState(null);
  const [compare, setCompare] = useState(null);
  const abortRef = useRef(null);

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify({ selected, topK }));
    } catch {
      /* storage unavailable */
    }
  }, [selected, topK]);

  useEffect(() => {
    if (!loading) return;
    const start = Date.now();
    const id = setInterval(
      () => setElapsed(Math.floor((Date.now() - start) / 1000)),
      500,
    );
    return () => clearInterval(id);
  }, [loading]);

  const run = async () => {
    if (!question.trim() || selected.length === 0) return;
    const controller = new AbortController();
    abortRef.current = controller;
    setLoading(true);
    setElapsed(0);
    setError(null);
    setSingle(null);
    setCompare(null);

    try {
      if (selected.length === 1) {
        const { chunking_strategy, retrieval_strategy } = parseKey(selected[0]);
        setSingle(
          await api.query(
            {
              question: question.trim(),
              top_k: topK,
              chunking_strategy,
              retrieval_strategy,
            },
            controller.signal,
          ),
        );
      } else {
        setCompare(
          await api.compare(
            {
              question: question.trim(),
              top_k: topK,
              strategies: selected.map(parseKey),
            },
            controller.signal,
          ),
        );
      }
    } catch (err) {
      if (err.name !== "AbortError") setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const cancel = () => abortRef.current?.abort();

  const n = selected.length;
  const canRun = question.trim().length > 0 && n > 0 && !loading;
  const runLabel =
    n === 0 ? "Pick a strategy" : n === 1 ? "Ask" : `Compare ${n} strategies`;

  return (
    <div className="page">
      <header className="page-head">
        <h1>Playground</h1>
        <p className="muted">
          Ask a question, choose how it should be retrieved, and inspect exactly
          what the model saw.
        </p>
      </header>

      <QuestionInput
        value={question}
        onChange={setQuestion}
        topK={topK}
        onTopKChange={setTopK}
        onSubmit={run}
        disabled={loading}
      />
      <StrategySelector
        selected={selected}
        onChange={setSelected}
        disabled={loading}
      />

      <div className="run-bar">
        <button
          type="button"
          className="btn btn-primary"
          onClick={run}
          disabled={!canRun}
        >
          {runLabel}
        </button>
        {loading && (
          <>
            <span className="spinner" aria-hidden />
            <span className="muted">
              Running{" "}
              {n > 1 ? `${n} strategies one after another` : "your question"}…{" "}
              {elapsed}s
              {n > 4 && " (the first run loads models, so it can take a while)"}
            </span>
            <button type="button" className="btn btn-ghost" onClick={cancel}>
              Cancel
            </button>
          </>
        )}
        {!loading && <span className="muted small">Ctrl/⌘ + Enter to run</span>}
      </div>

      {error && (
        <div className="notice notice-error">
          <b>Something went wrong.</b> {error}
        </div>
      )}

      {single && <AnswerCard result={single} />}

      {compare && (
        <>
          <ComparisonSummary data={compare} />
          <div className="compare-grid">
            {compare.results
              .filter((r) => r.result)
              .map((r) => (
                <AnswerCard key={r.strategy_name} result={r.result} compact />
              ))}
          </div>
        </>
      )}
    </div>
  );
}
