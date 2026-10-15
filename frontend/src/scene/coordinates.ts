import type { Position } from "../api/client";

/** Backend: east X, north Y, elevation. Scene: east X, up Y, south Z. */
export function toScene(p: Position): [number, number, number] {
  return [p.x_m, p.elevation_m ?? 0, -p.y_m];
}
