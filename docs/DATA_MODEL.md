# Digital Twin Data Model

## Identity and units

IDs are stable within a generated city and prefixed by entity type. A `city_id` derives from generator version and seed. Scenario state references a specific city snapshot, simulation version, model artifact ID, and monotonically increasing `state_version`. Coordinates use a local Cartesian meter grid with a declared origin; elevation and flood depth are meters; speed is meters/second; rainfall is mm/hour; simulation time is an integer number of seconds from scenario start. These are fictional local coordinates, not georeferenced coordinates.

## Entities

| Entity | Core fields | Evolving fields |
|---|---|---|
| City | id, name, seed, generator_version, bounds, CRS-like local-grid note | static generated entity catalog |
| District | id, city_id, name, land_use, population, vulnerability_index | aggregated flood/risk/access summaries |
| TerrainCell | id, row, col, x, y, elevation_m, roughness, storage | moisture/runoff state if implemented |
| Building | id, district_id, footprint, centroid, floors, use, occupants, vulnerability | depth_m, simulated damage class, risk score/version |
| Road | id, from_node, to_node, polyline, length_m, class, capacity | open/closed, depth_m, damage, travel cost |
| Bridge | id, road_id, river crossing, deck_elevation_m, capacity | open/closed, closure reason |
| RiverSegment | id, geometry, bed_elevation_m, stage_reference | stage_m, flow direction (assumed if not modeled) |
| Hospital | id, building_id, capacity, capabilities | operational state, access state |
| Shelter | id, building_id, capacity, safe-depth threshold | occupancy, safety/access state |
| FloodCell | id, terrain_cell_id, depth_m | depth_m, update time, source step |
| RiskZone | id, district or cell set, exposure summary | severity, priority, rationale, evaluation version |
| RescueUnit | id, type, capacity, speed_mps, base_node | availability, position, assigned mission |
| RescueMission | id, target_zone, requested capacity, objective | proposed/approved/active/completed/blocked status |
| ScenarioEvent | id, scenario_id, sequence, type, simulated time, payload, parent version | append-only record |
| AgentDecision | id, event_id, agent, inputs hash, version, outcome, explanation | status, output references |
| ScenarioState | scenario/city IDs, state version, time, config, entity state maps | authoritative mutable snapshot |

## Core state transitions

1. `ScenarioCreated(seed, config)` asks the generator for a deterministic city and initializes flood, road, asset, and resource state.
2. `SimulationAdvanced(dt, rainfall, river_stage)` applies one bounded time step to the flood grid, then updates affected road/building/facility state through documented thresholds.
3. The coordinator emits `FloodStateChanged`; risk and damage components update for affected cells/assets. Priority, route, allocation, and command proposal run in dependency order.
4. `InfrastructureClosed(road_id, reason)` changes graph availability and triggers route, allocation, and command proposal without rewinding flood state.
5. `PlanProposed(plan_id, based_on_version)` records a draft. `PlanReviewed(approve|reject, plan_id, reviewer)` records the human decision. Approval is rejected if the plan is stale; a fresh proposal is required.
6. Only an approval event can transition missions/units from proposed/available to active/assigned. Simulated movement advances on later ticks.

## Deterministic fictional city generator

- Accept an explicit integer seed plus `generator_version`.
- Use named random streams for terrain, road layout, building placement, population, and initial resources.
- Generate a small local grid with elevation slope, low basin, river channel, bridges, connected road network, districts, facilities, and declared asset counts.
- Validate invariants: unique IDs, road endpoints exist, shelters/hospitals link to buildings, bridges map to a road crossing, rescue units start on valid nodes, and at least one reachable facility exists.
- Store the generator version and seed. A generator change increments the version; saved scenarios never silently regenerate under new rules.

## Flood process and uncertainty

Flooding uses a small deterministic, discrete grid process, not a calibrated hydrodynamic model. Rainfall adds water by cell area and infiltration/storage assumptions. Water redistributes to lower neighboring cells through a bounded flow fraction and exchanges with river-stage forcing; timestep, boundary rules, and numerical caps are fixed and tested. Depth thresholds map to simulated building/road access states. Unmodeled drainage, flood defenses, flow physics, and local terrain accuracy are explicit limitations.

Risk prediction consumes a scenario snapshot, not an independent map. Every prediction records the state version, input features, model ID, and whether it is synthetic-model or rule-baseline output. The frontend never persists a second authoritative copy of evolving entity fields.

## Storage and replay

SQLite stores scenario metadata, append-only event records, proposal/review records, model metadata, and periodic state snapshots. Replay loads the nearest snapshot and applies ordered events using the matching engine version. If historical engine code is unavailable, the UI labels playback as stored events/snapshots, not a recomputation.
