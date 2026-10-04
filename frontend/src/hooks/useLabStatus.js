import { useCallback, useEffect, useState } from "react";
import { api } from "../services/api.js";

export function useLabStatus() {
  const [state, setState] = useState({ loading: true, offline: false });

  const load = useCallback(async () => {
    const [library, questions, evalRuns, overview, config] =
      await Promise.allSettled([
        api.library(),
        api.questions(),
        api.evalResults(),
        api.experimentsOverview(),
        api.config(),
      ]);
    const value = (r) => (r.status === "fulfilled" ? r.value : null);
    const unreachable = [library, questions, evalRuns, overview, config].every(
      (r) => r.status === "rejected" && !r.reason?.status,
    );
    setState({
      loading: false,
      offline: unreachable,
      library: value(library),
      questions: value(questions),
      evalRuns: value(evalRuns)?.results ?? null,
      overview: value(overview),
      config: value(config),
    });
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  return { ...state, reload: load };
}
