import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import DemoMode from "../components/DemoMode";
import fixture from "./fixtures/scenario.json";
import type { ScenarioEnvelope } from "../api/client";

const api = vi.hoisted(() => ({
  createScenario: vi.fn(),
  updateScenarioParameters: vi.fn(),
  advanceScenario: vi.fn(),
}));
vi.mock("../api/client", () => ({
  ...api,
  advanceScenario: api.advanceScenario,
  closeScenarioRoad: vi.fn(), createScenarioExperiment: vi.fn(), decideRescuePlan: vi.fn(),
  fetchAgentDashboard: vi.fn(), fetchAgentEvents: vi.fn(), fetchAgentTrace: vi.fn(),
  fetchLatestRecommendation: vi.fn(), fetchMLModel: vi.fn(), fetchScenarioPredictions: vi.fn(),
  fetchScenarioExperiment: vi.fn(), requestIntelligenceAssessment: vi.fn(), resetScenario: vi.fn(),
  updateScenarioParameters: api.updateScenarioParameters,
}));

describe("guided demo", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.createScenario.mockResolvedValue(fixture as ScenarioEnvelope);
    api.updateScenarioParameters.mockImplementation(async (state) => ({ ...fixture, state: { ...state, state_version: state.state_version + 1 } }));
    api.advanceScenario.mockImplementation(async (state, steps) => ({ ...fixture, state: { ...state, tick: steps, simulated_seconds: steps * 300, affected_buildings: 59, exposed_roads: 8 } }));
  });

  it("transitions through real initialization and flood actions using the configured 12 ticks", async () => {
    const onChange = vi.fn();
    render(<MemoryRouter><DemoMode scenario={null} onChange={onChange}/></MemoryRouter>);
    fireEvent.click(screen.getByRole("button", { name: /initialize demo scenario/i }));
    await waitFor(() => expect(screen.getByText(/Stage 2 · Flood event/i)).toBeTruthy());
    expect(api.createScenario).toHaveBeenCalledOnce();
    fireEvent.click(screen.getByRole("button", { name: /apply severe flood/i }));
    await waitFor(() => expect(screen.getByText(/Stage 3 · AI risk intelligence/i)).toBeTruthy());
    expect(api.advanceScenario).toHaveBeenCalledWith(expect.anything(), 12, true);
    expect(screen.getByText(/59 physically exposed buildings/)).toBeTruthy();
  });

  it("shows a failed authoritative action without advancing the demo stage", async () => {
    api.createScenario.mockRejectedValue(new Error("local service unavailable"));
    render(<MemoryRouter><DemoMode scenario={null} onChange={() => {}}/></MemoryRouter>);
    fireEvent.click(screen.getByRole("button", { name: /initialize demo scenario/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent("local service unavailable");
    expect(screen.getByText(/Stage 1 · Initial city/i)).toBeTruthy();
  });
});
