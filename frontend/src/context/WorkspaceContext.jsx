import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import { api } from "../services/api.js";
import {
  adoptWorkspaceFromUrl,
  getGroqKey,
  getModel,
  getWorkspaceId,
  isKeyRemembered,
  setGroqKey,
  setModel,
  setWorkspaceId,
  subscribe,
} from "../services/workspace.js";

const Ctx = createContext(null);

adoptWorkspaceFromUrl();

export function WorkspaceProvider({ children }) {
  const [, tick] = useState(0);
  const [info, setInfo] = useState(null);
  const [error, setError] = useState(null);
  const [notice, setNotice] = useState(null);

  useEffect(() => subscribe(() => tick((n) => n + 1)), []);

  const id = getWorkspaceId();
  const key = getGroqKey();
  const model = getModel();

  const refresh = useCallback(async () => {
    const hadWorkspace = Boolean(getWorkspaceId());
    try {
      setInfo(await api.currentWorkspace());
      setError(null);
    } catch (err) {
      if (err.status === 410 && hadWorkspace) {
        setNotice(
          "Your private workspace has expired or was deleted, so you're back on the sample.",
        );
        return;
      }
      setError(err.message);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [id, key, model, refresh]);

  const value = useMemo(
    () => ({
      id,
      info,
      error,
      notice,
      dismissNotice: () => setNotice(null),
      scope: id ?? "sample",
      isPrivate: Boolean(id),
      hosted: info?.mode === "hosted",
      readOnly: info?.read_only ?? false,
      hasKey: Boolean(key),
      keyRemembered: isKeyRemembered(),
      refresh,
      model: info?.model?.current ?? null,
      modelInfo: info?.model ?? null,
      chooseModel: setModel,
      saveKey: setGroqKey,
      clearKey: () => setGroqKey(null),
      useSample: () => setWorkspaceId(null),
      async startWorkspace(copySample) {
        const created = await api.createWorkspace(copySample);
        setNotice(null);
        setWorkspaceId(created.id);
        return created;
      },
      async deleteWorkspace() {
        if (!id) return;
        await api.deleteWorkspace(id);
        setWorkspaceId(null);
      },
    }),
    [id, key, model, info, error, notice, refresh],
  );
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useWorkspace() {
  const value = useContext(Ctx);
  if (!value)
    throw new Error("useWorkspace must be used inside <WorkspaceProvider>");
  return value;
}
