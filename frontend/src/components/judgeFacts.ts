import type {
  AgentDashboard, Mission, MLModelInfo, RescueRecommendation, ScenarioPredictionSet, ScenarioState,
} from "../api/client";

export function judgeFacts({
  scenario, predictions, dashboard, recommendation, missions, model,
}: {
  scenario: ScenarioState | null;
  predictions: ScenarioPredictionSet | null;
  dashboard: AgentDashboard | null;
  recommendation: RescueRecommendation | null;
  missions: Mission[];
  model: MLModelInfo | null;
}) {
  const predictionCurrent = Boolean(scenario && predictions && predictions.scenario_id === scenario.id &&
    predictions.scenario_state_version === scenario.state_version && predictions.scenario_tick === scenario.tick &&
    model?.status === "ready" && predictions.model_version === model.model_version);
  const traceCurrent = Boolean(scenario && dashboard?.latest_trace && dashboard.latest_trace.scenario_id === scenario.id &&
    dashboard.latest_trace.scenario_epoch === scenario.epoch && dashboard.latest_trace.simulation_state_version === scenario.state_version &&
    dashboard.latest_trace.infrastructure_revision === dashboard.infrastructure_revision);
  const recommendationCurrent = Boolean(scenario && recommendation && recommendation.scenario_id === scenario.id &&
    recommendation.scenario_version === scenario.state_version && recommendation.scenario_epoch === scenario.epoch &&
    dashboard && recommendation.infrastructure_revision === dashboard.infrastructure_revision);
  const decisionRecorded = Boolean(scenario && recommendation && dashboard && recommendation.scenario_id === scenario.id &&
    recommendation.scenario_epoch === scenario.epoch && recommendation.infrastructure_revision === dashboard.infrastructure_revision &&
    ["approved", "rejected"].includes(recommendation.status));
  const currentMissions = missions.filter((mission) => scenario && mission.scenario_id === scenario.id && mission.scenario_epoch === scenario.epoch);
  const exposed = scenario?.affected_buildings ?? null;
  const predicted = predictionCurrent ? predictions!.predictions.filter((row) => row.predicted_future_exposed).length : null;
  const pendingApproval = recommendationCurrent && recommendation!.status === "proposed";
  const activeMissions = currentMissions.filter((mission) => ["ready", "en_route", "blocked", "arrived"].includes(mission.status)).length;
  const completedMissions = currentMissions.filter((mission) => mission.status === "completed").length;
  const stages = [
    { label: "City", status: scenario ? "recorded" : "pending" },
    { label: "Flood", status: scenario && scenario.tick > 0 ? "recorded" : "pending" },
    { label: "Model", status: predictionCurrent ? "recorded" : model?.status === "unavailable" ? "unavailable" : "pending" },
    { label: "Agents", status: traceCurrent && dashboard?.latest_trace ? dashboard.latest_trace.status === "completed" ? "recorded" : "unavailable" : "pending" },
    { label: "Proposal", status: recommendationCurrent ? "recorded" : recommendation ? "unavailable" : "pending" },
    { label: "Commander", status: decisionRecorded ? "recorded" : "pending" },
    { label: "Missions", status: currentMissions.length ? "recorded" : "pending" },
  ] as const;
  return {
    predictionCurrent, traceCurrent, recommendationCurrent, decisionRecorded, pendingApproval,
    exposed, predicted, activeMissions, completedMissions, stages,
    nextAction: !scenario ? "Waiting for the local scenario snapshot" : scenario.tick === 0
      ? "Advance the flood simulator in Scenario Lab" : !predictionCurrent
        ? model?.status === "unavailable" ? "Inspect local model status in Model Intelligence Lab" : "Refresh model inference for this scenario version"
        : pendingApproval ? "A commander must review the current proposal" : !traceCurrent
          ? "Run a six-agent assessment in Guided Demo" : activeMissions
              ? "Review mission progress in Command Center" : "Inspect the saved evidence and assumptions",
  };
}
