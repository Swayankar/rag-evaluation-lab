import { Link } from "react-router-dom";
import { describeExperiments } from "../utils/experimentMeta.js";

function indexState(index) {
  if (!index) return { text: "—", tone: "" };
  if (!index.fixed_built) return { text: "○ Not built", tone: "tone-warn" };
  if (index.stale) return { text: "⚠ Out of date", tone: "tone-warn" };
  return { text: "✓ Up to date", tone: "tone-ok" };
}

export function StatusTiles({ status }) {
  const { library, questions, evalRuns, overview } = status;
  const rec = overview?.recommendation;
  const recLabel = rec
    ? describeExperiments([rec.name]).get(rec.name).label
    : null;
  const idx = indexState(library?.index);
  const latestRun = evalRuns?.length
    ? new Date(
        Math.max(
          ...evalRuns.map((r) => Date.parse(r.meta?.ran_at ?? r.modified)),
        ),
      ).toLocaleDateString()
    : null;

  const tiles = [
    {
      to: "/documents",
      label: "Documents",
      value: library ? library.total_documents : "—",
      sub: library
        ? `${library.departments.length} folder${library.departments.length === 1 ? "" : "s"}`
        : "unavailable",
    },
    {
      to: "/documents",
      label: "Search index",
      value: idx.text,
      tone: idx.tone,
      small: true,
      sub: library?.index?.fixed_built
        ? `${library.index.total_chunks} chunks · semantic ${library.index.semantic_built ? "built" : "not built"}`
        : "build it on Documents",
    },
    {
      to: "/evaluation",
      label: "Questions",
      value: questions ? questions.questions.length : "—",
      sub: questions?.exists ? "in questions.json" : "none yet",
    },
    {
      to: "/evaluation",
      label: "Evaluation runs",
      value: evalRuns ? evalRuns.length : "—",
      sub: latestRun ? `latest ${latestRun}` : "none saved yet",
    },
    {
      to: "/experiments",
      label: "Top experiment",
      value: recLabel ?? "—",
      small: Boolean(recLabel),
      sub: rec
        ? `best on ${rec.wins} of ${rec.total_metrics} metrics`
        : "run experiments to find out",
    },
  ];

  return (
    <div className="tiles">
      {tiles.map((t) => (
        <Link key={t.label} to={t.to} className="tile tile-link">
          <div className="tile-label">{t.label}</div>
          <div
            className={`tile-value ${t.small ? "tile-value-sm" : ""} ${t.tone ?? ""}`}
          >
            {t.value}
          </div>
          <div className="tile-sub">{t.sub}</div>
        </Link>
      ))}
    </div>
  );
}

export function QuickStart({ status }) {
  const { library, questions, overview } = status;
  const docs = library?.total_documents ?? 0;
  const indexOk =
    Boolean(library?.index?.fixed_built) && !library?.index?.stale;
  const hasQuestions = (questions?.questions.length ?? 0) > 0;
  const hasComparison = Boolean(overview?.comparison);

  const steps = [
    {
      id: "docs",
      done: docs > 0,
      title: "Add your documents",
      text: "Upload PDFs into department folders.",
      to: "/documents",
      cta: "Open Documents",
    },
    {
      id: "index",
      done: indexOk,
      title: "Build the search index",
      text:
        library?.index?.fixed_built && library?.index?.stale
          ? "Your documents changed since the last build."
          : "Chunks and embeds your PDFs (fixed and semantic).",
      to: "/documents",
      cta: "Rebuild index",
    },
    {
      id: "questions",
      done: hasQuestions,
      title: "Write evaluation questions",
      text: "Questions with the documents that should answer them.",
      to: "/evaluation",
      cta: "Open Evaluation",
    },
    {
      id: "experiments",
      done: hasComparison,
      title: "Run the experiments",
      text: "Every strategy answers every question.",
      to: "/experiments",
      cta: "Open Experiments",
    },
    {
      id: "read",
      done: false,
      title: "Read the recommendation",
      text: overview?.recommendation
        ? "See which setup won and where it's weak."
        : "Appears once an experiment run finishes.",
      to: "/experiments",
      cta: "See results",
      always: true,
    },
  ];
  const nextIdx = steps.findIndex((s) => !s.done && !s.always);
  const allDone = nextIdx === -1;

  return (
    <div className="card">
      <div className="summary-head">
        <div>
          <div className="field-label">Quick start</div>
          <div className="muted small">
            {allDone
              ? "You're set up. Re-run experiments whenever your documents or questions change."
              : "Follow these in order. The highlighted step is next."}
          </div>
        </div>
      </div>
      <ol className="steps">
        {steps.map((s, i) => {
          const state = s.done ? "done" : i === nextIdx ? "next" : "todo";
          return (
            <li key={s.id} className={`step step-${state}`}>
              <span className="step-mark" aria-hidden>
                {s.done ? "✓" : i + 1}
              </span>
              <div className="step-body">
                <div className="step-title">
                  {s.title}
                  {state === "done" && <span className="sr-only"> (done)</span>}
                  {state === "next" && (
                    <span className="badge badge-ok" style={{ marginLeft: 8 }}>
                      Next
                    </span>
                  )}
                </div>
                <div className="muted small">{s.text}</div>
              </div>
              <Link
                to={s.to}
                className={`btn ${state === "next" ? "btn-primary" : "btn-ghost"}`}
              >
                {s.cta}
              </Link>
            </li>
          );
        })}
      </ol>
    </div>
  );
}

export function BackendStatus({ status }) {
  const config = {
    checking: {
      label: "Checking backend",
      className: "backend-status-checking",
    },
    starting: {
      label: "Backend starting",
      className: "backend-status-starting",
    },
    online: {
      label: "Backend online",
      className: "backend-status-online",
    },
  };

  const current = config[status] ?? config.checking;

  return (
    <div className={`backend-status ${current.className}`}>
      <span className="backend-status-dot" />
      {current.label}
    </div>
  );
}
