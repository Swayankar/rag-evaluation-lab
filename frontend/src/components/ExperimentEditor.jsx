import { useEffect, useMemo, useRef, useState } from "react";
import { CHUNKING, RETRIEVAL } from "../constants/strategies.js";
import { api } from "../services/api.js";

const MAX = 12;
const NAME_RE = /^[A-Za-z0-9_-]+$/;
const RESERVED = new Set(["comparison_latest", "overview", "configs", "run"]);
const TOP_KS = [1, 3, 5, 8, 10, 15, 20];

const strip = (e) => ({
  name: e.name,
  chunking_strategy: e.chunking_strategy,
  retrieval_strategy: e.retrieval_strategy,
  top_k: Number(e.top_k),
});
let counter = 0;
const withKey = (e) => ({ ...strip(e), _key: `e${counter++}` });

function problemsFor(draft) {
  const out = {};
  const seen = new Map();
  draft.forEach((e) => {
    const name = e.name.trim();
    if (!name) out[e._key] = "Give it a name.";
    else if (!NAME_RE.test(name))
      out[e._key] = "Use letters, numbers, _ and - only.";
    else if (RESERVED.has(name)) out[e._key] = `"${name}" is reserved.`;
    else if (seen.has(name))
      out[e._key] = "Another experiment already has this name.";
    seen.set(name, true);
  });
  return out;
}

export default function ExperimentEditor({ initial, onSaved, locked }) {
  const [draft, setDraft] = useState(() => initial.experiments.map(withKey));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [savedAt, setSavedAt] = useState(null);
  const baseline = useRef(JSON.stringify(initial.experiments.map(strip)));

  useEffect(() => {
    setDraft(initial.experiments.map(withKey));
    baseline.current = JSON.stringify(initial.experiments.map(strip));
  }, [initial]);

  const problems = useMemo(() => problemsFor(draft), [draft]);
  const invalid = Object.keys(problems).length > 0 || draft.length === 0;
  const dirty =
    JSON.stringify(draft.map((e) => strip({ ...e, name: e.name.trim() }))) !==
    baseline.current;
  const canSave =
    !invalid && !locked && !saving && (dirty || !initial.from_files);

  const update = (key, patch) =>
    setDraft((d) => d.map((e) => (e._key === key ? { ...e, ...patch } : e)));
  const remove = (key) => setDraft((d) => d.filter((e) => e._key !== key));
  const add = () =>
    setDraft((d) => {
      let i = d.length + 1;
      while (d.some((e) => e.name === `experiment_${i}`)) i += 1;
      return [
        ...d,
        withKey({
          name: `experiment_${i}`,
          chunking_strategy: "fixed",
          retrieval_strategy: "bm25",
          top_k: 5,
        }),
      ];
    });

  const save = async () => {
    setSaving(true);
    setError(null);
    try {
      await api.saveExperimentConfigs(
        draft.map((e) => strip({ ...e, name: e.name.trim() })),
      );
      setSavedAt(new Date());
      await onSaved();
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="card">
      <div className="summary-head">
        <div>
          <div className="field-label">Experiment definitions</div>
          <div className="muted small">
            Each row is one experiment: a chunking strategy, a retrieval
            strategy and a top-K. Saving writes{" "}
            <span className="mono">experiment_001.json …</span> in{" "}
            <span className="mono">{initial.directory}</span>, the same files
            the command-line script reads.
          </div>
        </div>
        <div className="presets">
          <button
            type="button"
            className="btn btn-ghost"
            disabled={locked}
            onClick={() => setDraft(initial.canonical.map(withKey))}
          >
            Restore the 5 canonical
          </button>
        </div>
      </div>

      {!initial.from_files && (
        <div className="notice notice-ok" style={{ marginBottom: 12 }}>
          No experiment files exist yet, so these are the built-in five. Save to
          write them to disk, or edit them first.
        </div>
      )}
      {initial.problems.map((p) => (
        <div key={p} className="notice notice-warn" style={{ marginBottom: 8 }}>
          Skipped an unreadable file — {p}
        </div>
      ))}

      <div className="table-wrap">
        <table className="table">
          <thead>
            <tr>
              <th>#</th>
              <th>Name</th>
              <th>Chunking</th>
              <th>Retrieval</th>
              <th>Top-K</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {draft.map((e, i) => (
              <tr key={e._key}>
                <td className="muted mono">{i + 1}</td>
                <td>
                  <input
                    className="text-input"
                    style={{ minWidth: 300 }}
                    value={e.name}
                    disabled={locked}
                    aria-label={`Name of experiment ${i + 1}`}
                    onChange={(ev) => update(e._key, { name: ev.target.value })}
                  />
                  {problems[e._key] && (
                    <div className="error-text">{problems[e._key]}</div>
                  )}
                </td>
                <td>
                  <select
                    value={e.chunking_strategy}
                    disabled={locked}
                    onChange={(ev) =>
                      update(e._key, { chunking_strategy: ev.target.value })
                    }
                  >
                    {CHUNKING.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.label}
                      </option>
                    ))}
                  </select>
                </td>
                <td>
                  <select
                    value={e.retrieval_strategy}
                    disabled={locked}
                    onChange={(ev) =>
                      update(e._key, { retrieval_strategy: ev.target.value })
                    }
                  >
                    {RETRIEVAL.map((r) => (
                      <option key={r.id} value={r.id}>
                        {r.label}
                      </option>
                    ))}
                  </select>
                </td>
                <td>
                  <select
                    value={e.top_k}
                    disabled={locked}
                    onChange={(ev) =>
                      update(e._key, { top_k: Number(ev.target.value) })
                    }
                  >
                    {(TOP_KS.includes(e.top_k)
                      ? TOP_KS
                      : [...TOP_KS, e.top_k].sort((a, b) => a - b)
                    ).map((k) => (
                      <option key={k} value={k}>
                        {k}
                      </option>
                    ))}
                  </select>
                </td>
                <td>
                  <button
                    type="button"
                    className="icon-btn"
                    title="Remove this experiment"
                    disabled={locked || draft.length === 1}
                    onClick={() => remove(e._key)}
                  >
                    🗑
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="run-bar" style={{ marginTop: 14 }}>
        <button
          type="button"
          className="btn btn-secondary"
          onClick={add}
          disabled={locked || draft.length >= MAX}
        >
          + Add experiment
        </button>
        <button
          type="button"
          className="btn btn-primary"
          onClick={save}
          disabled={!canSave}
        >
          {saving
            ? "Saving…"
            : dirty || !initial.from_files
              ? "Save experiments"
              : "Saved"}
        </button>
        {dirty && <span className="warn-text">Unsaved changes</span>}
        {!dirty && savedAt && (
          <span className="ok-text small">
            Saved {savedAt.toLocaleTimeString()}
          </span>
        )}
        {locked && (
          <span className="muted small">
            Locked while a run is in progress.
          </span>
        )}
      </div>
      <div className="muted small" style={{ marginTop: 8 }}>
        Up to {MAX} experiments. Semantic experiments need the semantic index
        (Documents → Rebuild). Renaming an experiment starts a fresh result
        file; the next run rewrites the comparison.
      </div>
      {error && (
        <div className="notice notice-error" style={{ marginTop: 10 }}>
          {error}
        </div>
      )}
    </div>
  );
}
