import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "../services/api.js";

// ---------------------------------------------------------------------------
// Questions (questions.json) — local draft + explicit save
// ---------------------------------------------------------------------------

export const canon = (q) => ({
  id: (q.id ?? "").trim(),
  question: (q.question ?? "").trim(),
  relevant_document_ids: [
    ...new Set(
      (q.relevant_document_ids ?? []).map((s) => s.trim()).filter(Boolean),
    ),
  ],
  expected_answer: (q.expected_answer ?? "").trim() || null,
  expected_keywords: (q.expected_keywords ?? [])
    .map((s) => s.trim())
    .filter(Boolean),
  category: (q.category ?? "").trim() || null,
});

let keySeq = 0;
const withKey = (q) => ({ ...q, _key: `k${++keySeq}` });
const strip = ({ _key, ...q }) => q;

export function validateDraft(draft) {
  const problems = [];
  const seen = new Set();
  draft.forEach((raw, i) => {
    const q = canon(raw);
    const label = `Question ${i + 1}${q.id ? ` (${q.id})` : ""}`;
    if (!q.id) problems.push(`${label}: needs an id.`);
    else if (seen.has(q.id))
      problems.push(`${label}: id "${q.id}" is used more than once.`);
    seen.add(q.id);
    if (!q.question) problems.push(`${label}: the question text is empty.`);
    if (q.relevant_document_ids.length === 0)
      problems.push(`${label}: pick at least one relevant document.`);
  });
  return problems;
}

export function useQuestions() {
  const [payload, setPayload] = useState(null);
  const [draft, setDraft] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(null);
  const [saving, setSaving] = useState(false);
  const [saveProblems, setSaveProblems] = useState([]);
  const [savedAt, setSavedAt] = useState(null);

  const apply = useCallback((p) => {
    setPayload(p);
    setDraft(p.questions.map(withKey));
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      apply(await api.questions());
      setLoadError(null);
    } catch (err) {
      setLoadError(err.message);
    } finally {
      setLoading(false);
    }
  }, [apply]);

  useEffect(() => {
    load();
  }, [load]);

  const dirty = useMemo(
    () =>
      !!payload &&
      JSON.stringify(draft.map((q) => canon(strip(q)))) !==
        JSON.stringify(payload.questions.map(canon)),
    [draft, payload],
  );

  useEffect(() => {
    if (!dirty) return;
    const handler = (e) => {
      e.preventDefault();
      e.returnValue = "";
    };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [dirty]);

  const knownDocs = payload?.known_documents ?? [];
  const knownIds = useMemo(
    () => new Set(knownDocs.map((d) => d.document_id)),
    [knownDocs],
  );
  const problems = useMemo(() => validateDraft(draft), [draft]);

  const nextId = () => {
    const used = new Set(draft.map((q) => (q.id ?? "").trim()));
    let n = draft.length + 1;
    while (used.has(`q${n}`)) n += 1;
    return `q${n}`;
  };

  const ops = {
    add: () => {
      const q = withKey({
        id: nextId(),
        question: "",
        relevant_document_ids: [],
        expected_answer: "",
        expected_keywords: [],
        category: "",
      });
      setDraft((d) => [...d, q]);
      return q._key;
    },
    update: (key, patch) =>
      setDraft((d) => d.map((q) => (q._key === key ? { ...q, ...patch } : q))),
    remove: (key) => setDraft((d) => d.filter((q) => q._key !== key)),
    duplicate: (key) =>
      setDraft((d) => {
        const i = d.findIndex((q) => q._key === key);
        if (i < 0) return d;
        const used = new Set(d.map((q) => q.id));
        let n = d.length + 1;
        while (used.has(`q${n}`)) n += 1;
        const copy = withKey({
          ...d[i],
          id: `q${n}`,
          relevant_document_ids: [...d[i].relevant_document_ids],
        });
        return [...d.slice(0, i + 1), copy, ...d.slice(i + 1)];
      }),
    replaceAll: (questions) =>
      setDraft(
        questions.map((q) =>
          withKey({
            ...canon(q),
            expected_answer: q.expected_answer ?? "",
            category: q.category ?? "",
          }),
        ),
      ),
    discard: () => payload && apply(payload),
  };

  const save = async () => {
    setSaving(true);
    setSaveProblems([]);
    try {
      const res = await api.saveQuestions(draft.map((q) => canon(strip(q))));
      apply(res);
      setSavedAt(Date.now());
      return true;
    } catch (err) {
      let list = [err.message];
      try {
        const parsed = JSON.parse(err.message);
        if (Array.isArray(parsed)) list = parsed;
      } catch {
        /* plain message */
      }
      setSaveProblems(list);
      return false;
    } finally {
      setSaving(false);
    }
  };

  const createStarter = async () => {
    try {
      apply(await api.createStarterQuestions());
    } catch (err) {
      setSaveProblems([err.message]);
    }
  };

  return {
    payload,
    draft,
    knownDocs,
    knownIds,
    loading,
    loadError,
    dirty,
    problems,
    saving,
    saveProblems,
    savedAt,
    save,
    createStarter,
    reload: load,
    ...ops,
  };
}

// ---------------------------------------------------------------------------
// Saved evaluation runs (read-only)
// ---------------------------------------------------------------------------

export function useEvalRuns() {
  const [runs, setRuns] = useState(null);
  const [error, setError] = useState(null);
  const [selectedId, setSelectedId] = useState(null);
  const [detail, setDetail] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);

  const load = useCallback(async () => {
    try {
      const { runs: list } = await api.evalRuns();
      setRuns(list);
      setError(null);
      setSelectedId((cur) =>
        cur && list.some((r) => `${r.source}/${r.name}` === cur)
          ? cur
          : list[0]
            ? `${list[0].source}/${list[0].name}`
            : null,
      );
    } catch (err) {
      setError(err.message);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (!selectedId) {
      setDetail(null);
      return;
    }
    const [source, ...rest] = selectedId.split("/");
    const controller = new AbortController();
    setDetailLoading(true);
    api
      .evalRun(source, rest.join("/"), controller.signal)
      .then(setDetail)
      .catch((err) => err.name !== "AbortError" && setError(err.message))
      .finally(() => setDetailLoading(false));
    return () => controller.abort();
  }, [selectedId]);

  return {
    runs,
    error,
    selectedId,
    setSelectedId,
    detail,
    detailLoading,
    reload: load,
  };
}
