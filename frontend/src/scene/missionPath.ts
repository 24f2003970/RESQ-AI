export type MissionRouteGeometry = {
  polyline: number[][];
  polyline_xyz?: number[][] | null;
  segment_lengths_m?: number[] | null;
};

export type MissionRouteSample = {
  position: [number, number, number];
  segmentIndex: number;
  yaw: number;
};

/** Samples authoritative distance along the saved route, preserving segment corners and bridge height. */
export function sampleMissionRoute(route: MissionRouteGeometry, distanceM: number): MissionRouteSample | null {
  const points = route.polyline_xyz?.length === route.polyline.length
    ? route.polyline_xyz
    : route.polyline.map(([x, y]) => [x, y, 0]);
  if (points.length < 2 || points.some((point) => point.length < 3 || point.slice(0, 3).some((value) => !Number.isFinite(value)))) return null;
  const lengths = points.slice(0, -1).map((point, index) => {
    const declared = route.segment_lengths_m?.[index];
    return Number.isFinite(declared) && (declared ?? 0) >= 0
      ? declared as number
      : Math.hypot(points[index + 1][0] - point[0], points[index + 1][1] - point[1], points[index + 1][2] - point[2]);
  });
  let remaining = Math.max(0, Number.isFinite(distanceM) ? distanceM : 0);
  let segmentIndex = lengths.length - 1;
  for (let i = 0; i < lengths.length; i += 1) {
    if (remaining <= lengths[i] || i === lengths.length - 1) { segmentIndex = i; break; }
    remaining -= lengths[i];
  }
  const length = lengths[segmentIndex];
  const ratio = length > 0 ? Math.min(1, remaining / length) : 1;
  const a = points[segmentIndex];
  const b = points[segmentIndex + 1];
  const dx = b[0] - a[0];
  const dy = b[1] - a[1];
  return {
    position: [a[0] + dx * ratio, a[2] + (b[2] - a[2]) * ratio, -(a[1] + dy * ratio)],
    segmentIndex,
    yaw: Math.atan2(-dx, dy),
  };
}
