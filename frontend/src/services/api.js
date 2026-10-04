const BASE = (import.meta.env.VITE_API_URL ?? "http://localhost:8000").replace(
  /\/$/,
  "",
);

async function request(path, { method = "GET", body, signal } = {}) {
  const isForm = typeof FormData !== "undefined" && body instanceof FormData;
  let response;
  try {
    response = await fetch(`${BASE}${path}`, {
      method,
      headers:
        body && !isForm ? { "Content-Type": "application/json" } : undefined,
      body: body ? (isForm ? body : JSON.stringify(body)) : undefined,
      signal,
    });
  } catch (err) {
    if (err.name === "AbortError") throw err;
    throw new Error(
      `Can't reach the API at ${BASE}. Is the backend running? (uvicorn app.main:app --reload)`,
    );
  }

  if (!response.ok) {
    let detail = response.statusText;
    try {
      const data = await response.json();
      detail =
        typeof data.detail === "string"
          ? data.detail
          : JSON.stringify(data.detail ?? data);
    } catch {
      /* non-JSON error body */
    }
    const error = new Error(detail);
    error.status = response.status;
    throw error;
  }
  return response.json();
}

export const api = {
  health: (signal) => request("/health", { signal }),
  config: (signal) => request("/config", { signal }),

  query: (body, signal) => request("/query", { method: "POST", body, signal }),
  compare: (body, signal) =>
    request("/query/compare", { method: "POST", body, signal }),

  documents: (signal) => request("/documents", { signal }),
  library: (signal) => request("/documents/library", { signal }),
  createFolder: (name) =>
    request("/documents/folders", { method: "POST", body: { name } }),
  deleteFolder: (name) =>
    request(`/documents/folders/${encodeURIComponent(name)}`, {
      method: "DELETE",
    }),
  upload: (department, files) => {
    const form = new FormData();
    form.append("department", department);
    files.forEach((f) => form.append("files", f));
    return request("/documents/upload", { method: "POST", body: form });
  },
  deleteDocument: (department, filename) =>
    request(
      `/documents/${encodeURIComponent(department)}/${encodeURIComponent(filename)}`,
      { method: "DELETE" },
    ),
  resetLibrary: (body) => request("/documents/reset", { method: "POST", body }),
  rebuild: (chunking) =>
    request("/documents/rebuild", { method: "POST", body: { chunking } }),

  questions: (signal) => request("/evaluation/questions", { signal }),
  saveQuestions: (questions) =>
    request("/evaluation/questions", { method: "PUT", body: { questions } }),
  createStarterQuestions: () =>
    request("/evaluation/questions/starter", { method: "POST" }),
  evalRuns: (signal) => request("/evaluation/results", { signal }),
  evalRun: (source, name, signal) =>
    request(
      `/evaluation/results/${encodeURIComponent(source)}/${encodeURIComponent(name)}`,
      { signal },
    ),

  questions: (signal) => request("/evaluation/questions", { signal }),
  saveQuestions: (questions) =>
    request("/evaluation/questions", { method: "PUT", body: { questions } }),
  runEvaluation: (body) => request("/evaluation/run", { method: "POST", body }),
  evalResults: (signal) => request("/evaluation/results", { signal }),
  evalResult: (name, signal) =>
    request(`/evaluation/results/${encodeURIComponent(name)}`, { signal }),
  deleteEvalResult: (name) =>
    request(`/evaluation/results/${encodeURIComponent(name)}`, {
      method: "DELETE",
    }),

  experimentsOverview: (signal) => request("/experiments/overview", { signal }),
  experimentConfigs: (signal) => request("/experiments/configs", { signal }),
  saveExperimentConfigs: (experiments) =>
    request("/experiments/configs", { method: "PUT", body: { experiments } }),
  runExperiments: (body) =>
    request("/experiments/run", { method: "POST", body }),
  experimentDetail: (name, signal) =>
    request(`/experiments/${encodeURIComponent(name)}`, { signal }),

  job: (id, signal) => request(`/jobs/${id}`, { signal }),
  jobs: (kind, signal) =>
    request(`/jobs${kind ? `?kind=${kind}` : ""}`, { signal }),
};
