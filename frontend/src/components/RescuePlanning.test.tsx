import { afterEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import RescuePlanning from "./RescuePlanning";
import type { CityState, ScenarioState } from "../api/client";

describe("RescuePlanning unreachable destinations", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("explains unsupported graph access without dumping every destination id", async () => {
    const destinations = Array.from({ length: 72 }, (_, index) => ({
      building_id: `building-${index}`,
      reason: "No traversable road corridor supports a ground-vehicle route under current closures.",
    }));
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        plan_id: "rc1-plan",
        scenario_id: "rc1-scenario",
        scenario_version: 4,
        simulation_tick: 6,
        status: "proposed",
        priorities: [],
        missions: [],
        available_assignments: [],
        unreachable: destinations,
        comparison: {
          baseline: { destinations_covered: 0, total_distance_m: 0 },
          optimized: { destinations_covered: 0, total_distance_m: 0 },
        },
        solver_status: "optimal_linear_sum_assignment",
        objective: "synthetic objective",
        explanation: "legacy persisted wording",
      }),
    }));

    render(<RescuePlanning city={{ buildings: [], roads: [] } as unknown as CityState}
      scenario={{ id: "rc1-scenario", state_version: 4, tick: 6 } as ScenarioState}
      onPlan={() => undefined} />);
    fireEvent.click(screen.getByRole("button", { name: "Generate recommendation" }));

    expect(await screen.findByText("72 destinations have no supported route in this scenario")).toBeTruthy();
    expect(screen.getByText(/No mission is created for these destinations/)).toBeTruthy();
    expect(screen.getByText(/explicitly returns each unit to service/)).toBeTruthy();
    await waitFor(() => expect(screen.queryByText(/building-71/)).toBeNull());
  });
});
