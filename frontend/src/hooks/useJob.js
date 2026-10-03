import { useEffect, useRef, useState } from "react";
import { api } from "../services/api.js";

export function useJob(jobId, onFinished) {
  const [job, setJob] = useState(null);
  const finished = useRef(onFinished);
  finished.current = onFinished;

  useEffect(() => {
    if (!jobId) {
      setJob(null);
      return;
    }
    let stopped = false;
    let timer;

    const tick = async () => {
      try {
        const j = await api.job(jobId);
        if (stopped) return;
        setJob(j);
        if (j.status === "succeeded" || j.status === "failed") {
          finished.current?.(j);
          return;
        }
      } catch (err) {
        if (stopped) return;
        if (err.status === 404) {
          setJob({
            id: jobId,
            status: "failed",
            progress: 0,
            error: err.message,
          });
          return;
        }
      }
      timer = setTimeout(tick, 1000);
    };
    tick();

    return () => {
      stopped = true;
      clearTimeout(timer);
    };
  }, [jobId]);

  return job;
}
