import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import ModelLab from "../components/ModelLab";
import scenarioFixture from "./fixtures/scenario.json";
import cityFixture from "./fixtures/city.json";
import dataset from "../../../backend/ml_artifacts/dataset_metadata.json";
import evaluation from "../../../backend/ml_artifacts/evaluation.json";
import type { ScenarioPredictionSet, ScenarioState } from "../api/client";

afterEach(() => vi.unstubAllGlobals());
const scenario = scenarioFixture.state as ScenarioState;
const building = cityFixture.buildings[0];

function response(payload: unknown) { return Promise.resolve(new Response(JSON.stringify(payload), { status: 200, headers: { "Content-Type": "application/json" } })); }

describe("Model Intelligence Lab", () => {
  it("shows saved held-out metrics and distinguishes current from predicted exposure", async () => {
    const prediction: ScenarioPredictionSet = {
      model_version: "rf-v1", scenario_id: scenario.id, scenario_state_version: scenario.state_version,
      scenario_tick: scenario.tick, horizon_ticks: 6, horizon_minutes: 30,
      target_definition: "Synthetic threshold", probabilities_calibrated: false,
      predictions: [{ building_id: building.id, current_exposed: false, current_exposure_category: "none", current_max_depth_m: 0,
        predicted_future_exposed: true, predicted_category: "predicted_exposed", uncalibrated_model_score: 0.84,
        influential_features: [{ name: "river_level_m", value: 0.8, global_permutation_importance: 0.12 }] }],
    };
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/ml/model")) return response({ status: "ready", model_name: "RESQ-AI", model_version: "rf-v1", target: "future_exposed_30m", probabilities_calibrated: false });
      if (url.endsWith("/ml/dataset")) return response(dataset);
      if (url.endsWith("/ml/evaluation")) return response(evaluation);
      if (url.endsWith("/ml/features")) return response([{ name: "river_level_m", description: "Canal stage", units: "m", role: "numeric" }]);
      if (url.includes("/predictions")) return response(prediction);
      throw new Error(`Unexpected API path: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<MemoryRouter><ModelLab scenario={scenario} /></MemoryRouter>);
    expect((await screen.findAllByText("0.966")).length).toBeGreaterThan(0);
    expect(await screen.findByText("Current simulated exposure")).toBeInTheDocument();
    expect(screen.getAllByText("Not exposed").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Exposed").length).toBeGreaterThan(0);
    expect(screen.getByText(/not a probability/)).toBeInTheDocument();
    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
  });

  it("announces unavailable backend data instead of substituting metrics", async () => {
    vi.stubGlobal("fetch", vi.fn(() => Promise.resolve(new Response("", { status: 503 }))));
    render(<MemoryRouter><ModelLab scenario={scenario} /></MemoryRouter>);
    expect(await screen.findByRole("alert")).toBeInTheDocument();
    expect(screen.getAllByText("—").length).toBeGreaterThan(0);
  });
});
