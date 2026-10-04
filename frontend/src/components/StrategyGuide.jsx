import {
  CHUNKING_INFO,
  EXPERIMENT_PLAN,
  RETRIEVAL_INFO,
} from "../constants/learn.js";

function InfoCard({ item, config }) {
  const fill = (t) =>
    t
      .replace("{fixed}", config?.chunking?.fixed_chunk_size ?? 500)
      .replace("{overlap}", config?.chunking?.fixed_chunk_overlap ?? 50);
  return (
    <div className="card info-card">
      <div className="info-head">
        <h3>{item.title}</h3>
        {item.tag && <span className="badge">{item.tag}</span>}
      </div>
      <p className="muted">{fill(item.how)}</p>
      <div className="info-row">
        <span className="info-key info-good">Good at</span>
        <span>{item.good}</span>
      </div>
      <div className="info-row">
        <span className="info-key info-watch">Watch out</span>
        <span>{item.watch}</span>
      </div>
    </div>
  );
}

export default function StrategyGuide({ config }) {
  return (
    <div className="page" style={{ gap: 16 }}>
      <div>
        <div className="field-label" style={{ marginBottom: 8 }}>
          Chunking: how documents are cut up
        </div>
        <div className="info-grid info-grid-2">
          {CHUNKING_INFO.map((c) => (
            <InfoCard key={c.id} item={c} config={config} />
          ))}
        </div>
      </div>

      <div>
        <div className="field-label" style={{ marginBottom: 8 }}>
          Retrieval: how the right chunks are found
        </div>
        <div className="info-grid">
          {RETRIEVAL_INFO.map((r) => (
            <InfoCard key={r.id} item={r} config={config} />
          ))}
        </div>
      </div>

      <div className="card">
        <div className="field-label">The five default experiments</div>
        <div className="muted small" style={{ marginBottom: 10 }}>
          Chosen so that each one changes a single thing, which makes the
          comparison easy to read. You can edit them on the Experiments page.
        </div>
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>#</th>
                <th>Setup</th>
                <th>What it tells you</th>
              </tr>
            </thead>
            <tbody>
              {EXPERIMENT_PLAN.map((e) => (
                <tr key={e.n}>
                  <td className="mono muted">{e.n}</td>
                  <td>{e.combo}</td>
                  <td className="muted">{e.asks}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
