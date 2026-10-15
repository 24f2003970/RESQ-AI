# System Architecture

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
  ├─ Command Center / Studio / Scenario Lab / Decision Explorer / Model Lab
  ├─ React Three Fiber scene (projection of API state)
  └─ REST commands + WebSocket state/event stream
                 │ localhost only
FastAPI modular monolith
  ├─ API and schema validation
  ├─ Scenario and city state service
  ├─ Deterministic flood simulation
  ├─ Risk model adapter + transparent baseline
  ├─ Event bus / agent coordinator
  ├─ Prioritization, routing, assignment, and approval services
  └─ SQLite event and scenario persistence
                 │
       Local model artifact + configuration
```

### Frontend

React, TypeScript, Vite, Tailwind CSS, shadcn/ui, Framer Motion, React Three Fiber, Three.js, and Recharts are the preferred stack. Keep API types in a shared generated or hand-maintained schema package to avoid drift. The canvas consumes versioned city/scenario snapshots and event deltas. It submits commands such as `advance_simulation`, `close_road`, `request_plan`, `approve_plan`, and `reject_plan`; it does not compute authoritative flood depth, prediction, route, or assignment.

### Backend

FastAPI modules live in one process. Pydantic models validate requests and responses. A deterministic simulation service updates state in explicit time steps. A coordinator subscribes to domain events and invokes only the agents affected by the change. SQLite stores scenarios, event records, plans, reviews, and model metadata. WebSockets publish committed state versions and events; reconnecting clients fetch a full snapshot before applying deltas.

Initial API surface:

- `GET /api/v1/health`
- `GET /api/v1/city?seed=...`
- `GET /api/v1/scenarios/{id}` and `POST /api/v1/scenarios`
- `POST /api/v1/scenarios/{id}/advance`
- `POST /api/v1/scenarios/{id}/roads/{road_id}/closure`
- `POST /api/v1/scenarios/{id}/plans` (proposal only)
- `POST /api/v1/scenarios/{id}/plans/{plan_id}/review`
- `GET /api/v1/scenarios/{id}/events`
- `GET /api/v1/model/report`
- `WS /api/v1/scenarios/{id}/stream`

Use request IDs and monotonically increasing state versions. Reject stale commands when a client submits a version that no longer matches the server state.

## Canonical state and event flow

The `ScenarioState` contains city geometry IDs, flood-cell depths, asset conditions, road availability, resource positions/capacities, active missions, model outputs, pending plan, event sequence, simulated time, and deterministic random state. Each accepted command creates a domain event and a state version. The reducer/simulation service applies the event, stores it, then sends it to the coordinator. The coordinator calculates a new proposal and records agent decisions; it does not perform a rescue action. Human approval creates a separate review event and only then changes mission/unit state.

Flood progression is a deliberately small grid process: rainfall contributes runoff; terrain/elevation, local storage, channel proximity, and flow to lower neighboring cells govern bounded redistribution; river-stage forcing raises channel-adjacent cells; road/building thresholds produce simulated access and damage states. The equations, cell size, time step, and assumptions are versioned and visible in the UI. This is a demo process model, not a hydraulic solver.

## Agent coordination

Agents are event-driven workers with explicit transitions (`idle → triggered → evaluating → proposed/failed → recorded`). The coordinator deduplicates events by scenario version and agent type, records dependencies and input hashes, and does not let parallel workers mutate shared state directly. It commits a complete proposal as one transaction. A failed agent yields a partial-plan status with the missing component visible; it never appears as a complete plan.

| Agent | Trigger and input | Output / method | Validation |
|---|---|---|---|
| Hazard & Risk Intelligence | rainfall, river stage, time step; grid and assets | flood step plus per-cell classifier and rule-baseline scores | seed replay, bounds, holdout scenario metrics |
| Damage Assessment | flood-depth or shaking-state change; asset thresholds | simulated asset/access states and confidence/source labels | threshold boundary tests, event consistency |
| Rescue Priority | risk/damage/access change; population, vulnerability, facilities | deterministic priority score and contributions | hand-calculated fixtures, monotonicity checks |
| Routing | road closure, depth/access change, new assignment | NetworkX shortest safe path with hazard and distance costs | blocked-edge and disconnected-graph fixtures |
| Resource Allocation | priorities, unit availability/capacity, reachable paths | feasible unit-to-mission proposal | capacity, uniqueness, cost comparison on small cases |
| Command / Strategy | all upstream results for one state version | ordered draft plan, trade-offs, warnings | no side effects pre-approval; replay and schema checks |

Rules, scoring weights, model artifact version, and route costs are scenario metadata. Agents are cooperating algorithmic components; no language model is required or implied.

## Digital Twin contract

The backend `City` and evolving `ScenarioState` are the only source of truth. Each frontend object carries a stable ID and references an API entity. The scene maps coordinates and elevations to geometry, colors risk/depth through independently switchable layers, and interpolates display animation between server snapshots. Interaction selects an entity and requests its current state. Visual interpolation must not modify its underlying state.

A seed-based generator creates a bounded fictional terrain grid, river, districts, road graph, buildings, hospitals, shelters, bridges, and rescue units. It uses named random streams so a change to building placement does not silently change rainfall or unit allocation. Generator and simulation versions are persisted with each scenario.

## Offline and security boundaries

- Bind the service to loopback by default; document explicit host binding if needed for a local LAN demo.
- No hosted inference, tracking, telemetry, or automatic data downloads at runtime.
- Data preparation is an explicit offline step. Raw and large derived data is gitignored.
- Secrets stay in environment variables and `.env` remains ignored; provide `.env.example` only if configuration is later needed.
- HTTP and WebSocket traffic remains local. Never use real personal or emergency incident data in the demo.

## Deployment shape

For the hackathon, run a local FastAPI process and Vite-built frontend on one laptop. A desktop wrapper, containers, remote database, and multi-service deployment are deferred unless a concrete integration need arises.
