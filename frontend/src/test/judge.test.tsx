import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { AgentDashboard, MLModelInfo, RescueRecommendation, ScenarioEnvelope, ScenarioPredictionSet } from "../api/client";
import App from "../App";
import { judgeFacts } from "../components/judgeFacts";
import cityFixture from "./fixtures/city.json";
import scenarioFixture from "./fixtures/scenario.json";

const mocks = vi.hoisted(() => ({
  dashboardRequest: vi.fn(), recommendationRequest: vi.fn(), missionsRequest: vi.fn(), unitsRequest: vi.fn(),
  city: null as unknown, envelope: null as unknown, risk: null as unknown, sceneFails: false,
}));

vi.mock("../api/client", () => ({
  fetchAgentDashboard: mocks.dashboardRequest,
  fetchLatestRecommendation: mocks.recommendationRequest,
  fetchMissions: mocks.missionsRequest,
  fetchMissionUnits: mocks.unitsRequest,
}));
vi.mock("../api/useCity", () => ({ useCity: () => ({ city: mocks.city, status: "online", error: "", retry: vi.fn() }) }));
vi.mock("../api/useScenario", () => ({ useScenario: () => ({ envelope: mocks.envelope, scenario: (mocks.envelope as ScenarioEnvelope).state, error: "", retry: vi.fn(), accept: vi.fn() }) }));
vi.mock("../api/useRisk", () => ({ useRisk: () => mocks.risk }));
vi.mock("../components/CityWorkspace", () => ({ default: ({ scenario }: { scenario: { id: string } }) => <h1>Command Center scenario {scenario.id}</h1> }));
vi.mock("../scene/CityScene", () => ({ default: () => { if (mocks.sceneFails) throw new Error("WebGL unavailable"); return <div data-testid="judge-city-scene">City scene</div>; } }));

const typedCity = cityFixture as unknown as import("../api/client").CityState;
const typedEnvelope = scenarioFixture as unknown as ScenarioEnvelope;
const scenario = typedEnvelope.state;
const predictions = {
  scenario_id: scenario.id,
  scenario_state_version: scenario.state_version,
  scenario_tick: scenario.tick,
  model_version: "synthetic-v1",
  horizon_minutes: 30,
  predictions: [{ predicted_future_exposed: true }],
} as unknown as ScenarioPredictionSet;
const plan = {
  plan_id: "plan-current", scenario_id: scenario.id, scenario_version: scenario.state_version,
  scenario_epoch: scenario.epoch, infrastructure_revision: 1, status: "proposed", explanation: "A synthetic route was selected from current constraints.",
  missions: [], available_assignments: [], priorities: [], unreachable: [], solver_status: "optimal",
  objective: "test", comparison: { optimized: { destinations_covered: 1 }, baseline: { destinations_covered: 0 } },
} as unknown as RescueRecommendation;
const traceId = "persisted-event-for-judge";
const dashboard = {
  scenario_id: scenario.id, scenario_epoch: scenario.epoch, simulation_state_version: scenario.state_version,
  infrastructure_revision: 1, definitions: [], latest_runs: [], pending_events: 0,
  commander_action_required: true, approved_route_review_required: false, reserved_ground_units: [],
  latest_trace: { trace_id: "trace-1", event_id: traceId, scenario_id: scenario.id, scenario_epoch: scenario.epoch,
    simulation_state_version: scenario.state_version, infrastructure_revision: 1, status: "completed",
    summary: "Persisted assessment trace is available.", created_at_utc: "2026-01-01T00:00:00Z" },
} as unknown as AgentDashboard;

function arrange() {
  mocks.city = typedCity;
  mocks.envelope = typedEnvelope;
  mocks.risk = { model: { status: "ready", model_version: "synthetic-v1" }, predictions, error: "" };
  mocks.sceneFails = false;
  mocks.dashboardRequest.mockResolvedValue(dashboard);
  mocks.recommendationRequest.mockResolvedValue(plan);
  mocks.missionsRequest.mockResolvedValue([]);
  mocks.unitsRequest.mockResolvedValue([]);
}

afterEach(() => { vi.clearAllMocks(); });

describe("Judge Mode", () => {
  it("uses the application scenario, distinguishes physical and predicted exposure, and requires commander review", async () => {
    arrange();
    render(<MemoryRouter initialEntries={["/judge"]}><App/></MemoryRouter>);
    expect(await screen.findByRole("heading", { name: "Judge Mode" })).toBeInTheDocument();
    expect(await screen.findByText("Physically exposed buildings")).toBeInTheDocument();
    expect(screen.getByText("Predicted future exposure")).toBeInTheDocument();
    expect(await screen.findByText("Commander review required. No approval is performed in Judge Mode.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /approve/i })).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: /open commander review/i })).toHaveAttribute("href", "/");
    expect(screen.getByRole("link", { name: "View decision evidence" })).toHaveAttribute("href", `/decisions?event=${traceId}`);
    expect(screen.getByRole("list", { name: "Evidence stage status" })).toHaveTextContent("CommanderPending");
  });

  it("exits to Command Center with the same scenario state", async () => {
    arrange();
    render(<MemoryRouter initialEntries={["/judge"]}><App/></MemoryRouter>);
    fireEvent.click(await screen.findByRole("link", { name: "Exit Judge Mode" }));
    expect(await screen.findByRole("heading", { name: `Command Center scenario ${scenario.id}` })).toBeInTheDocument();
  });

  it("does not show prediction counts from a stale simulation version", () => {
    const facts = judgeFacts({
      scenario, predictions: { ...predictions, scenario_state_version: scenario.state_version - 1 },
      dashboard, recommendation: plan, missions: [], model: { status: "ready", model_version: "synthetic-v1" } as MLModelInfo,
    });
    expect(facts.predictionCurrent).toBe(false);
    expect(facts.predicted).toBeNull();
    expect(facts.stages.find((stage) => stage.label === "Model")?.status).toBe("pending");
    expect(facts.stages.find((stage) => stage.label === "Commander")?.status).toBe("pending");
    const oldModel = judgeFacts({
      scenario, predictions: { ...predictions, model_version: "previous-model" }, dashboard,
      recommendation: plan, missions: [], model: { status: "ready", model_version: "synthetic-v1" } as MLModelInfo,
    });
    expect(oldModel.predictionCurrent).toBe(false);
  });

  it("marks a proposal unavailable after an infrastructure revision changes", () => {
    const facts = judgeFacts({
      scenario, predictions, dashboard: { ...dashboard, infrastructure_revision: 2 },
      recommendation: plan, missions: [], model: { status: "ready", model_version: "synthetic-v1" } as MLModelInfo,
    });
    expect(facts.recommendationCurrent).toBe(false);
    expect(facts.pendingApproval).toBe(false);
    expect(facts.stages.find((stage) => stage.label === "Proposal")?.status).toBe("unavailable");
  });

  it("synchronizes the commander stage only after a persisted decision is returned", () => {
    const proposed = judgeFacts({ scenario, predictions, dashboard, recommendation: plan, missions: [], model: { status: "ready", model_version: "synthetic-v1" } as MLModelInfo });
    const approved = judgeFacts({ scenario: { ...scenario, state_version: scenario.state_version + 1 }, predictions, dashboard, recommendation: { ...plan, status: "approved" }, missions: [], model: { status: "ready", model_version: "synthetic-v1" } as MLModelInfo });
    expect(proposed.stages.find((stage) => stage.label === "Commander")?.status).toBe("pending");
    expect(approved.stages.find((stage) => stage.label === "Commander")?.status).toBe("recorded");
    expect(approved.recommendationCurrent).toBe(false);
  });

  it("announces unavailable evidence and exposes the low-graphics control", async () => {
    arrange();
    mocks.dashboardRequest.mockRejectedValue(new Error("Backend unavailable"));
    render(<MemoryRouter initialEntries={["/judge"]}><App/></MemoryRouter>);
    expect(await screen.findByRole("alert")).toHaveTextContent("Could not refresh agent status");
    const lowGraphics = screen.getByRole("checkbox", { name: "Low graphics" });
    expect(lowGraphics).toBeChecked();
    lowGraphics.focus();
    expect(document.activeElement).toBe(lowGraphics);
    fireEvent.click(lowGraphics);
    expect(lowGraphics).not.toBeChecked();
  });

  it("keeps backend exposure evidence available when the 3D scene fails", async () => {
    arrange();
    mocks.sceneFails = true;
    render(<MemoryRouter initialEntries={["/judge"]}><App/></MemoryRouter>);
    expect(await screen.findByRole("status", { name: "City map fallback" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Simulated max depth" })).toBeInTheDocument();
  });
});
