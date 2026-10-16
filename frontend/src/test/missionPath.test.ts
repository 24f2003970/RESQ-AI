import { describe, expect, it } from "vitest";
import { sampleMissionRoute } from "../scene/missionPath";

describe("mission route sampling", () => {
  it("follows a right-angle polyline without cutting across its corner", () => {
    const route = { polyline: [[0, 0], [10, 0], [10, 10]], polyline_xyz: [[0, 0, 0], [10, 0, 0], [10, 10, 0]], segment_lengths_m: [10, 10] };
    expect(sampleMissionRoute(route, 5)?.position).toEqual([5, 0, -0]);
    expect(sampleMissionRoute(route, 10)?.position).toEqual([10, 0, -0]);
    expect(sampleMissionRoute(route, 15)?.position).toEqual([10, 0, -5]);
    expect(sampleMissionRoute(route, 15)?.segmentIndex).toBe(1);
  });

  it("preserves bridge elevation, segment heading and the route endpoint", () => {
    const route = { polyline: [[0, 0], [10, 0]], polyline_xyz: [[0, 0, 0], [10, 0, 4]], segment_lengths_m: [10] };
    expect(sampleMissionRoute(route, 5)?.position).toEqual([5, 2, -0]);
    expect(sampleMissionRoute(route, 5)?.yaw).toBeCloseTo(-Math.PI / 2);
    expect(sampleMissionRoute(route, 50)?.position).toEqual([10, 4, -0]);
  });
});
