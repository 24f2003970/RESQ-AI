import { useEffect, useState } from "react";
import { fetchMLModel, fetchScenarioPredictions, type MLModelInfo, type ScenarioPredictionSet, type ScenarioState } from "./client";

export function useRisk(scenario: ScenarioState | null) {
  const [model, setModel] = useState<MLModelInfo | null>(null);
  const [predictions, setPredictions] = useState<ScenarioPredictionSet | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    const controller = new AbortController();
    fetchMLModel(controller.signal).then(setModel).catch((e: unknown) => {
      if (!controller.signal.aborted) setError(e instanceof Error ? e.message : "Model service unavailable.");
    });
    return () => controller.abort();
  }, []);
  useEffect(() => {
    setPredictions(null);
    if (!scenario || model?.status !== "ready") return;
    const controller = new AbortController();
    fetchScenarioPredictions(scenario, undefined, controller.signal).then((result) => {
      if (result.scenario_id === scenario.id && result.scenario_state_version === scenario.state_version && result.scenario_tick === scenario.tick) setPredictions(result);
    }).catch((e: unknown) => {
      if (!controller.signal.aborted) setError(e instanceof Error ? e.message : "Predictions unavailable.");
    });
    return () => controller.abort();
  }, [scenario, scenario?.id, scenario?.state_version, scenario?.tick, model?.status]);
  return { model, predictions, error };
}
