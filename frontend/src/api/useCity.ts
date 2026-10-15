import { useCallback, useEffect, useState } from "react";
import { fetchCity, fetchHealth, type CityState } from "./client";

export function useCity() {
  const [city, setCity] = useState<CityState | null>(null);
  const [status, setStatus] = useState<"loading" | "online" | "offline">(
    "loading",
  );
  const [error, setError] = useState("");
  const [revision, setRevision] = useState(0);
  const retry = useCallback(() => setRevision((r) => r + 1), []);
  useEffect(() => {
    const controller = new AbortController();
    setStatus("loading");
    setError("");
    Promise.all([fetchCity(controller.signal), fetchHealth()])
      .then(([data]) => {
        if (!controller.signal.aborted) {
          setCity(data);
          setStatus("online");
        }
      })
      .catch((e: unknown) => {
        if (!controller.signal.aborted) {
          setError(
            e instanceof Error ? e.message : "Cannot reach the local service.",
          );
          setStatus("offline");
        }
      });
    const timer = window.setInterval(() => {
      fetchHealth()
        .then(() => {
          if (!controller.signal.aborted)
            setStatus((current) =>
              current === "offline" ? current : "online",
            );
        })
        .catch(() => {
          if (!controller.signal.aborted) {
            setStatus("offline");
            setError(
              "Connection to the local backend was lost. The visible city is the last loaded snapshot.",
            );
          }
        });
    }, 15000);
    return () => {
      controller.abort();
      window.clearInterval(timer);
    };
  }, [revision]);
  return { city, status, error, retry };
}
