import { useCallback, useEffect, useState } from "react";
import ResultsView from "../components/ResultsView.jsx";
import EvalRunPanel from "../components/EvalRunPanel.jsx";
import QuestionEditor from "../components/QuestionEditor.jsx";
import ReadOnly from "../components/ReadOnly.jsx";
import { useWorkspace } from "../context/WorkspaceContext.jsx";
import { api } from "../services/api.js";
import { useJob } from "../hooks/useJob.js";

export default function Evaluation() {
  const { readOnly } = useWorkspace();
  const [tab, setTab] = useState("results");
  const [results, setResults] = useState(null);
  const [questions, setQuestions] = useState(null);
  const [error, setError] = useState(null);
  const [jobId, setJobId] = useState(null);
  const [starting, setStarting] = useState(false);
  const [startError, setStartError] = useState(null);

  const loadResults = useCallback(async () => {
    try {
      setResults((await api.evalResults()).results);
      setError(null);
    } catch (err) {
      setError(err.message);
    }
  }, []);

  const loadQuestions = useCallback(async () => {
    try {
      setQuestions(await api.questions());
    } catch (err) {
      setError(err.message);
    }
  }, []);

  useEffect(() => {
    loadResults();
    loadQuestions();
    api
      .jobs("evaluation")
      .then(({ jobs }) => {
        const active = jobs.find(
          (j) => j.status === "queued" || j.status === "running",
        );
        if (active) setJobId(active.id);
      })
      .catch(() => {});
  }, [loadResults, loadQuestions]);

  const job = useJob(jobId, () => loadResults());
  const running = job && (job.status === "queued" || job.status === "running");

  const start = async (body) => {
    setStarting(true);
    setStartError(null);
    try {
      const j = await api.runEvaluation(body);
      setJobId(j.id);
    } catch (err) {
      setStartError(err.message);
    } finally {
      setStarting(false);
    }
  };

  const numQuestions = questions?.questions.length ?? 0;

  return (
    <div className="page">
      <header className="page-head">
        <h1>Evaluation</h1>
        <p className="muted">
          Measure how well each strategy retrieves, answers and stays grounded,
          then edit the questions it's tested on.
        </p>
      </header>

      {running && (
        <div className="notice notice-ok running-banner">
          <span className="spinner" aria-hidden />
          <span>
            Evaluation running — {Math.round((job.progress ?? 0) * 100)}% ·{" "}
            {job.message}
          </span>
          {tab !== "run" && (
            <button
              type="button"
              className="link"
              onClick={() => setTab("run")}
            >
              View
            </button>
          )}
        </div>
      )}

      <div className="tabs" role="tablist">
        {[
          ["results", "Results", results?.length],
          ["run", "Run evaluation"],
          ["questions", "Questions", numQuestions || null],
        ].map(([id, label, count]) => (
          <button
            key={id}
            type="button"
            role="tab"
            aria-selected={tab === id}
            className={`tab ${tab === id ? "tab-on" : ""}`}
            onClick={() => setTab(id)}
          >
            {label}
            {count ? <span className="badge">{count}</span> : null}
          </button>
        ))}
      </div>

      {error && <div className="notice notice-error">{error}</div>}
      {startError && <div className="notice notice-error">{startError}</div>}

      {tab === "results" && results && (
        <ResultsView
          results={results}
          onGoRun={() => setTab("run")}
          onDelete={
            readOnly
              ? undefined
              : async (name) => {
                  await api.deleteEvalResult(name);
                  loadResults();
                }
          }
        />
      )}

      {tab === "run" && questions && (
        <ReadOnly>
          <EvalRunPanel
            numQuestions={numQuestions}
            job={job}
            onStart={start}
            starting={starting}
            onGoQuestions={() => setTab("questions")}
          />
        </ReadOnly>
      )}

      {questions && (
        <div hidden={tab !== "questions"}>
          <ReadOnly>
            <QuestionEditor
              initial={questions}
              onSaved={() => {
                loadQuestions();
                loadResults();
              }}
            />
          </ReadOnly>
        </div>
      )}

      {(!results || !questions) && !error && (
        <div className="run-bar">
          <span className="spinner" /> <span className="muted">Loading…</span>
        </div>
      )}
    </div>
  );
}
