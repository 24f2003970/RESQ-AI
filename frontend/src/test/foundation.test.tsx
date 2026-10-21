import { configure, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, useNavigate } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { CityState } from "../api/client";
import type { Layers } from "../scene/CityScene";
import { parseCity } from "../api/client";
import { toScene } from "../scene/coordinates";
import App, { RouteLoadingState } from "../App";
import fixture from "./fixtures/city.json";
import scenarioFixture from "./fixtures/scenario.json";

// Lazy route imports can exceed the default one-second wait on a busy demo laptop.
configure({ asyncUtilTimeout: 10000 });
vi.setConfig({ testTimeout: 20000 });

vi.mock("../scene/CityScene", () => ({
  default: ({
    city,
    onSelect,
    layers,
  }: {
    city: CityState;
    onSelect: (id: string) => void;
    layers: Layers;
  }) => (
    <div data-testid="mock-city" data-predicted-risk={layers.predictedRisk}>
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
        version: "0.3.0",
        service: "resq-ai",
      };
    else if (input.includes("/buildings/"))
      value = city.buildings.find((b) => input.endsWith(b.id));
    else if (input.endsWith("/scenarios/active")) value = scenarioFixture;
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
  it("keeps the overview focused and separates planning from mission controls without issuing commands", async () => {
    const mock = connectedFetch();
    render(<MemoryRouter><App/></MemoryRouter>);
    await screen.findByRole("heading", { name: "Situation overview" });
    expect(screen.queryByRole("heading", { name: "Rescue planning" })).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Mission Operations" })).not.toBeInTheDocument();
    expect(screen.getByText("Advanced tools", {selector:"summary"}).closest("details")).not.toHaveAttribute("open");
    fireEvent.click(screen.getByRole("link", { name: "Open rescue operations" }));
    await screen.findByRole("heading", { name: "Rescue operations" });
    expect(screen.getByRole("heading", { name: "Rescue planning" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Mission Operations" })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("link", { name: "2. Dispatch & track" }));
    expect(await screen.findByRole("heading", { name: "Mission Operations" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Rescue planning" })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("link", { name: "1. Plan & approve" }));
    expect(screen.getByRole("heading", { name: "Rescue planning" })).toBeInTheDocument();
    expect(mock.mock.calls.every((call) => !["POST", "PATCH", "DELETE"].includes((call as unknown as [string, RequestInit])[1]?.method ?? "GET"))).toBe(true);
  });
  it("opens mission controls on a direct mission link and preserves legacy review links", async () => {
    connectedFetch();
    const view = render(<MemoryRouter initialEntries={["/response?view=missions"]}><App/></MemoryRouter>);
    expect(await screen.findByRole("heading", { name: "Mission Operations" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Rescue planning" })).not.toBeInTheDocument();
    view.unmount();
    render(<MemoryRouter initialEntries={["/?review=latest"]}><App/></MemoryRouter>);
    expect(await screen.findByRole("heading", { name: "Rescue planning" })).toBeInTheDocument();
  });
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
    await screen.findByRole("heading", { name: city.buildings[0].name });
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
    const checkbox = screen.getByRole("checkbox", { name: "Greenery" });
    fireEvent.click(checkbox);
    expect(checkbox).not.toBeChecked();
    const predictedLayer = screen.getByRole("checkbox", { name: "Future ML exposure" });
    expect(predictedLayer).not.toBeChecked();
    fireEvent.click(predictedLayer);
    expect(screen.getByTestId("mock-city")).toHaveAttribute("data-predicted-risk", "true");
    fireEvent.click(screen.getAllByRole("link", { name: "Flood simulation" })[0]);
    await screen.findByRole("heading", { name: "Flood simulation" });
    expect(screen.getByRole("slider", { name: "Rainfall intensity" })).toBeInTheDocument();
    expect(screen.getByText("Water depth")).toBeInTheDocument();
    fireEvent.click(screen.getByText("Advanced tools", {selector:"summary"}));
    fireEvent.click(
      screen.getByRole("link", { name: "Model Intelligence Lab" }),
    );
    await screen.findByRole("heading", {
      name: "Model Intelligence Lab",
    });
    expect(
      screen.getByText(/not trained or validated on observed disaster outcomes/i),
    ).toBeInTheDocument();
  });
  it("loads a route-specific fallback without exposing prior workspace controls",()=>{
    render(<RouteLoadingState pathname="/robustness"/>);
    expect(screen.getByRole("status")).toHaveAttribute("aria-busy","true");
    expect(screen.getByRole("heading",{name:"Loading Decision Robustness"})).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveAttribute("data-loading-route","/robustness");
    expect(screen.queryByRole("button",{name:"Generate recommendation"})).not.toBeInTheDocument();
  });
  it("supports first lazy navigation, back, forward, and a second visit",async()=>{
    connectedFetch();
    function HistoryControls(){const navigate=useNavigate();return <><button onClick={()=>navigate(-1)}>Test browser back</button><button onClick={()=>navigate(1)}>Test browser forward</button></>;}
    render(<MemoryRouter initialEntries={["/"]}><HistoryControls/><App/></MemoryRouter>);
    await screen.findByRole("heading",{name:"Situation overview"});
    fireEvent.click(screen.getAllByRole("link",{name:"Flood simulation"})[0]);
    await screen.findByRole("heading",{name:"Flood simulation"});
    fireEvent.click(screen.getByRole("button",{name:"Test browser back"}));
    await screen.findByRole("heading",{name:"Situation overview"});
    fireEvent.click(screen.getByRole("button",{name:"Test browser forward"}));
    await screen.findByRole("heading",{name:"Flood simulation"});
    fireEvent.click(screen.getByText("Advanced tools", {selector:"summary"}));
    fireEvent.click(screen.getByRole("link",{name:"Model Intelligence Lab"}));
    await screen.findByRole("heading",{name:"Model Intelligence Lab"});
    fireEvent.click(screen.getByRole("button",{name:"Test browser back"}));
    await screen.findByRole("heading",{name:"Flood simulation"});
    fireEvent.click(screen.getByText("Advanced tools", {selector:"summary"}));
    fireEvent.click(screen.getByRole("link",{name:"Model Intelligence Lab"}));
    await screen.findByRole("heading",{name:"Model Intelligence Lab"});
    expect(screen.getByRole("link",{name:"Model Intelligence Lab"})).toHaveAttribute("aria-current","page");
  });
  it("renders a direct Scenario Lab route without requiring prior Command Center navigation",async()=>{
    connectedFetch();
    render(<MemoryRouter initialEntries={["/scenarios"]}><App/></MemoryRouter>);
    await screen.findByRole("heading",{name:"Flood simulation"});
    expect(screen.getByRole("link",{name:"Flood simulation"})).toHaveAttribute("aria-current","page");
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
