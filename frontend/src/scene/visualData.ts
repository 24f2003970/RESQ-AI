import type { Building } from "../api/client";

export type FloodDepthBand = "shallow" | "moderate" | "deep" | "very-deep";

export function floodDepthBand(depthM: number): FloodDepthBand {
  if (depthM < 0.3) return "shallow";
  if (depthM < 1) return "moderate";
  if (depthM < 2) return "deep";
  return "very-deep";
}

export function floodSurfaceColor(depthM: number): string {
  switch (floodDepthBand(depthM)) {
    case "shallow": return "#8bc9c1";
    case "moderate": return "#3d91b4";
    case "deep": return "#235e9a";
    case "very-deep": return "#403873";
  }
}

export function floodSurfaceOpacity(depthM: number): number {
  return 0.48 + Math.min(Math.max(depthM, 0), 2.5) * 0.16;
}

export type BuildingVisualProfile = {
  form: "home" | "commercial" | "institutional";
  wall: string;
  roof: string;
  trim: string;
  window: string;
  entrance: string;
};

/** Rendering style only; all footprint, position, height, and use values stay backend-owned. */
export function buildingVisualProfile(building: Building): BuildingVisualProfile {
  const use = building.use;
  if (use === "hospital") {
    return { form: "institutional", wall: "#d7d8cc", roof: "#778783", trim: "#c95e55", window: "#8db4b0", entrance: "#59645f" };
  }
  if (use === "shelter") {
    return { form: "institutional", wall: "#bdcbb6", roof: "#73877a", trim: "#45ad91", window: "#9ac5b4", entrance: "#526b61" };
  }
  if (use === "commercial") {
    return { form: "commercial", wall: building.material_color, roof: "#566365", trim: "#748d8d", window: "#3e646c", entrance: "#35464a" };
  }
  return { form: building.floors <= 2 ? "home" : "commercial", wall: building.material_color, roof: "#746d5f", trim: "#a99b82", window: "#47616a", entrance: "#594b3e" };
}

export function terrainSampleGrid(grid: number[][], x: number, y: number): number {
  const height = grid.length;
  const width = grid[0]?.length ?? 0;
  if (!width || !height) return 0;
  const gx = Math.max(0, Math.min(width - 1, (x + 320) / 20));
  const gy = Math.max(0, Math.min(height - 1, (y + 240) / 20));
  const x0 = Math.floor(gx), y0 = Math.floor(gy);
  const x1 = Math.min(x0 + 1, width - 1), y1 = Math.min(y0 + 1, height - 1);
  const tx = gx - x0, ty = gy - y0;
  return (grid[y0][x0] * (1 - tx) + grid[y0][x1] * tx) * (1 - ty)
    + (grid[y1][x0] * (1 - tx) + grid[y1][x1] * tx) * ty;
}
