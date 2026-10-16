import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import ScenarioComparison from "../components/ScenarioComparison";
import scenarioFixture from "./fixtures/scenario.json";
import cityFixture from "./fixtures/city.json";
import type { CityState, ScenarioState } from "../api/client";

describe("Scenario Intelligence Lab builder", () => {
  it("starts both variants from the same visible snapshot and exposes real city roads and duration controls", () => {
    const state = scenarioFixture.state as ScenarioState;
    const city = cityFixture as CityState;
    render(<ScenarioComparison scenario={state} city={city} />);

    expect(screen.getByText(new RegExp(`Seed ${state.seed} · tick ${state.tick} · version ${state.state_version}`))).toBeTruthy();
    expect(screen.getByLabelText("Variant A road closures").querySelectorAll("option").length).toBe(city.roads.length);
    expect(screen.getByLabelText("Variant B road closures").querySelectorAll("option").length).toBe(city.roads.length);
    expect(screen.getByText("6 ticks · 30 minutes")).toBeTruthy();
    fireEvent.change(screen.getAllByLabelText("Preset")[0], { target: { value: "heavy" } });
    expect(screen.getByText("90 mm/h")).toBeTruthy();

    const horizon = screen.getByRole("slider", { name: /additional simulation horizon/i });
    fireEvent.change(horizon, { target: { value: "30" } });
    expect(screen.getByText("30 ticks · 150 minutes")).toBeTruthy();
  });
});
