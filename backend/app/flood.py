"""Deterministic, volume-accounted educational cell-based flood model.

Each cell stores a depth in metres over 20 m terrain cells. Effective rainfall is
uniform and enters as an explicit volume source. Canal cells are held to the
configured stage and exchange a counted volume with the river reservoir.
Neighbour transfers follow free-surface head (terrain + depth), are capped per
donor, and therefore cannot create or destroy water. Drainage is an explicit,
bounded sink. This is not a calibrated hydraulic or forecasting model.
"""

from dataclasses import dataclass

import numpy as np

from .terrain import CELL_SIZE_M, GRID_HEIGHT, GRID_WIDTH, terrain_at, terrain_grid

CELL_AREA_M2 = CELL_SIZE_M**2
STEP_SECONDS = 300
CHANNEL_HALF_WIDTH_M = 26.0
MIN_EXPOSURE_M = 0.05
ROAD_CAUTION_M = 0.10
ROAD_FLOODED_M = 0.30
BUILDING_MODERATE_M = 0.30
BUILDING_SEVERE_M = 1.0
BRIDGE_CLEARANCE_M = 0.15
DRAINAGE_CAPACITY_MM_H = 15.0


@dataclass(frozen=True)
class SimulationParameters:
    rainfall_mm_h: float = 0.0
    river_level_m: float = -0.8
    drainage_effectiveness: float = 0.55
    speed: float = 1.0


def initial_depth(seed: int, river_level_m: float = -0.8) -> np.ndarray:
    """Dry land with the initial canal reservoir at its configured stage."""
    terrain = terrain_grid(seed)
    return np.where(channel_mask(), np.maximum(river_level_m - terrain, 0.0), 0.0)


def channel_mask() -> np.ndarray:
    ys = -250.0 + CELL_SIZE_M * (np.arange(GRID_HEIGHT) + 0.5)
    return np.broadcast_to((np.abs(ys) <= CHANNEL_HALF_WIDTH_M)[:, None], (GRID_HEIGHT, GRID_WIDTH))


def step(depth: np.ndarray, seed: int, params: SimulationParameters, steps: int = 1) -> tuple[np.ndarray, dict[str, float]]:
    """Advance fixed 300 s ticks and return new depth plus cumulative accounting."""
    water = np.asarray(depth, dtype=np.float64).copy()
    if water.shape != (GRID_HEIGHT, GRID_WIDTH) or np.any(water < 0):
        raise ValueError("Depth grid has an invalid shape or negative values")
    terrain = terrain_grid(seed)
    channel = channel_mask()
    totals = {"rainfall_m3": 0.0, "river_in_m3": 0.0, "river_out_m3": 0.0,
              "drainage_m3": 0.0, "initial_m3": float(water.sum() * CELL_AREA_M2)}
    dt = STEP_SECONDS
    for _ in range(steps):
        # 75% of precipitation becomes immediate surface runoff; the rest is an
        # explicit infiltration/loss assumption and is not added to surface water.
        rain_depth = params.rainfall_mm_h / 1000.0 * dt / 3600.0 * 0.75
        rain = np.full_like(water, rain_depth)
        water += rain
        totals["rainfall_m3"] += float(rain.sum() * CELL_AREA_M2)

        # Drainage removes at most the water currently in each cell.
        drain_depth = np.minimum(
            water,
            DRAINAGE_CAPACITY_MM_H / 1000.0 * params.drainage_effectiveness * dt / 3600.0,
        )
        drain_depth = np.where(channel, 0.0, drain_depth)
        water -= drain_depth
        totals["drainage_m3"] += float(drain_depth.sum() * CELL_AREA_M2)

        # Compute one-way transfers on each undirected edge from free-surface
        # head. 15% of a head difference per tick is moved before donor limiting.
        head = terrain + water
        out = np.zeros_like(water)
        edges = []
        for a, b, left, right in (
            (head[:, :-1], head[:, 1:], (slice(None), slice(None, -1)), (slice(None), slice(1, None))),
            (head[:-1, :], head[1:, :], (slice(None, -1), slice(None)), (slice(1, None), slice(None))),
        ):
            donor_a = a > b
            raw = np.abs(a - b) * 0.15
            flow_a = raw * donor_a
            flow_b = raw * ~donor_a
            out[left] += flow_a
            out[right] += flow_b
            edges.append((left, right, flow_a, flow_b))
        # Limit simultaneous total outflow to 45% of available cell depth.
        scale = np.minimum(1.0, np.divide(0.45 * water, out, out=np.ones_like(out), where=out > 0))
        water -= out * scale
        for left, right, flow_a, flow_b in edges:
            flow_a = flow_a * scale[left]
            flow_b = flow_b * scale[right]
            water[left] += flow_b
            water[right] += flow_a
        np.maximum(water, 0.0, out=water)

        # The channel is a stage-controlled reservoir. Adjustment in either
        # direction is counted as a river source/sink at the end of each tick.
        target = np.maximum(params.river_level_m - terrain, 0.0)
        delta = np.where(channel, target - water, 0.0)
        inflow_depth = np.maximum(delta, 0.0)
        outflow_depth = np.maximum(-delta, 0.0)
        water += inflow_depth - outflow_depth
        totals["river_in_m3"] += float(inflow_depth.sum() * CELL_AREA_M2)
        totals["river_out_m3"] += float(outflow_depth.sum() * CELL_AREA_M2)

    accounted = (totals["initial_m3"] + totals["rainfall_m3"] + totals["river_in_m3"]
                 - totals["river_out_m3"] - totals["drainage_m3"])
    totals["stored_m3"] = float(water.sum() * CELL_AREA_M2)
    totals["balance_error_m3"] = totals["stored_m3"] - accounted
    return water, totals


def impact_assessment(city, depth: np.ndarray, seed: int, river_level_m: float) -> dict:
    """Sample simulated depth along entity footprints and publish rule-based impacts."""
    ys = -250.0 + CELL_SIZE_M * (np.arange(GRID_HEIGHT) + 0.5)
    xs = -330.0 + CELL_SIZE_M * (np.arange(GRID_WIDTH) + 0.5)

    def sample(x: float, y: float) -> float:
        ix = int(np.clip(np.floor((x + 330.0) / CELL_SIZE_M), 0, GRID_WIDTH - 1))
        iy = int(np.clip(np.floor((y + 250.0) / CELL_SIZE_M), 0, GRID_HEIGHT - 1))
        return float(depth[iy, ix])

    buildings = []
    for b in city.buildings:
        x0, x1 = b.position.x_m - b.width_m / 2, b.position.x_m + b.width_m / 2
        y0, y1 = b.position.y_m - b.depth_m / 2, b.position.y_m + b.depth_m / 2
        mask = (xs[None, :] >= x0) & (xs[None, :] <= x1) & (ys[:, None] >= y0) & (ys[:, None] <= y1)
        values = depth[mask]
        local = values if values.size else np.asarray([sample(b.position.x_m, b.position.y_m)])
        maximum = float(local.max())
        exposed_fraction = float(np.mean(local >= MIN_EXPOSURE_M))
        category = "severe" if maximum >= BUILDING_SEVERE_M else "moderate" if maximum >= BUILDING_MODERATE_M else "watch" if maximum >= MIN_EXPOSURE_M else "none"
        buildings.append({"entity_id": b.id, "max_depth_m": round(maximum, 4),
                          "mean_depth_m": round(float(local.mean()), 4),
                          "exposed_fraction": round(exposed_fraction, 3), "category": category,
                          "water_reaches_building": maximum >= MIN_EXPOSURE_M})

    bridges = []
    bridge_by_road = {}
    for bridge in city.bridges:
        ground_depth = sample(bridge.position.x_m, bridge.position.y_m)
        water_surface = terrain_at(bridge.position.x_m, bridge.position.y_m, seed) + ground_depth
        if abs(bridge.position.y_m) <= 30:
            water_surface = max(water_surface, river_level_m)
        overtopped = water_surface >= bridge.position.elevation_m - BRIDGE_CLEARANCE_M
        item = {"entity_id": bridge.id, "max_depth_m": round(ground_depth, 4),
                        "deck_elevation_m": round(bridge.position.elevation_m, 3),
                        "water_surface_m": round(water_surface, 3),
                        "status": "closed" if overtopped else "open"}
        bridges.append(item)
        bridge_by_road[bridge.road_id] = item

    roads = []
    for road in city.roads:
        count = max(2, int(road.length_m / (CELL_SIZE_M / 2)))
        bridge = bridge_by_road.get(road.id)
        values = []
        for t in np.linspace(0.0, 1.0, count):
            x = road.start.x_m + (road.end.x_m - road.start.x_m) * t
            y = road.start.y_m + (road.end.y_m - road.start.y_m) * t
            # A clear elevated span is evaluated at deck height rather than
            # inheriting the water depth in the canal bed below it.
            if bridge and bridge["status"] == "open":
                bridge_entity = next(b for b in city.bridges if b.id == bridge["entity_id"])
                # Expand the geometric deck span by half a cell so raster cells
                # straddling the deck ends do not leak canal-bed depth onto it.
                clear_span = max(bridge_entity.length_m / 2 + CELL_SIZE_M / 2,
                                 CHANNEL_HALF_WIDTH_M + CELL_SIZE_M / 2)
                if abs(y - bridge_entity.position.y_m) <= clear_span:
                    continue
            values.append(sample(x, y))
        maximum = max(values, default=0.0)
        if bridge and bridge["status"] == "closed":
            maximum = max(maximum, bridge["water_surface_m"] - bridge["deck_elevation_m"])
        status = "flooded" if maximum >= ROAD_FLOODED_M else "caution" if maximum >= ROAD_CAUTION_M else "open"
        roads.append({"entity_id": road.id, "max_depth_m": round(maximum, 4), "status": status})
    return {"buildings": buildings, "roads": roads, "bridges": bridges}
