# Part 3 — Flood Simulation and Scenario Engine

## Scope

Part 3 upgrades the existing fictional city to a backend-authoritative flood Digital Twin. It does not add ML, agents, rescue prioritization, routing optimization, or earthquake simulation. The engine is an educational synthetic scenario model, not a real-world warning or calibrated forecast.

## Terrain and coordinates

The existing 660 m × 500 m city uses a seeded 33 × 25 elevation raster at 20 m cell spacing. X is east, Y is north, and elevation is up in the API; Three.js maps north to negative Z and elevation to Y. The generated surface has a low channel along the canal and modest deterministic relief/noise away from it. Building bases, roads, bridge decks, and the water mesh use the same elevation model. City entity IDs and layout remain intact.

## State and SQLite

`backend/app/scenarios.py` owns scenario persistence. SQLite keeps `scenarios` (seed, preset, status, tick, reset epoch, state version, simulated seconds, parameters, initial parameters, compressed depth grid, and volume totals), append-only `events`, periodic `checkpoints` every 12 ticks, and `creation_keys` for idempotent scenario creation. Mutations use `BEGIN IMMEDIATE`, an in-process lock, and optimistic `expected_version`; state and emitted events commit in one transaction. SQLite lives at `backend/data/resq.sqlite3` by default and is ignored by Git. `RESQ_DB_PATH` can select a local alternate path.

The baseline city is regenerated from its seed and remains immutable. Scenario state is stored separately. A reset starts a new epoch, restores the scenario's initial parameters and initial water, resets tick to zero, and preserves previous event history. One active scenario is selected as the most recently created scenario; scenarios otherwise remain isolated by ID.

## API

- `GET /api/v1/scenarios/active`: latest-created scenario.
- `POST /api/v1/scenarios`: create a deterministic scenario; requires `Idempotency-Key`.
- `GET /api/v1/scenarios/{scenario_id}`: current authoritative state and recent events.
- `PATCH /api/v1/scenarios/{scenario_id}/parameters`: update rainfall, river stage, drainage effectiveness, or UI speed with an expected state version.
- `POST /api/v1/scenarios/{scenario_id}/start`, `/pause`, `/resume`: guarded status transitions.
- `POST /api/v1/scenarios/{scenario_id}/advance`: advance fixed five-minute ticks, or one step when paused with `single_step=true`.
- `POST /api/v1/scenarios/{scenario_id}/reset`: restore initial conditions with expected version.
- `GET /api/v1/scenarios/{scenario_id}/events`: retrieve event history.
- `GET /api/v1/scenarios/{scenario_id}/replay/{tick}`: read-only reconstructed state at a current-epoch tick.
- `GET /api/v1/scenarios/{scenario_id}/snapshots`: list persisted checkpoint ticks and versions.

Pydantic constrains identifiers, scenario names, preset values, parameter ranges, step counts, and versions. Unknown scenario IDs return 404; stale versions and illegal transitions return 409; invalid values return 422. Frontend payloads are checked against generated JSON Schema contracts. The frontend never computes flood depths.

## Scenario events

Each event has a stable unique ID, scenario ID, tick, elapsed simulated seconds, state version, type, entity IDs, and compact JSON payload. Events include scenario creation, simulation lifecycle, parameter changes, each simulation tick, compact flood-grid summaries, building exposure category changes, road status transitions, bridge closures/reopenings, and reset. Cell updates are summarized as a batch count and maximum depth rather than one event per cell. Events are derived from committed changes and can be consumed by future agent services.

## Frontend behavior

Scenario Lab exposes mild, heavy-rain, and extreme-rain/river-overflow synthetic presets, editable rainfall, river stage, drainage, simulation speed, start/pause/resume, single-step, reset, elapsed time, depth legend, event timeline, and replay seek. A replay view is paused/read-only. Branching from a past replay point is unsupported. Running advances only while Scenario Lab is active and the document is visible; the timer is cleaned up on navigation/unmount, and leaving the route or hiding the tab requests a pause. Backend errors are surfaced with a retry action.

Command Center metrics (rainfall, elapsed time, maximum land depth, affected buildings, exposed roads, closed bridges, and status) come from the scenario response. The recommendation area remains explicitly unavailable. Existing building inspection remains supported.

## Known limitations

See [FLOOD_SIMULATION_METHOD.md](FLOOD_SIMULATION_METHOD.md) for physical assumptions. This is one-process local SQLite, not a multi-worker service. Replay depends on the current engine implementation and stored parameters; no migration framework for engine versions exists. The synthetic terrain/city and thresholds are not calibrated against geospatial or observed flood data. The browser's local offline mode requires already installed dependencies and a running local backend; runtime inference and hosted APIs are not used.
