# Part 8 — Mission Lifecycle Implementation

Part 8 adds a local, deterministic post-approval mission simulator. It is fictional planning software; it does not contact responders, verify evacuation, or claim lives saved.

## Delivery scope

- Approval transactionally creates one `ready` mission per assignment and reserves its unit. Backfill runs when the mission schema is initialized and derives records from historical approved plan payloads without rewriting those plans.
- Dispatch is an explicit, versioned command. Route geometry and graph edge IDs are copied from the approved assignment. A mission clock advances movement over those backend route segments.
- Infrastructure changes block only dispatched missions with a newly inaccessible remaining segment. Replacement routes are stored as proposals and require commander approval before motion resumes.
- Arrival, simulated completion, cancellation, and return-to-service are separate persisted operations. Replay reads the append-only mission event timeline and has no operational side effects.
- REST responses use Pydantic schemas; the exported OpenAPI schemas are consumed and AJV-validated in the frontend.

## State and transactions

`missions` is authoritative for mission status and route progress; `unit_resources` is authoritative for unit availability and current simulated position. `mission_clocks`, `mission_events`, `mission_clock_events`, and command tables persist clock state, audit entries, and idempotency responses. Plan approval, reservation, and mission creation share the PlanStore SQLite transaction. Mission commands and progress use `BEGIN IMMEDIATE` and expected versions.

Scenario epoch is part of each mission/resource/clock key. Reset starts a new active epoch; historical rows remain queryable with `?epoch=` and cannot accept commands. Replay returns recorded mission events rather than mutating live state.

## Reproduction

From `backend/`, run `python -m pytest -q`, then `python benchmark_missions.py`. From `frontend/`, run `npm test`, `npm run lint`, `npm run typecheck`, and `npm run build`. `python export_contract.py` followed by `npm run generate-api` refreshes the checked-in API contracts.

See [mission lifecycle](MISSION_LIFECYCLE.md), [clock model](MISSION_CLOCK_MODEL.md), [release policy](RESOURCE_RELEASE_POLICY.md), [event contract](MISSION_EVENT_CONTRACT.md), [demo guide](MISSION_DEMO_GUIDE.md), and [verification](PART_08_VERIFICATION.md).
