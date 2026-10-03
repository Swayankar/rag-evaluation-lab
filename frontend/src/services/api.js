const BASE = (import.meta.env.VITE_API_URL ?? "http://localhost:8000").replace(
  /\/$/,
  "",
);

async function request(path, { method = "GET", body, signal } = {}) {
  let response;
  try {
    response = await fetch(`${BASE}${path}`, {
      method,
      headers: body ? { "Content-Type": "application/json" } : undefined,
      body: body ? JSON.stringify(body) : undefined,
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
    throw new Error(detail);
  }
  return response.json();
}

export const api = {
  health: (signal) => request("/health", { signal }),
  query: (body, signal) => request("/query", { method: "POST", body, signal }),
  compare: (body, signal) =>
    request("/query/compare", { method: "POST", body, signal }),
  documents: (signal) => request("/documents", { signal }),
};
