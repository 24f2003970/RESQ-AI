import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import React from "react";
import type { ScenarioEnvelope } from "../api/client";
import ScenarioLab from "../components/ScenarioLab";
import fixture from "./fixtures/scenario.json";
afterEach(() => vi.unstubAllGlobals());

function Harness() {
  const initial = fixture as ScenarioEnvelope;
  const [state, setState] = React.useState(initial);
  return <ScenarioLab envelope={state} scenario={state.state} error="" onChange={setState} onRetry={() => {}} />;
}

describe("Scenario Lab controls and persisted replay", () => {
  it("sends conditions and single-step commands to the backend, then seeks a read-only tick", async () => {
    let current = JSON.parse(JSON.stringify(fixture)) as ScenarioEnvelope;
    const request = vi.fn(async (input: string, init?: RequestInit) => {
      const method = init?.method ?? "GET";
      if (method === "PATCH") {
        const body = JSON.parse(String(init?.body)) as Record<string, number>;
        delete body.expected_version;
        current = {
          ...current,
          state: {
            ...current.state,
            parameters: { ...current.state.parameters, ...body },
            state_version: current.state.state_version + 1,
          },
        };
      } else if (input.endsWith("/advance")) {
        current = {
          ...current,
          state: {
            ...current.state,
            tick: current.state.tick + 1,
            simulated_seconds: current.state.simulated_seconds + 300,
            state_version: current.state.state_version + 1,
            maximum_depth_m: 0.18,
          },
        };
      } else if (input.endsWith("/replay/0")) {
        current = { ...current, state: { ...current.state, tick: 0, simulated_seconds: 0, status: "paused" } };
      }
      return new Response(JSON.stringify(current), { status: 200, headers: { "Content-Type": "application/json" } });
    });
    vi.stubGlobal("fetch", request);
    const { unmount } = render(<Harness />);

    fireEvent.change(screen.getByRole("slider", { name: "Rainfall intensity" }), { target: { value: "60" } });
    fireEvent.click(screen.getByRole("button", { name: "Apply conditions" }));
    await waitFor(() => expect(request).toHaveBeenCalledWith(
      "/api/v1/scenarios/scenario-riverside-2026/parameters",
      expect.objectContaining({ method: "PATCH" }),
    ));
    expect(JSON.parse(String(request.mock.calls[0][1]?.body))).toMatchObject({ rainfall_mm_h: 60, expected_version: 1 });

    fireEvent.click(screen.getByRole("button", { name: /Step \+5 min/ }));
    await screen.findByText("00:05");
    expect(request).toHaveBeenCalledWith(
      "/api/v1/scenarios/scenario-riverside-2026/advance",
      expect.objectContaining({ method: "POST", body: expect.stringContaining('"single_step":true') }),
    );
    expect(screen.getByText(/0\.18 m/)).toBeInTheDocument();

    const seek = screen.getByRole("slider", { name: "Replay simulation tick" });
    fireEvent.change(seek, { target: { value: "0" } });
    fireEvent.pointerUp(seek);
    await screen.findByText("Replay view");
    expect(request).toHaveBeenCalledWith(
      "/api/v1/scenarios/scenario-riverside-2026/replay/0",
      expect.any(Object),
    );
    unmount();
  });
});
