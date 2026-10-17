import Ajv2020 from "ajv/dist/2020";
import citySchema from "./city.schema.json";
import scenarioSchema from "./scenario.schema.json";
import modelSchema from "./ml-model.schema.json";
import datasetSchema from "./ml-dataset.schema.json";
import evaluationSchema from "./ml-evaluation.schema.json";
import featureSchema from "./ml-feature.schema.json";
import predictionsSchema from "./ml-predictions.schema.json";
import agentDashboardSchema from "./agent-dashboard.schema.json";
import agentEventSchema from "./agent-event.schema.json";
import agentTraceDetailSchema from "./agent-trace-detail.schema.json";
import rescuePlanSchema from "./rescue-plan.schema.json";
import experimentRecordSchema from "./experiment-record.schema.json";
import missionSchema from "./mission.schema.json";
import missionClockSchema from "./mission-clock.schema.json";
import missionUnitResourceSchema from "./mission-unit-resource.schema.json";
import missionEventSchema from "./mission-event.schema.json";
import type { components } from "./schema";

export type CityState = components["schemas"]["CityState"];
export type Building = components["schemas"]["Building"];
export type Position = components["schemas"]["Position"];
export type Health = components["schemas"]["Health"];
export type ScenarioEnvelope = components["schemas"]["ScenarioEnvelope"];
export type ScenarioState = components["schemas"]["ScenarioState"];
export type SimulationParameters = components["schemas"]["SimulationParameters"];
export type SimulationEvent = components["schemas"]["SimulationEvent"];
export type MLModelInfo = components["schemas"]["MLModelInfo"];
export type MLDatasetInfo = components["schemas"]["MLDatasetInfo"];
export type MLEvaluationReport = components["schemas"]["MLEvaluationReport"];
export type MLFeatureInfo = components["schemas"]["MLFeatureInfo"];
export type BuildingRiskPrediction = components["schemas"]["BuildingRiskPrediction"];
export type ScenarioPredictionSet = components["schemas"]["ScenarioPredictionSet"];
export type ReliabilityEvidence = { status: string; warnings: string[]; report: Record<string, unknown> | null };
export type SensitivityEvidence = { status: string; reason?: string; report: Record<string, unknown> | null };
export type AgentDashboard = components["schemas"]["AgentDashboard"];
export type AgentEventEnvelope = components["schemas"]["AgentEventEnvelope"];
export type AgentTraceDetail = components["schemas"]["AgentTraceDetail"];
export type AgentRunRecord = components["schemas"]["AgentRunRecord"];
export type RescueRecommendation = components["schemas"]["RescuePlan"];
export type ScenarioExperiment = components["schemas"]["ExperimentRecord"];
export type ScenarioExperimentCreate = components["schemas"]["ExperimentCreate"];
export type Mission = components["schemas"]["Mission"];
export type MissionClock = components["schemas"]["MissionClock"];
export type MissionUnitResource = components["schemas"]["MissionUnitResource"];
export type MissionEvent = components["schemas"]["MissionEvent"];
export type RobustnessCondition = {
  condition_id: string; label: string;
  category: "environment" | "road_closure" | "bridge_closure" | "resources" | "ml_reliability";
  rainfall_mm_h?: number; river_level_m?: number; drainage_effectiveness?: number;
  closed_asset_ids?: string[]; unavailable_unit_ids?: string[];
  unavailable_unit_type?: "ambulance" | "rescue_team"; unavailable_count?: number;
  reliability_mode?: "actual" | "injected_unavailable" | "outside_support" | "no_forecast_destinations";
};
export type RobustnessBaseline = {
  scenario_id: string; scenario_epoch: number; simulation_state_version: number;
  infrastructure_revision: number; simulation_tick: number; seed: number;
  available_unit_ids: string[]; reserved_unit_ids: string[]; manual_closure_road_ids: string[];
  plans: {plan_id:string;status:string;assignment_count:number;solver_status:string}[];
  model_reliability: {status:string;warnings:string[];calibration_status:string;probabilities_calibrated:boolean};
};
export type RobustnessStudy = {
  study_id:string;scenario_id:string;scenario_epoch:number;simulation_state_version:number;
  infrastructure_revision:number;simulation_tick:number;seed:number;original_plan_id:string;
  snapshot_sha256:string;frozen_available_unit_ids:string[];frozen_reserved_unit_ids:string[];
  baseline:Record<string,unknown>;conditions:RobustnessCondition[];evaluation_horizon_ticks:number;
  algorithm_version:string;status:"pending"|"running"|"completed"|"failed"|"interrupted";
  created_at_utc:string;completed_at_utc:string|null;stale:boolean;stale_reason:string|null;
  results:Record<string,unknown>|null;reproduction:Record<string,unknown>;error:string|null;
};

const validate = new Ajv2020({
  strict: false,
  allErrors: true,
}).compile<CityState>(citySchema);
const validateScenario = new Ajv2020({ strict: false, allErrors: true }).compile<ScenarioEnvelope>(scenarioSchema);
const ajv = new Ajv2020({ strict: false, allErrors: true });
ajv.addFormat("date-time", true);
const validateModel = ajv.compile<MLModelInfo>(modelSchema);
const validateDataset = ajv.compile<MLDatasetInfo>(datasetSchema);
const validateEvaluation = ajv.compile<MLEvaluationReport>(evaluationSchema);
const validateFeature = ajv.compile<MLFeatureInfo>(featureSchema);
const validatePredictions = ajv.compile<ScenarioPredictionSet>(predictionsSchema);
const validateAgentDashboard = ajv.compile<AgentDashboard>(agentDashboardSchema);
const validateAgentEvent = ajv.compile<AgentEventEnvelope>(agentEventSchema);
const validateAgentTrace = ajv.compile<AgentTraceDetail>(agentTraceDetailSchema);
const validateRescuePlan = ajv.compile<RescueRecommendation>(rescuePlanSchema);
const validateExperiment = ajv.compile<ScenarioExperiment>(experimentRecordSchema);
const validateMission = ajv.compile<Mission>(missionSchema);
const validateMissionClock = ajv.compile<MissionClock>(missionClockSchema);
const validateMissionUnit = ajv.compile<MissionUnitResource>(missionUnitResourceSchema);
const validateMissionEvent = ajv.compile<MissionEvent>(missionEventSchema);

export function parseCity(value: unknown): CityState {
  if (!validate(value))
    throw new Error(
      "The local service returned an invalid city. Restart the backend and retry.",
    );
  if (!value.buildings.length)
    throw new Error(
      "The city has no buildings. Check the local seed configuration and retry.",
    );
  return value;
}

async function request(path: string, signal?: AbortSignal, init?: RequestInit): Promise<unknown> {
  const timeout = AbortSignal.timeout(8000);
  const response = await fetch(`/api/v1/${path}`, {
    ...init,
    signal: signal ? AbortSignal.any([signal, timeout]) : timeout,
  });
  if (!response.ok) {
    const problem=await response.json().catch(()=>null) as {detail?:unknown;error?:{message?:unknown}}|null;
    const detail=typeof problem?.detail==="string"?problem.detail:typeof problem?.error?.message==="string"?problem.error.message:null;
    throw new Error(detail??`The local service returned ${response.status}. Check that FastAPI is running on port 8000.`);
  }
  return response.json();
}

async function scenarioRequest(path: string, method = "GET", body?: unknown, extraHeaders?: Record<string, string>): Promise<ScenarioEnvelope> {
  const value = await request(path, undefined, {
    method,
    ...(body === undefined && !extraHeaders ? {} : {
      headers: { ...(body === undefined ? {} : { "Content-Type": "application/json" }), ...extraHeaders },
      ...(body === undefined ? {} : { body: JSON.stringify(body) }),
    }),
  });
  if (!validateScenario(value)) throw new Error("The local service returned an invalid scenario state.");
  return value;
}

async function validatedML<T>(path: string, validator: (value: unknown) => value is T, signal?: AbortSignal): Promise<T> {
  const value = await request(path, signal);
  if (!validator(value)) throw new Error("The local service returned an invalid ML response contract.");
  return value;
}

export const fetchMLModel = (signal?: AbortSignal) => validatedML("ml/model", validateModel, signal);
export const fetchMLDataset = (signal?: AbortSignal) => validatedML("ml/dataset", validateDataset, signal);
export const fetchMLEvaluation = (signal?: AbortSignal) => validatedML("ml/evaluation", validateEvaluation, signal);
export async function fetchMLReliability(signal?: AbortSignal): Promise<ReliabilityEvidence> {
  const value = await request("ml/reliability", signal) as ReliabilityEvidence;
  if (!value || typeof value.status !== "string" || !Array.isArray(value.warnings)) throw new Error("Reliability evidence response is invalid.");
  return value;
}
export async function fetchMLSensitivity(signal?: AbortSignal): Promise<SensitivityEvidence> {
  const value = await request("ml/sensitivity", signal) as SensitivityEvidence;
  if (!value || typeof value.status !== "string") throw new Error("Sensitivity evidence response is invalid.");
  return value;
}
export async function fetchMLFeatures(signal?: AbortSignal): Promise<MLFeatureInfo[]> {
  const value: unknown = await request("ml/features", signal);
  if (!Array.isArray(value) || !value.every((feature) => validateFeature(feature)))
    throw new Error("The local service returned invalid ML feature definitions.");
  return value;
}
export const fetchScenarioPredictions = (state: ScenarioState, buildingId?: string, signal?: AbortSignal) =>
  validatedML(`scenarios/${encodeURIComponent(state.id)}/predictions${buildingId ? `/${encodeURIComponent(buildingId)}` : ""}`, validatePredictions, signal);

export const fetchActiveScenario = () => scenarioRequest("scenarios/active");
export const fetchAgentDashboard = async (scenarioId: string, signal?: AbortSignal) => {
  const value = await request(`scenarios/${encodeURIComponent(scenarioId)}/agent-status`, signal);
  if (!validateAgentDashboard(value)) throw new Error("The local service returned an invalid agent status contract.");
  return value;
};
export const fetchAgentEvents = async (scenarioId: string, signal?: AbortSignal) => {
  const value: unknown = await request(`scenarios/${encodeURIComponent(scenarioId)}/agent-events?limit=30`, signal);
  if (!Array.isArray(value) || !value.every((event) => validateAgentEvent(event))) throw new Error("The local service returned invalid agent events.");
  return value as AgentEventEnvelope[];
};
export const fetchAgentTrace = async (eventId: string, signal?: AbortSignal) => {
  const value = await request(`agent-traces/${encodeURIComponent(eventId)}`, signal);
  if (!validateAgentTrace(value)) throw new Error("The local service returned an invalid decision trace contract.");
  return value;
};
export const fetchLatestRecommendation = async (scenarioId:string, signal?:AbortSignal):Promise<RescueRecommendation|null> => {
  const value=await request(`scenarios/${encodeURIComponent(scenarioId)}/recommendations/latest`,signal);
  if(value===null)return null;
  if(!validateRescuePlan(value))throw new Error("The local service returned an invalid rescue recommendation.");
  return value;
};
export async function requestIntelligenceAssessment(scenarioId: string, signal?: AbortSignal) {
  const value = await request(`scenarios/${encodeURIComponent(scenarioId)}/intelligence-assessments`, signal, {method:"POST"});
  if (!value || typeof value !== "object" || !("event_id" in value) || typeof value.event_id !== "string") throw new Error("The local service returned an invalid assessment receipt.");
  return value as components["schemas"]["AgentEventAccepted"];
}
export async function retryAgentEvent(eventId: string, signal?: AbortSignal) {
  const value = await request(`agent-events/${encodeURIComponent(eventId)}/retry`, signal, {method:"POST"});
  if (!value || typeof value !== "object" || !("event_id" in value)) throw new Error("The local service returned an invalid retry receipt.");
  return value as components["schemas"]["AgentEventAccepted"];
}
export const createScenario = (name: string, preset: "mild" | "heavy" | "extreme") =>
  scenarioRequest("scenarios", "POST", { name, preset, seed: 2026 }, { "Idempotency-Key": crypto.randomUUID() });
export const fetchScenario = (id: string) => scenarioRequest(`scenarios/${encodeURIComponent(id)}`);
export const fetchReplay = (id: string, tick: number) => scenarioRequest(`scenarios/${encodeURIComponent(id)}/replay/${tick}`);
export const updateScenarioParameters = (state: ScenarioState, params: Partial<SimulationParameters>) =>
  scenarioRequest(`scenarios/${encodeURIComponent(state.id)}/parameters`, "PATCH", { ...params, expected_version: state.state_version });
export const transitionScenario = (state: ScenarioState, action: "start" | "pause" | "resume") =>
  scenarioRequest(`scenarios/${encodeURIComponent(state.id)}/${action}`, "POST", { expected_version: state.state_version });
export const advanceScenario = (state: ScenarioState, steps = 1, singleStep = false) =>
  scenarioRequest(`scenarios/${encodeURIComponent(state.id)}/advance`, "POST", { steps, single_step: singleStep, expected_version: state.state_version });
export const resetScenario = (state: ScenarioState) =>
  scenarioRequest(`scenarios/${encodeURIComponent(state.id)}/reset`, "POST", { expected_version: state.state_version });

export async function fetchCity(signal?: AbortSignal): Promise<CityState> {
  return parseCity(await request("city/state", signal));
}

export async function fetchCityForSeed(seed: number, signal?: AbortSignal): Promise<CityState> {
  return parseCity(await request(`city/state?seed=${encodeURIComponent(seed)}`, signal));
}

export async function createScenarioExperiment(scenarioId: string, body: ScenarioExperimentCreate): Promise<ScenarioExperiment> {
  const value = await request(`scenarios/${encodeURIComponent(scenarioId)}/experiments`, undefined, {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
  if (!validateExperiment(value)) throw new Error("The local service returned an invalid experiment contract.");
  return value;
}

export async function fetchScenarioExperiment(experimentId: string, signal?: AbortSignal): Promise<ScenarioExperiment> {
  const value = await request(`scenario-experiments/${encodeURIComponent(experimentId)}`, signal);
  if (!validateExperiment(value)) throw new Error("The local service returned an invalid experiment result.");
  return value;
}

export async function fetchScenarioExperiments(scenarioId: string, signal?: AbortSignal): Promise<ScenarioExperiment[]> {
  const value: unknown = await request(`scenarios/${encodeURIComponent(scenarioId)}/experiments`, signal);
  if (!Array.isArray(value) || !value.every((item) => validateExperiment(item))) throw new Error("The local service returned an invalid saved experiments list.");
  return value as ScenarioExperiment[];
}

export async function fetchMissions(scenarioId:string,signal?:AbortSignal,epoch?:number):Promise<Mission[]> {
  const query=epoch===undefined?"":`?epoch=${encodeURIComponent(epoch)}`;
  const value:unknown=await request(`scenarios/${encodeURIComponent(scenarioId)}/missions${query}`,signal);
  if(!Array.isArray(value)||!value.every(item=>validateMission(item)))throw new Error("The local service returned invalid mission records.");
  return value as Mission[];
}
export async function fetchMissionClock(scenarioId:string,signal?:AbortSignal):Promise<MissionClock> {
  const value=await request(`scenarios/${encodeURIComponent(scenarioId)}/missions/clock`,signal);
  if(!validateMissionClock(value))throw new Error("The local service returned an invalid mission clock.");
  return value;
}
export async function fetchMissionUnits(scenarioId:string,signal?:AbortSignal):Promise<MissionUnitResource[]> {
  const value:unknown=await request(`scenarios/${encodeURIComponent(scenarioId)}/missions/units`,signal);
  if(!Array.isArray(value)||!value.every(item=>validateMissionUnit(item)))throw new Error("The local service returned invalid unit lifecycle records.");
  return value as MissionUnitResource[];
}
export async function missionCommand(missionId:string,action:"dispatch"|"pause"|"resume"|"complete"|"cancel"|"restore",expectedVersion:number,reason="") {
  const suffix=reason?`?reason=${encodeURIComponent(reason)}`:"";
  const value=await request(`missions/${encodeURIComponent(missionId)}/${action}${suffix}`,undefined,{method:"POST",headers:{"Content-Type":"application/json","Idempotency-Key":crypto.randomUUID()},body:JSON.stringify({expected_version:expectedVersion})});
  if(!validateMission(value))throw new Error("The local service returned an invalid mission after the command.");
  return value;
}
export async function advanceMissionClock(scenarioId:string,clock:MissionClock,stateVersion:number,seconds:number) {
  const value=await request(`scenarios/${encodeURIComponent(scenarioId)}/missions/clock/advance`,undefined,{method:"POST",headers:{"Content-Type":"application/json","Idempotency-Key":crypto.randomUUID()},body:JSON.stringify({expected_version:clock.version,expected_state_version:stateVersion,seconds})});
  if(!value||typeof value!=="object"||!("clock" in value)||!validateMissionClock(value.clock)||!("missions" in value)||!Array.isArray(value.missions)||!value.missions.every(item=>validateMission(item)))throw new Error("The local service returned an invalid mission progress response.");
  return value as {clock:MissionClock;missions:Mission[];infrastructure_revision:number};
}
export async function controlMissionClock(scenarioId:string,clock:MissionClock,action:"pause"|"resume") {
  const value=await request(`scenarios/${encodeURIComponent(scenarioId)}/missions/clock/${action}`,undefined,{method:"POST",headers:{"Content-Type":"application/json","Idempotency-Key":crypto.randomUUID()},body:JSON.stringify({expected_version:clock.version})});
  if(!validateMissionClock(value))throw new Error("The local service returned an invalid mission clock response.");
  return value;
}
export async function requestMissionRoute(missionId:string,expectedVersion:number) {
  const value=await request(`missions/${encodeURIComponent(missionId)}/route-proposal`,undefined,{method:"POST",headers:{"Content-Type":"application/json","Idempotency-Key":crypto.randomUUID()},body:JSON.stringify({expected_version:expectedVersion})});
  if(!validateMission(value))throw new Error("The local service returned an invalid route proposal.");
  return value;
}
export async function approveMissionRoute(missionId:string,expectedVersion:number,routeRevisionId:string) {
  const value=await request(`missions/${encodeURIComponent(missionId)}/route-approval`,undefined,{method:"POST",headers:{"Content-Type":"application/json","Idempotency-Key":crypto.randomUUID()},body:JSON.stringify({expected_version:expectedVersion,route_revision_id:routeRevisionId})});
  if(!validateMission(value))throw new Error("The local service returned an invalid route approval response.");
  return value;
}
export async function fetchMissionEvents(missionId:string,signal?:AbortSignal):Promise<MissionEvent[]> {
  const value:unknown=await request(`missions/${encodeURIComponent(missionId)}/events`,signal);
  if(!Array.isArray(value)||!value.every(item=>validateMissionEvent(item)))throw new Error("The local service returned an invalid mission event timeline.");
  return value as MissionEvent[];
}

export async function cancelScenarioExperiment(experimentId: string): Promise<ScenarioExperiment> {
  const value = await request(`scenario-experiments/${encodeURIComponent(experimentId)}/cancel`, undefined, {method:"POST"});
  if (!validateExperiment(value)) throw new Error("The local service returned an invalid experiment cancellation response.");
  return value;
}

export async function closeScenarioRoad(scenarioId: string, roadId: string, reason: string) {
  return request(`scenarios/${encodeURIComponent(scenarioId)}/road-closures`, undefined, {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({road_id:roadId,reason})});
}

export async function decideRescuePlan(planId: string, action: "approved"|"rejected", expectedVersion: number, reason: string) {
  const value = await request(`rescue-plans/${encodeURIComponent(planId)}/decision`, undefined, {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({action,expected_version:expectedVersion,reason})});
  if (!validateRescuePlan(value)) throw new Error("The local service returned an invalid rescue decision.");
  return value;
}

export async function fetchRobustnessBaseline(scenarioId:string,signal?:AbortSignal):Promise<RobustnessBaseline>{
  return await request(`scenarios/${encodeURIComponent(scenarioId)}/robustness-baseline`,signal) as RobustnessBaseline;
}
export async function createRobustnessStudy(scenarioId:string,baseline:RobustnessBaseline,conditions:RobustnessCondition[],horizon:number,planId?:string):Promise<RobustnessStudy>{
  return await request(`scenarios/${encodeURIComponent(scenarioId)}/robustness-studies`,undefined,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({scenario_id:scenarioId,expected_state_version:baseline.simulation_state_version,expected_epoch:baseline.scenario_epoch,expected_infrastructure_revision:baseline.infrastructure_revision,original_plan_id:planId??null,evaluation_horizon_ticks:horizon,conditions})}) as RobustnessStudy;
}
export async function fetchRobustnessStudy(studyId:string,signal?:AbortSignal):Promise<RobustnessStudy>{
  return await request(`robustness-studies/${encodeURIComponent(studyId)}`,signal) as RobustnessStudy;
}
export async function fetchRobustnessStudies(scenarioId:string,signal?:AbortSignal):Promise<RobustnessStudy[]>{
  return await request(`scenarios/${encodeURIComponent(scenarioId)}/robustness-studies?limit=10`,signal) as RobustnessStudy[];
}

export async function fetchHealth(): Promise<Health> {
  const value = (await request("health")) as Health;
  if (value.status !== "ok" || value.mode !== "local")
    throw new Error("The local health response is invalid.");
  return value;
}

export async function fetchBuilding(
  id: string,
  city: CityState,
  signal?: AbortSignal,
): Promise<Building> {
  const value = await request(
    `city/buildings/${encodeURIComponent(id)}`,
    signal,
  );
  const expected = city.buildings.find((b) => b.id === id);
  if (!expected || JSON.stringify(value) !== JSON.stringify(expected))
    throw new Error(
      "Building details do not match the city snapshot. Refresh the city.",
    );
  return value as Building;
}
