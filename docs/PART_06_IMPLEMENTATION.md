# Part 6 implementation

Part 6 adds a local, deterministic coordination pipeline to the existing Part 5 simulation and rescue-planning contracts. It uses algorithmic agents, SQLite and REST polling. It uses no hosted model/API, does not execute missions, and leaves every proposal for a human commander.

## Implemented agents

1. **Hazard Intelligence** reads the committed flood state and local 30-minute exposure model. It records current and newly predicted exposed buildings, depth increases of at least 0.05 m, rainfall, river stage, and model status. Missing local model artifacts produce an explicit degraded rule-based assessment; the service does not invent future predictions. Probabilities are synthetic and uncalibrated.
2. **Impact Assessment** compares measured building, road and bridge impacts against the previous completed assessment in the same scenario epoch. It reports access status changes and hospital/shelter exposure; it does not infer structural damage.
3. **Rescue Priority** reuses Part 5's 0–100 transparent formula and reports score deltas of at least 3 points and newly top-five destinations.
4. **Routing** reuses the NetworkX road graph and Dijkstra constraints with flood status, bridge status and current manual closures. Boats remain unsupported; unreachable pairs are explicit.
5. **Resource Allocation** reuses the Part 5 SciPy `linear_sum_assignment` optimizer, its nearest-unit baseline, capacities and unique-unit/unique-destination constraints, excluding already approved units.
6. **Commander / Strategy** evaluates material changes, suppresses equivalent proposals, and persists a versioned plan for review. It never approves or executes.

The dependency order is fixed and persisted: hazard → impact → priority → routing → allocation → commander. Inputs are immutable scenario/event snapshots with input hashes and compact output summaries.

## API

- `GET /api/v1/agents/registry`
- `GET /api/v1/scenarios/{id}/agent-status`
- `GET /api/v1/scenarios/{id}/agent-events?limit=30`
- `GET /api/v1/scenarios/{id}/agent-runs?limit=100`
- `GET /api/v1/scenarios/{id}/recommendations/latest`
- `GET /api/v1/agent-traces/{event_id}`
- `POST /api/v1/scenarios/{id}/intelligence-assessments` (202; queues a durable event)
- `POST /api/v1/agent-events/{event_id}/retry` (bounded to three attempts)

Generated OpenAPI and TypeScript contracts live under `frontend/src/api/`. AJV checks dashboard, event, trace and recommendation responses. The UI polls every 2.5–3 seconds and ignores obsolete request responses. REST polling is the chosen local fallback; there is no WebSocket or SSE dependency.

## Safety and replay

Simulation commands write scenario state and corresponding agent outbox events in one SQLite transaction. Manual closures and rescue decisions also write their outbox events in the same transaction as their mutations. Plan persistence locks the database and checks scenario version, epoch, infrastructure revision, and approved resource reservations. Approval repeats these checks and commits the decision and event atomically. A road closure increments a scenario/epoch-scoped revision; reset starts a new epoch with no inherited manual closures or reservations. Existing approved plans remain historical; if a currently blocked road intersects one, status reports a commander-review alert without changing approval or mission state.

Outbox processing is at least once. A SQLite `BEGIN IMMEDIATE` status claim protects against multiple processors; run uniqueness `(event_id, agent_name)` and plan uniqueness by trigger prevent duplicate effects. A restarted service resets interrupted events to pending and retries no more than three attempts. Results whose snapshot is no longer current are marked superseded. Historical simulation replay is a read-only reconstruction and never enqueues or applies operational events. Replay can reconstruct simulation state and transition history; agent records and traces remain separately queryable but replay does not recompute prior model versions.

## Trigger policy

Triggers include scenario creation, parameter updates, each committed simulation advance, reset, physical access changes carried by simulation events, manual road close/reopen, and rescue approval/rejection. The commander requires a new/predicted exposed destination, depth increase ≥0.05 m, measured road/bridge transition, route change/invalidation, priority delta ≥3, reset/manual assessment, infrastructure revision, or new approved-resource reservation. No wall-clock cooldown is used: equivalent assignment/route/priority signatures are suppressed, and small changes are retained as traces without creating duplicate proposals. This lets meaningful route closures replan immediately.

## Signature demo

Follow `PART_06_VERIFICATION.md` and `AGENT_DEMO_SCENARIO.md`. The benchmark uses seed 2026, extreme preset, rainfall 300 mm/h, river level 5 m, drainage 0, and 120 deterministic steps. A closure example is accepted only if the actual route edge sequence changes; see the automated `road-ew-1` reroute test.

## Scope limits

This was the Part 6 scope: it did not provide calibrated flood prediction, casualties/survivors, structural damage, boats/water rescue, live data, communications, real dispatch, crew movement, mission completion or resource release. Part 8 later added simulated mission lifecycle, explicit completion and commander return-to-service. Units are not released automatically; reset starts a new epoch. Do not use this system to make real emergency decisions.
