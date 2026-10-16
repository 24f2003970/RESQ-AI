# System Architecture

> **Implementation status through Part 8:** The local FastAPI service owns flood scenario state, local ML inference, rescue routing and assignment, human review, six durable event-triggered algorithmic agents, isolated reproducible A/B experiments, and persistent fictional rescue mission progression. Coordination uses a SQLite outbox and REST polling; experiments use a separate SQLite database. There is no WebSocket/SSE dependency. Boat navigation remains unsupported.

## Design principles

1. Build a modular monolith that starts with one local command.
2. Keep one authoritative scenario state in the Python service.
3. Separate the flood process model from the learned risk classifier.
4. Make agent triggers, transitions, and outputs observable and replayable.
5. Prefer deterministic algorithms and modest dependencies that can be explained live.
6. Label simulated evidence and avoid operational forecasting claims.

## Logical components

```text
React + TypeScript application
  ├─ Command Center / Studio / Scenario Lab / Decision Explorer / Model Lab / Guided Demo
  ├─ React Three Fiber scene (projection of API state)
  └─ REST commands + safe polling of committed state/events
                 │ localhost only
FastAPI modular monolith
  ├─ API and schema validation
  ├─ Scenario and city state service
  ├─ Deterministic flood simulation
  ├─ Risk model adapter + transparent baseline
  ├─ SQLite outbox / ordered agent coordinator
  ├─ Prioritization, routing, assignment, and approval services
  ├─ Mission state machine, operational clock, route movement, and resource lifecycle
  ├─ SQLite operational event and scenario persistence
  └─ Isolated experiment snapshot/results database and worker
                 │
       Local model artifact + configuration
```

### Frontend

React, TypeScript, Vite, Tailwind CSS, shadcn/ui, Framer Motion, React Three Fiber, Three.js, and Recharts are the preferred stack. Keep API types in a shared generated or hand-maintained schema package to avoid drift. The canvas consumes versioned city/scenario snapshots and event deltas. It submits commands such as `advance_simulation`, `close_road`, `request_plan`, `approve_plan`, and `reject_plan`; it does not compute authoritative flood depth, prediction, route, or assignment.

### Backend

FastAPI modules live in one process. Pydantic models validate requests and responses. A deterministic simulation service updates state in explicit time steps. State-changing producers enqueue durable events in SQLite transactions; the ordered agent coordinator processes them independently of browser rendering. SQLite stores scenarios, outbox events, agent runs, traces, plans, reviews, and model metadata. The frontend polls committed versioned responses and ignores stale results.

Initial API surface:

- `GET /api/v1/health`
- `GET /api/v1/city/state`
- `GET /api/v1/scenarios/{id}` and `POST /api/v1/scenarios`
- `POST /api/v1/scenarios/{id}/advance`
- `POST /api/v1/scenarios/{id}/road-closures` and `DELETE /api/v1/scenarios/{id}/road-closures/{road_id}`
- `POST /api/v1/scenarios/{id}/rescue-plans` and `POST /api/v1/rescue-plans/{plan_id}/decision`
- `GET /api/v1/scenarios/{id}/events`
- `GET /api/v1/scenarios/{id}/agent-status`, `/agent-events`, `/agent-runs`, and `/recommendations/latest`
- `GET /api/v1/agent-traces/{event_id}`
- `POST /api/v1/scenarios/{id}/intelligence-assessments`
- `POST /api/v1/scenarios/{id}/experiments`, `GET /api/v1/scenarios/{id}/experiments`, `GET /api/v1/scenario-experiments/{experiment_id}`, and `POST /api/v1/scenario-experiments/{experiment_id}/cancel`

Use request IDs and monotonically increasing state versions. Reject stale commands when a client submits a version that no longer matches the server state.

## Canonical state and event flow

The `ScenarioState` contains city geometry IDs, flood-cell depths, asset conditions, road availability, resource positions/capacities, active missions, model outputs, pending plan, event sequence, simulated time, and deterministic random state. Each accepted command creates a domain event and a state version. The reducer/simulation service applies the event, stores it, then sends it to the coordinator. The coordinator calculates a new proposal and records agent decisions; it does not perform a rescue action. Human approval creates a separate review event and only then changes mission/unit state.

Flood progression is a deliberately small grid process: rainfall contributes runoff; terrain/elevation, local storage, channel proximity, and flow to lower neighboring cells govern bounded redistribution; river-stage forcing raises channel-adjacent cells; road/building thresholds produce simulated access and damage states. The equations, cell size, time step, and assumptions are versioned and visible in the UI. This is a demo process model, not a hydraulic solver.

## Agent coordination

Agents are local event-driven workers ordered as Hazard Intelligence → Impact Assessment → Rescue Priority → Routing → Resource Allocation → Commander / Strategy. The durable outbox is written atomically with scenario updates, manual infrastructure revisions, and rescue decisions. `AgentOrchestrator` claims events in SQLite, deduplicates by event/agent, persists hashes and compact traces, validates epoch/version/revision before each stage, and rechecks plan freshness and reservations when saving. A failed dependency remains visible and downstream stages are skipped until retry; the Commander can only create a proposal, never approve or execute one. The UI polls trace endpoints and does not trigger the backend pipeline.

| Agent | Trigger and input | Output / method | Validation |
|---|---|---|---|
| Hazard Intelligence | committed flood state and local future exposure | new exposure/depth delta; synthetic classifier label | thresholds, missing-model degraded behavior |
| Impact Assessment | previous same-epoch assessment plus physical impacts | changed building, road and bridge states; facility exposure | no inferred structural damage |
| Rescue Priority | existing Part 5 score inputs | ranked eligible locations and significant score deltas | stable transparent formula |
| Routing | current graph, flood status, manual closures | compatible ground routes, changed/invalidated pairs, unreachable sites | blocked-edge and actual reroute test |
| Resource Allocation | route map, capacities, approved reservations | SciPy optimal assignment plus nearest-unit baseline | unit/destination uniqueness, reservations |
| Commander / Strategy | validated upstream outputs and trigger policy | versioned proposal, suppression rationale, or no-plan trace | no side effects before explicit approval |

Rules, scoring weights, model artifact version, and route costs are scenario metadata. Agents are cooperating algorithmic components; no language model is required or implied.

## Digital Twin contract

The backend `City` and evolving `ScenarioState` are the only source of truth. Each frontend object carries a stable ID and references an API entity. The scene maps coordinates and elevations to geometry, colors risk/depth through independently switchable layers, and interpolates display animation between server snapshots. Interaction selects an entity and requests its current state. Visual interpolation must not modify its underlying state.

A seed-based generator creates a bounded fictional terrain grid, river, districts, road graph, buildings, hospitals, shelters, bridges, and rescue units. It uses named random streams so a change to building placement does not silently change rainfall or unit allocation. Generator and simulation versions are persisted with each scenario.

## Offline and security boundaries

- Bind the service to loopback by default; document explicit host binding if needed for a local LAN demo.
- No hosted inference, tracking, telemetry, or automatic data downloads at runtime.
- Data preparation is an explicit offline step. Raw and large derived data is gitignored.
- Secrets stay in environment variables and `.env` remains ignored; provide `.env.example` only if configuration is later needed.
- HTTP traffic remains local. Never use real personal or emergency incident data in the demo.

## Deployment shape

For the hackathon, run a local FastAPI process and Vite-built frontend on one laptop. A desktop wrapper, containers, remote database, and multi-service deployment are deferred unless a concrete integration need arises.

## Part 3 live scenario path

The browser requests the generated city and active scenario over versioned local REST endpoints. `ScenarioStore` serializes mutations with a process lock and SQLite `BEGIN IMMEDIATE`, checks `expected_version`, applies a fixed flood tick in Python/NumPy, updates derived impacts, records compact transition events, and commits state and events together. The frontend renders returned terrain/depth/impact values; it does not implement hydraulic calculations. Each scenario persists its own seed, parameters, compressed depth array, tick, epoch, version, accounting totals, events, and periodic depth checkpoints. Replay is read-only and reconstructs from the nearest checkpoint plus deterministic tick events.

See [PART_03_IMPLEMENTATION.md](PART_03_IMPLEMENTATION.md) for REST contracts and [FLOOD_SIMULATION_METHOD.md](FLOOD_SIMULATION_METHOD.md) for numerical details.

## Part 7 analytical experiments

`ExperimentRepository` stores a canonical starting snapshot and request in a separate `experiments.sqlite3` file. `ExperimentRunner` imports that snapshot into per-variant scenario namespaces in the same dedicated file, runs the existing `ScenarioStore` stepper for equal durations, applies manual road closures only to the experiment `PlanStore`, and computes the Part 5 route/assignment functions in memory. It never invokes the operational outbox coordinator or persists operational approvals/reservations. ML inference receives the explicit variant `ScenarioState` through `predict_state`.

The Scenario Lab renders chart points from saved result data and lazily reuses one `CityScene` canvas while switching variants. The Guided Demo creates a separate operational scenario because its real event pipeline and commander decision must be observable; its reset preserves old traces as historical and starts a new scenario epoch. See [SCENARIO_COMPARISON.md](SCENARIO_COMPARISON.md), [PART_07_IMPLEMENTATION.md](PART_07_IMPLEMENTATION.md), and [HACKATHON_DEMO_GUIDE.md](HACKATHON_DEMO_GUIDE.md).

## Part 8 mission operations

Approval creates reserved `ready` missions; dispatch remains an explicit command. The mission clock is independent of the five-minute flood clock, and only backend progression changes mission position or arrival. `unit_resources` is authoritative for availability and current unit position; `missions` is authoritative for mission state and route progress. Scenario epoch, flood state version, mission version, and infrastructure revision are checked at operational boundaries.

A committed road closure blocks a dispatched mission only when it intersects a not-yet-traversed route segment. The Routing Agent can calculate a replacement proposal from a blocked unit's verified current route segment; only commander approval of a current proposal resumes travel. Arrival is distinct from explicit simulated completion. Completion and dispatched cancellation leave units unavailable until an explicit restore at their persisted location. Reset starts a new epoch while retaining prior mission history. The frontend follows the approved route polyline for display only, interpolating no farther than authoritative backend traversed-distance snapshots; it cannot progress mission state. See [MISSION_LIFECYCLE.md](MISSION_LIFECYCLE.md) and [MISSION_CLOCK_MODEL.md](MISSION_CLOCK_MODEL.md).
