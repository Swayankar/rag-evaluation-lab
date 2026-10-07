import { useCallback, useEffect, useState } from "react";
import { api } from "../services/api.js";

const CHECK_INTERVAL = 10000;
const TIMEOUT = 5000;

export function useBackendStatus() {
  const [status, setStatus] = useState("checking");

  const check = useCallback(async () => {
    try {
      const result = await api.health(AbortSignal.timeout(TIMEOUT));

      setStatus(result?.status === "ok" ? "online" : "starting");
    } catch {
      setStatus("starting");
    }
  }, []);

  useEffect(() => {
    check();

    const interval = setInterval(check, CHECK_INTERVAL);

    return () => clearInterval(interval);
  }, [check]);

  return {
    status,
    check,
  };
}
