import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import EvaluationChart from "../charts/EvaluationChart.jsx";
import WinsChart from "../charts/WinsChart.jsx";
import RecommendationCard from "../components/RecommendationCard.jsx";
import ExperimentTable from "../components/ExperimentTable.jsx";
import ExperimentRunPanel from "../components/ExperimentRunPanel.jsx";
import ExperimentEditor from "../components/ExperimentEditor.jsx";
import ReadOnly from "../components/ReadOnly.jsx";
import QuestionHeatmap from "../components/QuestionHeatmap.jsx";
import { api } from "../services/api.js";
import { useJob } from "../hooks/useJob.js";
import { downloadCsv } from "../utils/csv.js";
import { CHART_GROUPS, TILE_METRICS, bestBy } from "../utils/evalMetrics.js";
import {
  comparisonCsv,
  describeExperiments,
  metricsWon,
  rowsFromComparison,
} from "../utils/experimentMeta.js";

const PER_QUESTION_COLUMNS = [
  "experiment",
  "question_id",
  "question",
  "recall_at_k",
  "precision_at_k",
  "mrr",
  "citation_accuracy",
  "correctness",
  "relevance",
  "completeness",
  "faithfulness",
  "likely_hallucination",
  "latency_ms",
  "answer",
  "error",
];

export default function Experiments() {
  const navigate = useNavigate();
  const [tab, setTab] = useState(null);
  const [overview, setOverview] = useState(null);
  const [configs, setConfigs] = useState(null);
  const [numQuestions, setNumQuestions] = useState(null);
  const [details, setDetails] = useState({});
  const [error, setError] = useState(null);
  const [jobId, setJobId] = useState(null);
  const [starting, setStarting] = useState(false);
  const [startError, setStartError] = useState(null);

  const loadOverview = useCallback(async () => {
    try {
      setOverview(await api.experimentsOverview());
      setError(null);
    } catch (err) {
      setError(err.message);
    }
  }, []);
  const loadConfigs = useCallback(async () => {
    try {
      setConfigs(await api.experimentConfigs());
    } catch (err) {
      setError(err.message);
    }
  }, []);

  useEffect(() => {
    loadOverview();
    loadConfigs();
    api
      .questions()
      .then((q) => setNumQuestions(q.questions.length))
      .catch((err) => setError(err.message));
    api
      .jobs("experiments")
      .then(({ jobs }) => {
        const active = jobs.find(
          (j) => j.status === "queued" || j.status === "running",
        );
        if (active) setJobId(active.id);
      })
      .catch(() => {});
  }, [loadOverview, loadConfigs]);

  const comparison = overview?.comparison ?? null;
  const stamp = comparison
    ? `${comparison.meta?.ran_at ?? ""}|${comparison.experiments.join(",")}`
    : "";

  useEffect(() => {
    setDetails({});
    if (!comparison) return;
    let cancelled = false;
    comparison.experiments.forEach((name) =>
      api
        .experimentDetail(name)
        .then(
          (d) => !cancelled && setDetails((prev) => ({ ...prev, [name]: d })),
        )
        .catch(() => {}),
    );
    return () => {
      cancelled = true;
    };
  }, [stamp]);

  const loaded = overview && configs && numQuestions !== null;
  useEffect(() => {
    if (loaded && tab === null) setTab(comparison ? "comparison" : "run");
  }, [loaded, tab, comparison]);

  const job = useJob(jobId, () => {
    loadOverview();
  });
  const running = Boolean(
    job && (job.status === "queued" || job.status === "running"),
  );

  const start = async (body) => {
    setStarting(true);
    setStartError(null);
    try {
      const j = await api.runExperiments(body);
      setJobId(j.id);
    } catch (err) {
      setStartError(err.message);
    } finally {
      setStarting(false);
    }
  };

  const names = comparison?.experiments ?? [];
  const meta = useMemo(
    () => describeExperiments(names, configs?.experiments ?? [], details),
    [names.join(","), configs, details],
  );
  const labelOf = (n) => meta.get(n)?.label ?? n;
  const rows = useMemo(
    () => rowsFromComparison(comparison, meta),
    [comparison, meta],
  );
  const won = useMemo(
    () => (comparison ? metricsWon(comparison) : {}),
    [comparison],
  );

  const fallbackRuns = names.filter(
    (n) => details[n]?.meta?.embedder === "HashingEmbedder",
  );
  const noopRerank = names.filter(
    (n) => details[n]?.meta?.reranker === "NoOpReranker",
  );
  const skipped = Object.entries(comparison?.skipped ?? {});

  const exportComparison = () => {
    const { rows: csvRows, columns } = comparisonCsv(comparison, meta);
    downloadCsv("experiments-comparison.csv", csvRows, columns);
  };
  const exportPerQuestion = () => {
    const out = [];
    names.forEach((n) =>
      (details[n]?.results ?? []).forEach((q) =>
        out.push({
          experiment: labelOf(n),
          question_id: q.question_id,
          question: q.question,
          recall_at_k: q.retrieval?.recall_at_k,
          precision_at_k: q.retrieval?.precision_at_k,
          mrr: q.retrieval?.mrr,
          citation_accuracy: q.citation?.citation_accuracy,
          correctness: q.answer_judge?.correctness,
          relevance: q.answer_judge?.relevance,
          completeness: q.answer_judge?.completeness,
          faithfulness: q.grounding_judge?.faithfulness,
          likely_hallucination: q.grounding_judge?.likely_hallucination,
          latency_ms: q.system?.latency_ms,
          answer: q.answer,
          error: q.error ?? q.judge_error,
        }),
      ),
    );
    downloadCsv("experiments-per-question.csv", out, PER_QUESTION_COLUMNS);
  };

  return (
    <div className="page">
      <header className="page-head">
        <h1>Experiments</h1>
        <p className="muted">
          Run the same questions through several chunking × retrieval setups,
          compare them side by side, and see which one the numbers favour.
        </p>
      </header>

      {running && (
        <div className="notice notice-ok running-banner">
          <span className="spinner" aria-hidden />
          <span>
            Experiments running — {Math.round((job.progress ?? 0) * 100)}% ·{" "}
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

      {error && <div className="notice notice-error">{error}</div>}
      {startError && <div className="notice notice-error">{startError}</div>}

      {!loaded && !error && (
        <div className="run-bar">
          <span className="spinner" /> <span className="muted">Loading…</span>
        </div>
      )}

      {loaded && (
        <>
          <div className="tabs" role="tablist">
            {[
              ["comparison", "Comparison", comparison?.experiments.length],
              ["run", "Run"],
              ["setup", "Experiments", configs.experiments.length],
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

          {tab === "comparison" && !comparison && (
            <div className="card empty">
              <h3>No comparison yet</h3>
              <p className="muted">
                Run the experiments to see how the strategies stack up.
              </p>
              <button
                type="button"
                className="btn btn-primary"
                onClick={() => setTab("run")}
                style={{ marginTop: 12 }}
              >
                Run experiments
              </button>
            </div>
          )}

          {tab === "comparison" && comparison && (
            <div className="page" style={{ gap: 16 }}>
              {overview.dataset_match === false && (
                <div className="notice notice-warn">
                  ⚠ This comparison was made on an{" "}
                  <b>older version of the questions</b>. Re-run the experiments
                  so it reflects the current set.
                </div>
              )}
              {skipped.map(([name, why]) => (
                <div key={name} className="notice notice-warn">
                  ⚠ <b>{name}</b> wasn't part of this comparison: {why}
                </div>
              ))}
              {fallbackRuns.length > 0 && (
                <div className="notice notice-warn">
                  ⚠ {fallbackRuns.map(labelOf).join(", ")} used the{" "}
                  <b>HashingEmbedder fallback</b>, not real embeddings, so their
                  retrieval scores don't reflect real semantic search quality.
                </div>
              )}
              {noopRerank.length > 0 && (
                <div className="notice notice-warn">
                  ⚠ {noopRerank.map(labelOf).join(", ")} ran with the no-op
                  reranker fallback, so it behaved like plain hybrid.
                </div>
              )}

              <RecommendationCard
                rec={overview.recommendation}
                labelOf={labelOf}
                stale={overview.dataset_match === false}
              />

              <div className="tiles">
                {TILE_METRICS.map((m) => {
                  const best = bestBy(rows, m.key, m.direction);
                  if (!best) return null;
                  return (
                    <div key={m.key} className="tile">
                      <div className="tile-label">{m.label}</div>
                      <div className="tile-value">
                        {best[m.key].toFixed(m.decimals)}
                        <span className="muted small">{m.suffix}</span>
                      </div>
                      <div className="tile-sub">{labelOf(best.name)}</div>
                    </div>
                  );
                })}
              </div>

              <WinsChart
                ranking={
                  overview.recommendation?.ranking ??
                  names.map((n) => ({ name: n, wins: won[n]?.length ?? 0 }))
                }
                total={comparison.metrics.length}
                won={won}
                labelOf={labelOf}
              />

              <div className="chart-grid">
                {CHART_GROUPS.map((g) => (
                  <EvaluationChart
                    key={g.id}
                    title={g.title}
                    subtitle={g.subtitle}
                    rows={rows}
                    series={g.series}
                    domain={g.domain}
                    decimals={g.decimals}
                    labelOf={labelOf}
                  />
                ))}
              </div>

              <div className="card">
                <div className="summary-head">
                  <div>
                    <div className="field-label">Full comparison</div>
                    <div className="muted small">
                      ★ marks the best value on each metric (↑ higher is better,
                      ↓ lower is better).
                      {comparison.meta?.ran_at &&
                        ` Run ${new Date(comparison.meta.ran_at).toLocaleString()}`}
                      {comparison.meta?.num_questions != null &&
                        ` on ${comparison.meta.num_questions} question(s)`}
                      {comparison.meta?.llm_judges === false &&
                        " · LLM judges off"}
                      .
                    </div>
                  </div>
                  <div className="presets">
                    <button
                      type="button"
                      className="btn btn-secondary"
                      onClick={exportComparison}
                    >
                      Export comparison CSV
                    </button>
                    <button
                      type="button"
                      className="btn btn-secondary"
                      onClick={exportPerQuestion}
                      disabled={names.some((n) => !details[n])}
                      title={
                        names.some((n) => !details[n])
                          ? "Per-question detail is still loading or missing"
                          : undefined
                      }
                    >
                      Export per-question CSV
                    </button>
                  </div>
                </div>
                <ExperimentTable comparison={comparison} labelOf={labelOf} />
              </div>

              <QuestionHeatmap
                names={names}
                details={details}
                labelOf={labelOf}
              />
            </div>
          )}

          {tab === "run" && (
            <ReadOnly>
              <ExperimentRunPanel
                configs={configs.experiments}
                numQuestions={numQuestions}
                job={job}
                onStart={start}
                starting={starting}
                hasComparison={Boolean(comparison)}
                onGoSetup={() => setTab("setup")}
                onGoQuestions={() => navigate("/evaluation")}
              />
            </ReadOnly>
          )}

          {/* Always mounted (just hidden) so unsaved edits survive switching tabs. */}
          <div hidden={tab !== "setup"}>
            <ReadOnly>
              <ExperimentEditor
                initial={configs}
                locked={running}
                onSaved={async () => {
                  await loadConfigs();
                  await loadOverview();
                }}
              />
            </ReadOnly>
          </div>
        </>
      )}
    </div>
  );
}
