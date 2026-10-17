# Decision Robustness Study Contract

## Identity

A study contains a unique study ID; source scenario ID; scenario epoch, simulation state version, tick, seed and infrastructure revision; original rescue proposal ID; frozen available and reserved unit IDs; frozen resource positions; a SHA-256 snapshot identity; baseline plan reference and metrics; intervention definitions; evaluation horizon; algorithm version; per-condition outputs; study status; completion time; and reproduction metadata.

The snapshot hash covers the serialized scenario state, including the physical depth grid, parameters, impacts, and version identity. The canonical idempotency identity also includes the infrastructure revision, the exact frozen manual road-closure IDs, semantically relevant original plan, request conditions, and algorithm version. The frozen closure IDs are also stored in reproduction metadata and retained as an analytical baseline for every condition. Volatile plan IDs, timestamps, and timing fields do not change the idempotency identity.

## Status values

`pending`, `running`, `completed`, `failed`, and `interrupted` are explicit. Only `completed` records contain complete results. A study can also be marked `stale` after completion when its live scenario epoch, state version, or infrastructure revision changes.

## Isolation

Rows are stored in the dedicated experiment database. No hypothetical closure is inserted into the operational road-closure table. Plans created during evaluation remain in-memory analytical values and are never inserted into operational rescue plans. No mission, unit, approval, or outbox operation is called. Resource commitments are read from the current mission inventory and held fixed in the saved snapshot.

## API

- `GET /api/v1/scenarios/{scenario_id}/robustness-baseline`
- `POST /api/v1/scenarios/{scenario_id}/robustness-studies`
- `GET /api/v1/scenarios/{scenario_id}/robustness-studies?limit=10`
- `GET /api/v1/robustness-studies/{study_id}`

Creation requires `expected_state_version`, `expected_epoch`, and `expected_infrastructure_revision`; mismatches return a conflict. A final `BEGIN IMMEDIATE` recheck protects the persisted snapshot from state, closure, or reservation changes that occur during proposal construction. The transaction holds a write-intent lock briefly and makes no operational writes.

## Failure behavior

Unknown infrastructure or resource IDs are rejected. Missing local model/calibration artifacts produce the existing degraded/unavailable status and physical fallback. Unsupported prediction rows remain ineligible under the established policy. A worker exception is stored as `failed` with an explicit error; a process restart marks pending work `interrupted`. One local worker runs at a time and condition count/horizon are bounded.
