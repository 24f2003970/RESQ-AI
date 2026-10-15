import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { CityState } from "../api/client";
import { parseCity } from "../api/client";
import { toScene } from "../scene/coordinates";
import App from "../App";
import fixture from "./fixtures/city.json";

vi.mock("../scene/CityScene", () => ({
  default: ({
    city,
    onSelect,
  }: {
    city: CityState;
    onSelect: (id: string) => void;
  }) => (
    <div data-testid="mock-city">
      <button onClick={() => onSelect(city.buildings[0].id)}>
        Select first building
      </button>
    </div>
  ),
}));

const city = fixture as CityState;
function connectedFetch() {
  const mock = vi.fn(async (input: string) => {
    let value: unknown = city;
    if (input.endsWith("/health"))
      value = {
        status: "ok",
        mode: "local",
        version: "0.2.0",
        service: "resq-ai",
      };
    else if (input.includes("/buildings/"))
      value = city.buildings.find((b) => input.endsWith(b.id));
    return new Response(JSON.stringify(value), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  });
  vi.stubGlobal("fetch", mock);
  return mock;
}
afterEach(() => vi.unstubAllGlobals());

describe("API contract and coordinate boundary", () => {
  it("accepts backend data and rejects malformed or empty payloads", () => {
    expect(parseCity(city).city.id).toBe(city.city.id);
    expect(() => parseCity({ ...city, buildings: [] })).toThrow("no buildings");
    expect(() => parseCity({ ...city, roads: "bad" })).toThrow("invalid city");
    expect(() =>
      parseCity({
        ...city,
        buildings: [{ ...city.buildings[0], height_m: -1 }],
      }),
    ).toThrow();
  });
  it("maps north to negative scene Z and elevation to scene Y", () => {
    expect(toScene({ x_m: 20, y_m: 40, elevation_m: 3 })).toEqual([20, 3, -40]);
  });
});

describe("connected application", () => {
  it("loads backend inventory, selects a building and fetches details", async () => {
    const mock = connectedFetch();
    render(
      <MemoryRouter>
        <App />
      </MemoryRouter>,
    );
    await screen.findByRole("heading", { name: /Situation overview/ });
    expect(screen.getByText("Local service connected")).toBeInTheDocument();
    fireEvent.click(
      await screen.findByRole("button", { name: "Select first building" }),
    );
    await screen.findByText(city.buildings[0].name);
    expect(mock).toHaveBeenCalledWith(
      `/api/v1/city/buildings/${city.buildings[0].id}`,
      expect.any(Object),
    );
    expect(
      screen.getByText("Verified against building API"),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Close inspector" }));
    await screen.findByText("A city of connected details.");
  });
  it("supports navigation, layers and future-state honesty", async () => {
    connectedFetch();
    render(
      <MemoryRouter>
        <App />
      </MemoryRouter>,
    );
    await screen.findByTestId("mock-city");
    fireEvent.click(screen.getByRole("button", { name: "Layers" }));
    const checkbox = screen.getByRole("checkbox", { name: "greenery" });
    fireEvent.click(checkbox);
    expect(checkbox).not.toBeChecked();
    fireEvent.click(screen.getByRole("link", { name: "Scenario Lab" }));
    await screen.findByRole("heading", {
      name: "Every response starts with a scenario.",
    });
    expect(screen.getByText(/Under development/)).toBeInTheDocument();
    fireEvent.click(
      screen.getByRole("link", { name: "Model Intelligence Lab" }),
    );
    await screen.findByRole("heading", {
      name: "Evidence before intelligence.",
    });
    expect(
      screen.getByText(/No model has been trained yet/),
    ).toBeInTheDocument();
  });
  it("shows a real connection failure and recovers on retry", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockRejectedValue(new TypeError("Failed to fetch")),
    );
    render(
      <MemoryRouter>
        <App />
      </MemoryRouter>,
    );
    await screen.findByRole("heading", {
      name: /reconnect your command center/,
    });
    connectedFetch();
    fireEvent.click(screen.getByRole("button", { name: "Retry connection" }));
    await screen.findByText("Local service connected");
  });
  it("does not claim a connected city after invalid JSON data", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          new Response(JSON.stringify({ status: "ok", mode: "local" })),
        ),
    );
    render(
      <MemoryRouter>
        <App />
      </MemoryRouter>,
    );
    await screen.findByRole("heading", {
      name: /reconnect your command center/,
    });
    await waitFor(() =>
      expect(screen.queryByTestId("mock-city")).not.toBeInTheDocument(),
    );
  });
});
