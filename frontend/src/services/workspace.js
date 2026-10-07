const ID_KEY = "rag-lab.workspace";
const KEY_KEY = "rag-lab.groq-key";
const MODEL_KEY = "rag-lab.groq-model";
const ID_RE = /^[a-f0-9]{20}$/;

const memory = { id: null, key: null, model: null };
const listeners = new Set();

function read(store, name) {
  try {
    return window[store].getItem(name);
  } catch {
    return null;
  }
}
function write(store, name, value) {
  try {
    if (value == null) window[store].removeItem(name);
    else window[store].setItem(name, value);
  } catch {
    /* storage unavailable: the in-memory copy still works for this page */
  }
}
const emit = () => listeners.forEach((fn) => fn());

export const isValidWorkspaceId = (id) =>
  typeof id === "string" && ID_RE.test(id);

export function getWorkspaceId() {
  const stored = read("localStorage", ID_KEY) ?? memory.id;
  return isValidWorkspaceId(stored) ? stored : null;
}
export function setWorkspaceId(id) {
  memory.id = id ?? null;
  write("localStorage", ID_KEY, id ?? null);
  emit();
}

export function getGroqKey() {
  return (
    read("sessionStorage", KEY_KEY) ??
    read("localStorage", KEY_KEY) ??
    memory.key ??
    ""
  );
}
export function isKeyRemembered() {
  return Boolean(read("localStorage", KEY_KEY));
}
export function setGroqKey(key, remember = false) {
  const value = key?.trim() || null;
  memory.key = value;
  write("sessionStorage", KEY_KEY, remember ? null : value);
  write("localStorage", KEY_KEY, remember ? value : null);
  emit();
}

export function getModel() {
  return read("localStorage", MODEL_KEY) ?? memory.model ?? "";
}
export function setModel(model) {
  const value = model?.trim() || null;
  memory.model = value;
  write("localStorage", MODEL_KEY, value);
  emit();
}
export const MODEL_RE = /^[A-Za-z0-9][A-Za-z0-9._:/-]{0,99}$/;

export function subscribe(fn) {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

export function adoptWorkspaceFromUrl() {
  try {
    const url = new URL(window.location.href);
    const id = url.searchParams.get("ws");
    if (!id) return;
    url.searchParams.delete("ws");
    window.history.replaceState(
      {},
      "",
      url.pathname + (url.search || "") + url.hash,
    );
    if (isValidWorkspaceId(id)) setWorkspaceId(id);
  } catch {
    /* ignore */
  }
}

export function resumeLink(id) {
  return `${window.location.origin}${window.location.pathname}?ws=${id}`;
}
