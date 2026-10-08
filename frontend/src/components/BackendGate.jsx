import { useEffect, useRef, useState } from "react";
import { api } from "../services/api.js";
import "./BackendGate.css";

const TRY_TIMEOUT_MS = 8000; // give up on one attempt after this long...
const RETRY_DELAY_MS = 2000; // ...wait a moment, then try again
const SHOW_AFTER_MS = 1200; // fast backends never see the waiting screen
const SLOW_AFTER_S = 75; // after this we say it is taking unusually long

export default function BackendGate({ children }) {
  const [ready, setReady] = useState(false);
  const [showWait, setShowWait] = useState(false);
  const [seconds, setSeconds] = useState(0);
  const [attempts, setAttempts] = useState(0);
  const startedAt = useRef(Date.now());

  useEffect(() => {
    let stopped = false;
    let retryTimer;
    let abort;
    const started = startedAt.current;

    async function check() {
      abort = new AbortController();
      const timeout = setTimeout(() => abort.abort(), TRY_TIMEOUT_MS);
      try {
        await api.health(abort.signal);
        clearTimeout(timeout);
        if (!stopped) setReady(true);
      } catch {
        clearTimeout(timeout);
        if (stopped) return;
        setAttempts((n) => n + 1);
        retryTimer = setTimeout(check, RETRY_DELAY_MS);
      }
    }
    check();

    const tick = setInterval(() => {
      const elapsed = Date.now() - started;
      setSeconds(Math.floor(elapsed / 1000));
      if (elapsed > SHOW_AFTER_MS) setShowWait(true);
    }, 500);

    return () => {
      stopped = true;
      clearTimeout(retryTimer);
      clearInterval(tick);
      abort?.abort();
    };
  }, []);

  if (ready) return children;
  if (!showWait) return null;

  const slow = seconds >= SLOW_AFTER_S;
  return (
    <div className="gate" role="status" aria-live="polite">
      <div className="gate-card">
        <div className="gate-spinner" aria-hidden="true" />
        <h1 className="gate-title">Waking up the server…</h1>
        <p className="gate-text">
          The backend runs on a free server that goes to sleep when nobody is
          using it. The first visit wakes it up, which usually takes{" "}
          <strong>30–60 seconds</strong>. This page will open by itself as soon
          as it is ready.
        </p>
        <div className="gate-timer mono">{seconds}s</div>
        <div className="gate-bar" aria-hidden="true">
          <span style={{ width: `${Math.min(95, (seconds / 60) * 100)}%` }} />
        </div>
        {slow && (
          <p className="gate-slow">
            This is taking longer than usual ({attempts} tries so far). The
            server may still be starting. If it never opens, the backend may be
            down or misconfigured.{" "}
            <button
              className="btn btn-secondary btn-sm"
              onClick={() => window.location.reload()}
            >
              Reload
            </button>
          </p>
        )}
      </div>
    </div>
  );
}
