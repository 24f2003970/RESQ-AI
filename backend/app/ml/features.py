"""Leakage-conscious features shared by dataset generation and local inference."""

from __future__ import annotations

from typing import Any

import numpy as np

from ..city_service import generate_city
from ..flood import SimulationParameters, impact_assessment
from ..terrain import CELL_SIZE_M, terrain_grid

NUMERIC_FEATURES = [
    "current_depth_max_m",
    "current_depth_mean_m",
    "current_exposed_fraction",
    "neighborhood_depth_max_m",
    "neighborhood_depth_mean_m",
    "neighborhood_wet_fraction_005m",
    "neighborhood_wet_fraction_030m",
    "terrain_elevation_m",
    "terrain_neighborhood_mean_m",
    "distance_to_canal_m",
    "river_level_m",
    "terrain_minus_river_m",
    "rainfall_mm_h",
    "drainage_effectiveness",
    "simulation_tick",
    "building_height_m",
    "building_floors",
    "building_width_m",
    "building_depth_m",
    "x_m",
    "y_m",
]
USE_FEATURES = ["use_residential", "use_commercial", "use_hospital", "use_shelter"]
FEATURE_NAMES = NUMERIC_FEATURES + USE_FEATURES
TARGET_NAME = "future_exposed_30m"
HORIZON_TICKS = 6
ENGINE_VERSION = "flood-engine-v1"


def _index(x_m: float, y_m: float) -> tuple[int, int]:
    return (
        int(np.clip(np.floor((x_m + 330.0) / CELL_SIZE_M), 0, 32)),
        int(np.clip(np.floor((y_m + 250.0) / CELL_SIZE_M), 0, 24)),
    )


def build_feature_rows(city, depth: np.ndarray, seed: int, params: SimulationParameters, tick: int) -> list[dict[str, float]]:
    """Extract only current state, parameters, and static building/terrain data."""
    terrain = terrain_grid(seed)
    impacts = impact_assessment(city, depth, seed, params.river_level_m)
    exposure_by_id = {item["entity_id"]: item for item in impacts["buildings"]}
    rows: list[dict[str, float]] = []
    for building in city.buildings:
        x = building.position.x_m
        y = building.position.y_m
        ix, iy = _index(x, y)
        local = depth[max(0, iy - 1):min(depth.shape[0], iy + 2), max(0, ix - 1):min(depth.shape[1], ix + 2)]
        ground = float(terrain[iy, ix])
        exposure = exposure_by_id[building.id]
        row: dict[str, float] = {
            "current_depth_max_m": float(exposure["max_depth_m"]),
            "current_depth_mean_m": float(exposure["mean_depth_m"]),
            "current_exposed_fraction": float(exposure["exposed_fraction"]),
            "neighborhood_depth_max_m": float(local.max()),
            "neighborhood_depth_mean_m": float(local.mean()),
            "neighborhood_wet_fraction_005m": float(np.mean(local >= 0.05)),
            "neighborhood_wet_fraction_030m": float(np.mean(local >= 0.30)),
            "terrain_elevation_m": ground,
            "terrain_neighborhood_mean_m": float(terrain[max(0, iy - 1):min(terrain.shape[0], iy + 2), max(0, ix - 1):min(terrain.shape[1], ix + 2)].mean()),
            "distance_to_canal_m": max(0.0, abs(y) - 26.0),
            "river_level_m": params.river_level_m,
            "terrain_minus_river_m": ground - params.river_level_m,
            "rainfall_mm_h": params.rainfall_mm_h,
            "drainage_effectiveness": params.drainage_effectiveness,
            "simulation_tick": float(tick),
            "building_height_m": building.height_m,
            "building_floors": float(building.floors),
            "building_width_m": building.width_m,
            "building_depth_m": building.depth_m,
            "x_m": x,
            "y_m": y,
        }
        for use in ("residential", "commercial", "hospital", "shelter"):
            row[f"use_{use}"] = float(building.use == use)
        rows.append(row)
    return rows


def feature_matrix(rows: list[dict[str, Any]]) -> np.ndarray:
    return np.asarray([[float(row[name]) for name in FEATURE_NAMES] for row in rows], dtype=np.float64)


def heuristic_score(row: dict[str, Any], horizon_ticks: int = HORIZON_TICKS) -> float:
    """Transparent forecast: local current depth plus net rain/drain input and stage pressure.

    It omits spatial redistribution, making it a distinct, deliberately simple
    comparator rather than a second invocation of the simulator.
    """
    runoff = max(0.0, float(row["rainfall_mm_h"]) * 0.75 - 15.0 * float(row["drainage_effectiveness"]))
    added_depth = runoff / 1000.0 * 300.0 / 3600.0 * horizon_ticks
    river_pressure = max(0.0, -float(row["terrain_minus_river_m"])) * 0.08
    return max(float(row["current_depth_max_m"]), float(row["neighborhood_depth_max_m"]) * 0.5) + added_depth + river_pressure


def heuristic_prediction(row: dict[str, Any], threshold_m: float = 0.05) -> int:
    return int(heuristic_score(row) >= threshold_m)


def target_exposed(city, future_depth: np.ndarray, seed: int, river_level_m: float) -> dict[str, int]:
    impacts = impact_assessment(city, future_depth, seed, river_level_m)
    return {item["entity_id"]: int(item["water_reaches_building"]) for item in impacts["buildings"]}
