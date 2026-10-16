import { describe, expect, it } from "vitest";
import type { Building } from "../api/client";
import { buildingVisualProfile, floodDepthBand, floodSurfaceColor, floodSurfaceOpacity, terrainSampleGrid } from "../scene/visualData";

const building = (use: Building["use"], floors = 2) => ({ use, floors, material_color: "#aabbcc" } as Building);

describe("Digital Twin visual data", () => {
  it("maps backend flood depths to stable readable bands", () => {
    expect([0.1, 0.5, 1.5, 2.5].map(floodDepthBand)).toEqual(["shallow", "moderate", "deep", "very-deep"]);
    expect(floodSurfaceColor(0.1)).not.toBe(floodSurfaceColor(2.5));
    expect(floodSurfaceOpacity(2)).toBeGreaterThan(floodSurfaceOpacity(0.2));
    expect(floodSurfaceOpacity(10)).toBeLessThanOrEqual(0.88);
  });

  it("distinguishes facilities and homes without changing their backend geometry", () => {
    expect(buildingVisualProfile(building("hospital")).trim).not.toBe(buildingVisualProfile(building("shelter")).trim);
    expect(buildingVisualProfile(building("residential", 2)).form).toBe("home");
    expect(buildingVisualProfile(building("residential", 6)).form).toBe("commercial");
    expect(buildingVisualProfile(building("commercial")).wall).toBe("#aabbcc");
  });

  it("interpolates terrain elevations between authoritative grid samples", () => {
    const grid = [[0, 10], [20, 30]];
    expect(terrainSampleGrid(grid, -310, -230)).toBe(15);
    expect(terrainSampleGrid(grid, -320, -240)).toBe(0);
    expect(terrainSampleGrid(grid, 1000, 1000)).toBe(30);
  });
});
