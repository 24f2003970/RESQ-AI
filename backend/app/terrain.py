"""Shared deterministic synthetic terrain for the fictional Riverside city."""

from functools import lru_cache

import numpy as np

CELL_SIZE_M = 20.0
GRID_WIDTH = 33
GRID_HEIGHT = 25
X_ORIGIN_M = -330.0
Y_ORIGIN_M = -250.0


@lru_cache(maxsize=8)
def terrain_grid(seed: int = 2026) -> np.ndarray:
    """Return cell-center elevations (m); the canal corridor is a shallow basin."""
    rng = np.random.default_rng(seed ^ 0x52455351)
    xs = X_ORIGIN_M + CELL_SIZE_M * (np.arange(GRID_WIDTH) + 0.5)
    ys = Y_ORIGIN_M + CELL_SIZE_M * (np.arange(GRID_HEIGHT) + 0.5)
    xx, yy = np.meshgrid(xs, ys)
    elevation = (
        0.22
        + 0.0105 * np.abs(yy)
        + 0.00045 * np.abs(xx)
        - 0.30 * np.exp(-((yy / 38.0) ** 2))
        - 1.60 * np.exp(-((yy / 14.0) ** 2))
        - 0.22 * np.exp(-(((xx + 135) / 75) ** 2 + ((yy - 55) / 60) ** 2))
        - 0.18 * np.exp(-(((xx - 165) / 70) ** 2 + ((yy + 35) / 55) ** 2))
        + rng.normal(0.0, 0.045, size=(GRID_HEIGHT, GRID_WIDTH))
    )
    return np.maximum(elevation, -1.25).astype(np.float64)


def terrain_at(x_m: float, y_m: float, seed: int = 2026) -> float:
    """Bilinearly sample the shared terrain grid at a city coordinate."""
    grid = terrain_grid(seed)
    gx = np.clip((x_m - X_ORIGIN_M) / CELL_SIZE_M - 0.5, 0, GRID_WIDTH - 1)
    gy = np.clip((y_m - Y_ORIGIN_M) / CELL_SIZE_M - 0.5, 0, GRID_HEIGHT - 1)
    x0, y0 = int(np.floor(gx)), int(np.floor(gy))
    x1, y1 = min(x0 + 1, GRID_WIDTH - 1), min(y0 + 1, GRID_HEIGHT - 1)
    tx, ty = gx - x0, gy - y0
    top = grid[y0, x0] * (1 - tx) + grid[y0, x1] * tx
    bottom = grid[y1, x0] * (1 - tx) + grid[y1, x1] * tx
    return float(top * (1 - ty) + bottom * ty)


def grid_coordinates() -> tuple[list[float], list[float]]:
    return (
        (X_ORIGIN_M + CELL_SIZE_M * (np.arange(GRID_WIDTH) + 0.5)).tolist(),
        (Y_ORIGIN_M + CELL_SIZE_M * (np.arange(GRID_HEIGHT) + 0.5)).tolist(),
    )
