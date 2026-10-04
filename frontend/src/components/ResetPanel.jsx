import { useState } from "react";

export default function ResetPanel({
  onReset,
  disabled,
  documentCount = null,
}) {
  const [open, setOpen] = useState(false);
  const [typed, setTyped] = useState("");
  const [keepFolders, setKeepFolders] = useState(false);
  const [clearQuestions, setClearQuestions] = useState(false);
  const [clearResults, setClearResults] = useState(false);
  const [clearExperiments, setClearExperiments] = useState(false);
  const [busy, setBusy] = useState(false);
  const [outcome, setOutcome] = useState(null);
  const [error, setError] = useState(null);

  const confirm = async () => {
    setBusy(true);
    setError(null);
    try {
      const res = await onReset({
        confirm: "RESET",
        keep_folders: keepFolders,
        clear_questions: clearQuestions,
        clear_results: clearResults,
        clear_experiments: clearExperiments,
      });
      setOutcome(res);
      setOpen(false);
      setTyped("");
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="card danger-zone">
      <div className="summary-head">
        <div>
          <div className="field-label">Start over</div>
          <div className="muted small">
            Remove every document and folder and clear the search index, so you
            can load a different dataset from scratch.
          </div>
        </div>
        {!open && (
          <button
            type="button"
            className="btn btn-danger"
            onClick={() => setOpen(true)}
            disabled={disabled}
          >
            Reset library…
          </button>
        )}
      </div>

      {outcome && (
        <div className="notice notice-ok">
          Removed {outcome.deleted_documents} document(s) and{" "}
          {outcome.deleted_folders} folder(s)
          {outcome.cleared.length > 0 &&
            `, and also cleared: ${outcome.cleared.join(", ")}`}
          . Upload your new documents above, then rebuild the index.
        </div>
      )}

      {open && (
        <div className="reset-confirm">
          <div className="notice notice-error">
            This permanently deletes{" "}
            {documentCount === null
              ? "all uploaded PDFs"
              : `all ${documentCount} uploaded PDF(s)`}{" "}
            and the built index. It can't be undone.
          </div>
          <label className="check">
            <input
              type="checkbox"
              checked={keepFolders}
              onChange={(e) => setKeepFolders(e.target.checked)}
            />
            Keep the (empty) folders so I can reuse the same structure
          </label>
          <label className="check">
            <input
              type="checkbox"
              checked={clearQuestions}
              onChange={(e) => setClearQuestions(e.target.checked)}
            />
            Also delete the evaluation questions (they refer to the old
            documents)
          </label>
          <label className="check">
            <input
              type="checkbox"
              checked={clearResults}
              onChange={(e) => setClearResults(e.target.checked)}
            />
            Also delete saved evaluation results
          </label>
          <label className="check">
            <input
              type="checkbox"
              checked={clearExperiments}
              onChange={(e) => setClearExperiments(e.target.checked)}
            />
            Also delete experiment results and the saved comparison (your
            experiment definitions are kept)
          </label>
          <div className="muted small">
            Type <b className="mono">RESET</b> to confirm:
          </div>
          <div className="folder-form">
            <input
              className="text-input"
              value={typed}
              onChange={(e) => setTyped(e.target.value)}
              placeholder="RESET"
              autoFocus
            />
            <button
              type="button"
              className="btn btn-danger"
              disabled={typed !== "RESET" || busy}
              onClick={confirm}
            >
              {busy ? "Resetting…" : "Delete everything"}
            </button>
            <button
              type="button"
              className="btn btn-ghost"
              onClick={() => setOpen(false)}
              disabled={busy}
            >
              Cancel
            </button>
          </div>
          {error && <div className="notice notice-error">{error}</div>}
        </div>
      )}
    </div>
  );
}
