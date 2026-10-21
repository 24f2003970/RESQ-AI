import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { CityState, ScenarioEnvelope } from "../api/client";
import CityInventory from "../components/CityInventory";
import SceneControls from "../components/SceneControls";
import SceneSelection from "../components/SceneSelection";
import cityFixture from "./fixtures/city.json";
import scenarioFixture from "./fixtures/scenario.json";

const city = cityFixture as CityState;
const scenario = (scenarioFixture as ScenarioEnvelope).state;
const building = city.buildings[0];
const wetScenario = { ...scenario, impacts: { ...scenario.impacts, buildings: scenario.impacts.buildings.map((impact) => impact.entity_id === building.id ? { ...impact, max_depth_m: 0.75, water_reaches_building: true } : impact) } };

describe("3D exploration controls", () => {
  it("keeps unavailable camera destinations disabled and exposes usable inventory controls", () => {
    const command = vi.fn(), inventory = vi.fn();
    const props = { inventory: false, lighting: "daylight", hasSelection: false, hasFlood: false, hasBridge: true, hasMission: false, onCommand: command, onLighting: vi.fn(), onInventory: inventory };
    const view = render(<SceneControls {...props}/>);
    expect(screen.getByRole("button", { name: "Focus selected building" })).toBeDisabled();
    expect(screen.getByRole("option", { name: /Flood hotspot/ })).toBeDisabled();
    expect(screen.getByRole("option", { name: /Selected mission/ })).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "Zoom in" }));
    expect(command).toHaveBeenCalledWith("zoom-in");
    fireEvent.click(screen.getByRole("button", { name: "Show building inventory" }));
    expect(inventory).toHaveBeenCalledOnce();
    view.rerender(<SceneControls {...props} inventory/>);
    expect(screen.getByRole("button", { name: "Zoom in" })).toBeDisabled();
    expect(screen.getByRole("combobox", { name: "Lighting preset" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Show 3D city" })).toBeEnabled();
  });

  it("filters authoritative building impacts, searches identity and preserves selection", () => {
    const choose = vi.fn();
    render(<CityInventory city={city} scenario={wetScenario} selected={building} onSelect={choose}/>);
    fireEvent.click(screen.getByRole("checkbox", { name: "Only buildings reached by water" }));
    expect(screen.getByRole("status")).toHaveTextContent(`1 of ${city.buildings.length} buildings`);
    expect(screen.getByText(/0.75 m maximum depth/)).toBeInTheDocument();
    const result = screen.getByText(building.name).closest("button")!;
    expect(result).toHaveAttribute("aria-pressed", "true");
    fireEvent.click(result);
    expect(choose).toHaveBeenCalledWith(building.id);
    fireEvent.change(screen.getByRole("searchbox", { name: "Search buildings" }), { target: { value: "no-such-building" } });
    expect(screen.getByText(/No buildings match/)).toBeInTheDocument();
    fireEvent.change(screen.getByRole("searchbox", { name: "Search buildings" }), { target: { value: building.id } });
    expect(screen.getByText(building.name)).toBeInTheDocument();
  });

  it("keeps missing physical data unavailable rather than labeling buildings dry", () => {
    render(<CityInventory city={city} scenario={null} selected={null} onSelect={vi.fn()}/>);
    expect(screen.getByRole("checkbox")).toBeDisabled();
    expect(screen.getByRole("status")).toHaveTextContent("physical state unavailable");
    expect(screen.getAllByText("Current depth unavailable")).toHaveLength(city.buildings.length);
    expect(screen.queryByText(/Water has not reached/)).not.toBeInTheDocument();
  });

  it("shows physical depth even when no model estimate is available", () => {
    render(<SceneSelection building={building} scenario={wetScenario} predictions={null} mission={null}/>);
    expect(screen.getByText(/0.75 m maximum depth · water reaches building/)).toBeInTheDocument();
    expect(screen.getByText("No current supported estimate available")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /More building details/ })).toHaveAttribute("href", "#building-details");
  });
});
