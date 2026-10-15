# Flood Simulation Method (Part 3)

## Purpose and limits

This is a deterministic, educational surface-water model for a fictional city. It is not a calibrated hydraulic solver, flood warning, safety assessment, or operational forecast. It omits calibrated hydrology, soil moisture, spatially varying rainfall, sewer networks, levees, buildings as flow obstructions, momentum, and boundary inflows beyond the modeled canal.

## Grid and units

The domain is 660 m east-west × 500 m north-south, represented by 33 × 25 square cells, each 20 m on a side (400 m²). Each cell stores water depth in metres over synthetic terrain elevation in metres. The canonical coordinates are east X, north Y, elevation up. The channel is a 52 m wide stage-controlled strip centered at Y=0. Model ticks are fixed at 300 simulated seconds; UI speed changes wall-clock interval only, not model physics.

## Per-tick update

For every cell, rainfall contributes a uniform depth

`rain_mm_h / 1000 × 300 / 3600 × 0.75` metres.

The 0.75 runoff coefficient means the remaining 25% is assumed to infiltrate or otherwise not enter surface storage; only effective runoff is counted as `rainfall_m3`. Drainage then removes up to `15 mm/hour × drainage_effectiveness × 300/3600` metres per land cell, bounded by water present. Channel cells are exempt from drainage.

The model computes free-surface head as terrain elevation plus depth. On each four-neighbor edge, water flows from higher to lower head by 15% of the head difference. Simultaneous proposed outflow from a cell is scaled so it cannot exceed 45% of that cell's available water for that tick. Transfers conserve volume and cannot create negative depth. There is no flux beyond the grid boundary (closed boundary). This explicit donor cap and fixed tick are stability choices for this small educational grid, not a general numerical stability proof for calibrated hydraulics.

At the end of each tick, each channel cell is adjusted to `max(river_level_m - terrain_m, 0)`. Any increase is counted as river inflow; any decrease is counted as river outflow. This is an idealized reservoir boundary, not a routed river-flow model.

## Water accounting

The stored volume is the sum of cell depths times 400 m². The expected accounting is:

`initial + effective rainfall + river inflow - river outflow - drainage = stored`.

The API reports these volumes and `balance_error_m3`; finite precision may leave a small floating-point residual. Internal lateral transfers cancel by construction. The model does not count the assumed infiltration fraction as surface input.

## Exposure and access rules

- A building is exposed at sampled footprint water depth ≥ 0.05 m. Its reported max/mean depth and exposed-cell fraction are synthetic indicators; categories are watch ≥0.05 m, moderate ≥0.30 m, severe ≥1.0 m.
- A road is caution at ≥0.10 m, flooded at ≥0.30 m, otherwise open.
- A bridge closes if sampled water surface reaches within 0.15 m of its deck. An open elevated bridge span is skipped when sampling road-bed depth, so flooded ground beside it does not automatically close it.

These thresholds express transparent prototype rules, not engineering standards. Physical depth, accessibility status, and human rescue priority are distinct; Part 3 computes the first two only.

## 3D projection

The frontend receives terrain and flood depth grids from FastAPI. It renders one indexed height-field water surface whose vertices are terrain plus backend depth, colors it by depth, and interpolates display geometry between server snapshots. Roads/buildings/facilities share the terrain frame. Rendering interpolation does not modify or predict simulation state. The grid mesh avoids creating one React mesh per cell. A lower-graphics mode and inventory fallback remain available.
