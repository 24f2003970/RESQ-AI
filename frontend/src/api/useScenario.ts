import { useCallback, useEffect, useRef, useState } from "react";
import {
  advanceScenario,
  fetchActiveScenario,
  transitionScenario,
  type ScenarioEnvelope,
} from "./client";

export function useScenario(pathname: string) {
  const [envelope, setEnvelope] = useState<ScenarioEnvelope | null>(null);
  const [error, setError] = useState("");
  const [revision, setRevision] = useState(0);
  const stateRef = useRef<ScenarioEnvelope["state"] | null>(null);
  const busy = useRef(false);
  const timerFailed = useRef(false);
  if (envelope) stateRef.current = envelope.state;

  const retry = useCallback(() => setRevision((value) => value + 1), []);
  const accept = useCallback((next: ScenarioEnvelope) => {
    setEnvelope(next);
    stateRef.current = next.state;
    setError("");
  }, []);

  useEffect(() => {
    let live = true;
    fetchActiveScenario()
      .then((next) => {
        if (live) accept(next);
      })
      .catch((cause: unknown) => {
        if (live) setError(cause instanceof Error ? cause.message : "Cannot load the local scenario.");
      });
    return () => {
      live = false;
    };
  }, [accept, revision]);

  useEffect(() => {
    const state = stateRef.current;
    if (!state || state.status !== "running") return;
    if (pathname !== "/scenarios") {
      transitionScenario(state, "pause").then(accept).catch(() => {});
      return;
    }
    timerFailed.current = false;
    const intervalMs = Math.max(150, 1000 / state.parameters.speed);
    const timer = window.setInterval(() => {
      const current = stateRef.current;
      if (!current || current.status !== "running" || busy.current || document.hidden || timerFailed.current) return;
      busy.current = true;
      advanceScenario(current)
        .then(accept)
        .catch((cause: unknown) => {
          timerFailed.current = true;
          setError(cause instanceof Error ? cause.message : "Simulation update failed. Retry the local connection.");
        })
        .finally(() => {
          busy.current = false;
        });
    }, intervalMs);
    return () => window.clearInterval(timer);
  }, [accept, pathname, envelope?.state.status, envelope?.state.parameters.speed]);

  useEffect(() => {
    const pauseIfHidden = () => {
      const state = stateRef.current;
      if (document.hidden && state?.status === "running")
        transitionScenario(state, "pause").then(accept).catch(() => {});
    };
    document.addEventListener("visibilitychange", pauseIfHidden);
    return () => document.removeEventListener("visibilitychange", pauseIfHidden);
  }, [accept]);

  return { envelope, scenario: envelope?.state ?? null, error, retry, accept };
}
