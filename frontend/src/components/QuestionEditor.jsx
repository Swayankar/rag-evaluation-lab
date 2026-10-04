import { useMemo, useRef, useState } from "react";
import { api } from "../services/api.js";

let keySeq = 0;
const withKey = (q) => ({
  _key: ++keySeq,
  id: q.id ?? "",
  question: q.question ?? "",
  relevant_document_ids: Array.isArray(q.relevant_document_ids)
    ? q.relevant_document_ids
    : [],
  expected_answer: q.expected_answer ?? "",
  keywordsText: (q.expected_keywords ?? []).join(", "),
  category: q.category ?? "",
});

const strip = (row) => ({
  id: row.id.trim(),
  question: row.question,
  relevant_document_ids: row.relevant_document_ids,
  expected_answer: row.expected_answer || null,
  expected_keywords: row.keywordsText
    .split(",")
    .map((k) => k.trim())
    .filter(Boolean),
  category: row.category || null,
});

function DocPicker({ value, onChange, known, listId }) {
  const [text, setText] = useState("");
  const add = (id) => {
    const v = id.trim();
    if (v && !value.includes(v)) onChange([...value, v]);
    setText("");
  };
  return (
    <div>
      <div className="file-chips" style={{ marginTop: 4 }}>
        {value.map((id) => (
          <span
            key={id}
            className={`chip chip-doc ${known.includes(id) ? "" : "chip-unknown"}`}
            title={known.includes(id) ? "" : "Not in the document library"}
          >
            {id}
            <button
              type="button"
              className="chip-x"
              onClick={() => onChange(value.filter((v) => v !== id))}
            >
              ×
            </button>
          </span>
        ))}
      </div>
      <input
        className="text-input"
        style={{ marginTop: 6, width: "100%" }}
        list={listId}
        placeholder="Add a document id…"
        value={text}
        onChange={(e) =>
          known.includes(e.target.value)
            ? add(e.target.value)
            : setText(e.target.value)
        }
        onKeyDown={(e) => {
          if (e.key === "Enter") {
            e.preventDefault();
            add(text);
          }
        }}
      />
    </div>
  );
}

export default function QuestionEditor({ initial, onSaved }) {
  const known = initial.known_document_ids;
  const [rows, setRows] = useState(() => initial.questions.map(withKey));
  const [snapshot, setSnapshot] = useState(() =>
    JSON.stringify(initial.questions.map((q) => strip(withKey(q)))),
  );
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [warnings, setWarnings] = useState([]);
  const [saved, setSaved] = useState(false);
  const fileRef = useRef(null);

  const current = useMemo(() => rows.map(strip), [rows]);
  const dirty = JSON.stringify(current) !== snapshot;
  const categories = useMemo(
    () => [...new Set(rows.map((r) => r.category).filter(Boolean))],
    [rows],
  );

  const update = (key, patch) => {
    setSaved(false);
    setRows((rs) => rs.map((r) => (r._key === key ? { ...r, ...patch } : r)));
  };

  const nextId = () => {
    const nums = rows
      .map((r) => /^q(\d+)$/.exec(r.id.trim())?.[1])
      .filter(Boolean)
      .map(Number);
    return `q${(nums.length ? Math.max(...nums) : 0) + 1}`;
  };

  const add = () => {
    setSaved(false);
    setRows((rs) => [...rs, withKey({ id: nextId() })]);
  };
  const duplicate = (row) => {
    setSaved(false);
    setRows((rs) => {
      const i = rs.findIndex((r) => r._key === row._key);
      const copy = { ...row, _key: ++keySeq, id: nextId() };
      return [...rs.slice(0, i + 1), copy, ...rs.slice(i + 1)];
    });
  };
  const remove = (row) => {
    setSaved(false);
    setRows((rs) => rs.filter((r) => r._key !== row._key));
  };

  const save = async () => {
    setSaving(true);
    setError(null);
    setWarnings([]);
    try {
      const res = await api.saveQuestions(current);
      setSnapshot(JSON.stringify(current));
      setWarnings(res.warnings ?? []);
      setSaved(true);
      onSaved?.(res);
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  const revert = () => {
    setRows(initial.questions.map(withKey));
    setError(null);
    setWarnings([]);
    setSaved(false);
  };

  const exportJson = () => {
    const blob = new Blob([JSON.stringify({ questions: current }, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "questions.json";
    a.click();
    URL.revokeObjectURL(url);
  };

  const importJson = async (file) => {
    if (!file) return;
    setError(null);
    try {
      const data = JSON.parse(await file.text());
      const list = Array.isArray(data) ? data : data.questions;
      if (!Array.isArray(list))
        throw new Error(
          'Expected a JSON array or an object with a "questions" array.',
        );
      if (
        rows.length > 0 &&
        !window.confirm(
          `Replace the ${rows.length} question(s) in the editor with ${list.length} from this file? (Nothing is saved until you click Save.)`,
        )
      )
        return;
      setSaved(false);
      setRows(list.map((q, i) => withKey({ ...q, id: q.id || `q${i + 1}` })));
    } catch (err) {
      setError(`Couldn't import that file: ${err.message}`);
    } finally {
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  return (
    <div className="page" style={{ gap: 14 }}>
      <datalist id="doc-ids">
        {known.map((d) => (
          <option key={d} value={d} />
        ))}
      </datalist>
      <datalist id="categories">
        {categories.map((c) => (
          <option key={c} value={c} />
        ))}
      </datalist>

      <div className="summary-head">
        <div className="muted small" style={{ maxWidth: 640 }}>
          Ground truth is document-level: list which document(s) should answer
          each question. The reference answer is what the LLM judge scores
          correctness against. Saving changes the question-set version, so
          earlier results will be flagged as "older questions" and LangSmith
          will create a fresh dataset for the next run.
        </div>
        <div className="presets">
          <input
            ref={fileRef}
            type="file"
            accept=".json,application/json"
            hidden
            onChange={(e) => importJson(e.target.files?.[0])}
          />
          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => fileRef.current?.click()}
          >
            Import JSON
          </button>
          <button
            type="button"
            className="btn btn-secondary"
            onClick={exportJson}
            disabled={rows.length === 0}
          >
            Export JSON
          </button>
        </div>
      </div>

      {known.length === 0 && (
        <div className="notice notice-warn">
          The document library is empty, so there are no document ids to pick
          from. You can still type ids by hand.
        </div>
      )}

      {rows.length === 0 && (
        <div className="card empty">
          <h3>No questions yet</h3>
          <p className="muted">
            Add a question, or import an existing questions.json.
          </p>
        </div>
      )}

      {rows.map((row, i) => (
        <div key={row._key} className="card q-card">
          <div className="q-head">
            <span className="muted small">#{i + 1}</span>
            <input
              className="text-input id-input mono"
              value={row.id}
              onChange={(e) => update(row._key, { id: e.target.value })}
              aria-label="Question id"
            />
            <input
              className="text-input"
              style={{ maxWidth: 180 }}
              list="categories"
              placeholder="category"
              value={row.category}
              onChange={(e) => update(row._key, { category: e.target.value })}
              aria-label="Category"
            />
            <span style={{ flex: 1 }} />
            <button
              type="button"
              className="link"
              onClick={() => duplicate(row)}
            >
              Duplicate
            </button>
            <button
              type="button"
              className="link danger"
              onClick={() => remove(row)}
            >
              Delete
            </button>
          </div>
          <div className="q-grid">
            <label className="q-field wide">
              Question
              <textarea
                rows={2}
                value={row.question}
                onChange={(e) => update(row._key, { question: e.target.value })}
              />
            </label>
            <div className="q-field">
              Relevant document(s)
              <DocPicker
                value={row.relevant_document_ids}
                onChange={(v) => update(row._key, { relevant_document_ids: v })}
                known={known}
                listId="doc-ids"
              />
            </div>
            <label className="q-field">
              Reference answer
              <textarea
                rows={2}
                value={row.expected_answer}
                onChange={(e) =>
                  update(row._key, { expected_answer: e.target.value })
                }
                placeholder="Optional — needed for answer-quality judging"
              />
            </label>
            <label className="q-field wide">
              Keywords (comma-separated, for your own reading)
              <input
                className="text-input"
                value={row.keywordsText}
                onChange={(e) =>
                  update(row._key, { keywordsText: e.target.value })
                }
              />
            </label>
          </div>
        </div>
      ))}

      <button
        type="button"
        className="btn btn-secondary"
        onClick={add}
        style={{ alignSelf: "flex-start" }}
      >
        + Add question
      </button>

      <div className="sticky-bar">
        <button
          type="button"
          className="btn btn-primary"
          onClick={save}
          disabled={!dirty || saving}
        >
          {saving ? "Saving…" : "Save questions"}
        </button>
        <button
          type="button"
          className="btn btn-ghost"
          onClick={revert}
          disabled={!dirty || saving}
        >
          Revert
        </button>
        <span className="muted small">
          {rows.length} question(s) ·{" "}
          {dirty ? "unsaved changes" : saved ? "saved ✓" : "up to date"}
        </span>
      </div>

      {error && <div className="notice notice-error">{error}</div>}
      {warnings.map((w) => (
        <div key={w} className="notice notice-warn">
          {w}
        </div>
      ))}
    </div>
  );
}
