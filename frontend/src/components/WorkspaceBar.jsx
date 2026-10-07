import { useState } from "react";
import { MODEL_RE, resumeLink } from "../services/workspace.js";
import { useWorkspace } from "../context/WorkspaceContext.jsx";

export default function WorkspaceBar() {
  const ws = useWorkspace();
  const [panel, setPanel] = useState(null); // "start" | "key" | null
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState(null);
  const [copied, setCopied] = useState(false);
  const [keyDraft, setKeyDraft] = useState("");
  const [customModel, setCustomModel] = useState("");
  const [remember, setRemember] = useState(ws.keyRemembered);

  if (!ws.info && !ws.notice) return null;

  const info = ws.info;
  const act = async (fn) => {
    setBusy(true);
    setProblem(null);
    try {
      await fn();
      setPanel(null);
    } catch (err) {
      setProblem(err.message);
    } finally {
      setBusy(false);
    }
  };

  const copyLink = async () => {
    try {
      await navigator.clipboard.writeText(resumeLink(ws.id));
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      window.prompt(
        "Copy this link to resume your workspace on another device:",
        resumeLink(ws.id),
      );
    }
  };

  const expiry =
    info?.expires_in_days != null
      ? Math.max(0, Math.ceil(info.expires_in_days))
      : null;
  const canUseLlm = info?.key?.can_use_llm;
  const local = Boolean(info) && !ws.hosted && !ws.isPrivate;
  const model = info?.model;
  const isListed = model?.options.includes(model.current);
  const applyCustomModel = () => {
    const name = customModel.trim();
    if (!name) return;
    if (!MODEL_RE.test(name)) {
      setProblem(
        "Model names can only use letters, numbers and . _ : / - (for example llama-3.3-70b-versatile).",
      );
      return;
    }
    setProblem(null);
    ws.chooseModel(name === model.default ? "" : name);
    setCustomModel("");
    setPanel(null);
  };

  return (
    <div className="wsbar" role="region" aria-label="Workspace">
      {ws.notice && (
        <div className="notice notice-warn wsbar-notice">
          {ws.notice}{" "}
          <button type="button" className="link" onClick={ws.dismissNotice}>
            Dismiss
          </button>
        </div>
      )}

      {info && (
        <div className="wsbar-row">
          <div className="wsbar-state">
            {local ? (
              <span className="muted small">
                Using your local files and the server's Groq key.
              </span>
            ) : ws.isPrivate ? (
              <>
                <span className="chip chip-ok">✎ Your private workspace</span>
                <span className="muted small">
                  Only reachable from this browser or your resume link
                  {expiry != null &&
                    ` · deleted after ${info.ttl_days} idle days (about ${expiry} left)`}
                  {info.limits &&
                    ` · ${info.usage.documents}/${info.limits.documents} documents`}
                </span>
              </>
            ) : (
              <>
                <span className="chip">
                  {info.read_only
                    ? "🔒 Sample workspace · read-only"
                    : "Local workspace"}
                </span>
                <span className="muted small">
                  {info.read_only
                    ? "Everyone sees the same sample results. Start your own workspace to try your documents."
                    : "These are your local files."}
                </span>
              </>
            )}
          </div>

          <div className="wsbar-actions">
            {model && (
              <button
                type="button"
                className="chip chip-btn"
                onClick={() => setPanel(panel === "model" ? null : "model")}
                title="Which Groq model answers questions and judges answers"
              >
                🧠 {model.current}
                {!isListed && " · custom"}
              </button>
            )}
            {!local && (
              <button
                type="button"
                className={`chip chip-btn ${canUseLlm ? "chip-ok" : "chip-warn"}`}
                onClick={() => setPanel(panel === "key" ? null : "key")}
              >
                {ws.hasKey
                  ? "🔑 Using your Groq key"
                  : canUseLlm
                    ? "🔑 Server key"
                    : "🔑 Add Groq key"}
              </button>
            )}
            {ws.isPrivate ? (
              <>
                <button
                  type="button"
                  className="chip chip-btn"
                  onClick={copyLink}
                >
                  {copied ? "Copied ✓" : "Copy resume link"}
                </button>
                <button
                  type="button"
                  className="chip chip-btn"
                  onClick={ws.useSample}
                >
                  View sample
                </button>
                <button
                  type="button"
                  className="chip chip-btn chip-danger"
                  disabled={busy}
                  onClick={() =>
                    window.confirm(
                      "Delete your private workspace and everything in it (documents, index, questions, results)? This can't be undone.",
                    ) && act(ws.deleteWorkspace)
                  }
                >
                  Delete workspace
                </button>
              </>
            ) : (
              ws.hosted && (
                <button
                  type="button"
                  className="btn btn-primary btn-sm"
                  onClick={() => setPanel(panel === "start" ? null : "start")}
                >
                  Start my own workspace
                </button>
              )
            )}
          </div>
        </div>
      )}

      {problem && (
        <div className="notice notice-error wsbar-notice">{problem}</div>
      )}

      {panel === "start" && (
        <div className="card wsbar-panel">
          <div className="field-label">Start a private workspace</div>
          <p className="muted small">
            You get your own folders, search index, questions, results and
            experiments. Nothing you do there changes the sample or anyone
            else's work, and it survives refreshes and closing the tab.
          </p>
          <div className="wsbar-choices">
            <button
              type="button"
              className="btn btn-primary"
              disabled={busy}
              onClick={() => act(() => ws.startWorkspace(false))}
            >
              Start empty
            </button>
            <button
              type="button"
              className="btn btn-secondary"
              disabled={busy}
              onClick={() => act(() => ws.startWorkspace(true))}
            >
              Start from a copy of the sample
            </button>
            <button
              type="button"
              className="btn btn-ghost"
              onClick={() => setPanel(null)}
            >
              Cancel
            </button>
          </div>
          <p className="muted small">
            ⚠ Uploaded PDFs are stored on this server (in your workspace only)
            and deleted after {info?.ttl_days ?? 7} idle days. Don't upload
            anything confidential.
          </p>
        </div>
      )}

      {panel === "model" && model && (
        <div className="card wsbar-panel">
          <div className="field-label">Language model</div>
          <p className="muted small">
            Used to write answers and to judge them during evaluations. It's
            remembered in this browser. Results record which model made them, so
            re-run an evaluation after switching if you want to compare models
            fairly.
          </p>
          <div className="wsbar-choices" role="radiogroup" aria-label="Model">
            {model.options.map((m) => (
              <button
                key={m}
                type="button"
                role="radio"
                aria-checked={model.current === m}
                className={`chip chip-btn ${model.current === m ? "chip-ok" : ""}`}
                onClick={() => {
                  ws.chooseModel(m === model.default ? "" : m);
                  setPanel(null);
                }}
              >
                {model.current === m ? "✓ " : ""}
                {m}
                {m === model.default && " (default)"}
              </button>
            ))}
          </div>
          {model.custom_allowed ? (
            <form
              className="wsbar-choices"
              onSubmit={(e) => {
                e.preventDefault();
                applyCustomModel();
              }}
            >
              <input
                className="text-input"
                placeholder={
                  !isListed
                    ? `Custom: ${model.current}`
                    : "Or type any Groq model name, e.g. qwen/qwen3-32b"
                }
                value={customModel}
                onChange={(e) => setCustomModel(e.target.value)}
                aria-label="Custom model name"
                spellCheck={false}
              />
              <button
                type="submit"
                className="btn btn-secondary"
                disabled={!customModel.trim()}
              >
                Use this model
              </button>
            </form>
          ) : (
            <p className="muted small">
              Custom model names need your own Groq key (add it with the key
              button).
            </p>
          )}
          {model.current !== model.default && (
            <div>
              <button
                type="button"
                className="btn btn-ghost"
                onClick={() => {
                  ws.chooseModel("");
                  setPanel(null);
                }}
              >
                Back to default ({model.default})
              </button>
            </div>
          )}
        </div>
      )}

      {panel === "key" && (
        <form
          className="card wsbar-panel"
          onSubmit={(e) => {
            e.preventDefault();
            if (!keyDraft.trim()) return;
            act(async () => {
              ws.saveKey(keyDraft, remember);
              setKeyDraft("");
            });
          }}
        >
          <div className="field-label">Your Groq API key</div>
          <p className="muted small">
            Needed to ask questions and run evaluations (browsing the sample
            results needs no key). Get a free one at{" "}
            <a
              href="https://console.groq.com/keys"
              target="_blank"
              rel="noreferrer"
            >
              console.groq.com/keys
            </a>
            . It stays in this browser and is sent with your requests only so
            the server can call Groq for you — the server does not store it.
          </p>
          <div className="wsbar-choices">
            <input
              className="text-input"
              type="password"
              autoComplete="off"
              spellCheck={false}
              placeholder={
                ws.hasKey
                  ? "A key is saved — paste a new one to replace it"
                  : "gsk_…"
              }
              value={keyDraft}
              onChange={(e) => setKeyDraft(e.target.value)}
              aria-label="Groq API key"
            />
            <button
              type="submit"
              className="btn btn-primary"
              disabled={!keyDraft.trim()}
            >
              Save key
            </button>
            {ws.hasKey && (
              <button
                type="button"
                className="btn btn-ghost"
                onClick={ws.clearKey}
              >
                Remove key
              </button>
            )}
          </div>
          <label className="muted small wsbar-remember">
            <input
              type="checkbox"
              checked={remember}
              onChange={(e) => setRemember(e.target.checked)}
            />{" "}
            Remember on this device (otherwise it's forgotten when you close the
            tab)
          </label>
        </form>
      )}
    </div>
  );
}
