# Rescue plan contract

`POST /api/v1/scenarios/{scenario_id}/rescue-plans` computes and persists a proposal with scenario ID/version/tick, ranked destinations, routes, assignments, unreachable sites, exact-search status, baseline comparison, and objective. `GET /api/v1/rescue-plans/{plan_id}` retrieves it. `POST /api/v1/rescue-plans/{plan_id}/decision` accepts `{ "action": "approved" | "rejected", "expected_version": n, "reason": "..." }`. A decision is serialized with SQLite `BEGIN IMMEDIATE`; current scenario version and the plan version must match. A stale proposal becomes superseded and cannot be approved. Repeated decisions against a non-proposed record are rejected.

`PATCH /api/v1/rescue-plans/{plan_id}/assignments` accepts an expected version and a list of `{unit_id,destination_id}` pairs. It checks saved route feasibility and enforces unique unit and destination assignment before recomputing comparison metrics. Unit capacity bounds the occupant count targeted by each mission.

Road closure and reopen endpoints update a persistent scenario overlay. Creating or removing a closure supersedes pending proposals. A replacement proposal is generated on explicit request. Approval records commander intent only: Part 5 does not create or execute simulated rescue missions. Plans are Pydantic validated and persisted as JSON plus indexed scenario/version/status columns.

API endpoints return explicit 404/409/422 responses for unknown plans, stale decisions, invalid actions, and unknown road IDs. The scenario database is authoritative for physical state; the closure overlay is authoritative for commander planning constraints.
