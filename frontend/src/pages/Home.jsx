import { Link } from "react-router-dom";
import {
  BackendStatus,
  QuickStart,
  StatusTiles,
} from "../components/LabStatus.jsx";
import HowItWorks from "../components/HowItWorks.jsx";
import StrategyGuide from "../components/StrategyGuide.jsx";
import MetricGuide from "../components/MetricGuide.jsx";
import { useLabStatus } from "../hooks/useLabStatus.js";
import { useBackendStatus } from "../hooks/useBackendStatus.js";

const SECTIONS = [
  ["status", "Your lab"],
  ["how", "How it works"],
  ["strategies", "Strategies"],
  ["metrics", "Metrics"],
];

function Section({ id, title, intro, children }) {
  return (
    <section id={id} className="home-section" aria-labelledby={`${id}-h`}>
      <h2 id={`${id}-h`}>{title}</h2>
      {intro && <p className="muted home-intro">{intro}</p>}
      {children}
    </section>
  );
}

export default function Home() {
  const status = useLabStatus();
  const backend = useBackendStatus();

  return (
    <div className="page home">
      <header className="hero">
        <span className="eyebrow">RAG Evaluation Lab</span>
        <h1>Compare RAG strategies, with evidence.</h1>
        <p className="muted hero-text">
          Ask questions over your own documents, switch how they are chunked and
          searched, and measure which combination really answers best, instead
          of guessing from a few examples.
        </p>
        <div className="hero-actions">
          <Link to="/playground" className="btn btn-primary">
            Open the Playground →
          </Link>
          <Link to="/experiments" className="btn btn-secondary">
            See the experiments
          </Link>
        </div>
        <nav className="home-nav" aria-label="On this page">
          {SECTIONS.map(([id, label]) => (
            <a key={id} href={`#${id}`} className="home-nav-link">
              {label}
            </a>
          ))}
        </nav>
      </header>

      <Section
        id="status"
        title="Your lab right now"
        intro="Live from the backend. Click a tile to go to the page where you change it."
      >
        <BackendStatus status={backend.status} />

        {backend.status === "checking" ? (
          <div className="run-bar">
            <span className="spinner" />
            <span className="muted">Checking backend…</span>
          </div>
        ) : backend.status === "starting" ? (
          <div className="notice notice-warn">
            <div>
              <strong>Backend is starting…</strong>

              <div className="muted small" style={{ marginTop: 4 }}>
                The RAG backend is waking up. This can take a little while on
                the free hosting tier.
              </div>
            </div>

            <button type="button" className="link" onClick={backend.check}>
              Check again
            </button>
          </div>
        ) : status.offline ? (
          <div className="notice notice-error">
            Can't reach the API. Start the backend (
            <span className="mono">
              uvicorn app.main:app --reload --port 8000
            </span>{" "}
            in <span className="mono">backend/</span>) and{" "}
            <button type="button" className="link" onClick={status.reload}>
              try again
            </button>
            . The explanations below still work without it.
          </div>
        ) : (
          <div className="page" style={{ gap: 16 }}>
            <StatusTiles status={status} />
            <QuickStart status={status} />
          </div>
        )}
      </Section>

      <Section
        id="how"
        title="How it works"
        intro="Three stages: prepare the documents once, answer each question from the best-matching passages, then score the answers. Click a step, or walk through with Next."
      >
        <HowItWorks config={status.config} />
      </Section>

      <Section
        id="strategies"
        title="The strategies being compared"
        intro="Two ways to cut documents up and four ways to search them. Every combination is a different experiment."
      >
        <StrategyGuide config={status.config} />
      </Section>

      <Section
        id="metrics"
        title="What gets measured"
        intro="Retrieval, answer quality, grounding and cost, each answering a different question about how well a setup works."
      >
        <MetricGuide />
      </Section>
    </div>
  );
}
