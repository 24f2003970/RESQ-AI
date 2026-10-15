# Decision trace contract

`agent_event_outbox` persists typed event envelopes and consumer status. `agent_runs` stores one record for each event/agent pair, with UTC start/end processing timestamps, algorithm status, attempt, input hash/snapshot reference, compact output summary, numerical evidence, proposed action, explanation and failure text. `decision_traces` stores one event-level result with correlation ID, scenario epoch/version/infrastructure revision, final status, plan ID, narrative summary and compact evidence. Large flood grids are not duplicated in traces.

Read endpoints:

- `GET /api/v1/scenarios/{id}/agent-events`
- `GET /api/v1/scenarios/{id}/agent-runs`
- `GET /api/v1/agent-traces/{event_id}`
- `GET /api/v1/scenarios/{id}/agent-status`

Trace evidence includes event insertion time, local inference time, per-agent durations, routing duration, assignment solve duration, plan persistence time, end-to-end processing time, model status, newly exposed buildings, physical road/bridge changes, route deltas, unreachable destinations, priority deltas, assignments and baseline/optimized metrics. These are measured from the running implementation. UTC timestamps are operational processing times; simulation tick/seconds are in the scenario event and are not wall time.

Statuses include waiting/running/completed/degraded/skipped/failed/superseded for runs and pending/processing/completed/degraded/failed/superseded for events/traces. Degraded is an explicit rule-based fallback; skipped denotes dependency failure; superseded means the captured snapshot is no longer current. Retries update the same event/agent run and bounded attempt fields. Traces remain immutable in meaning but may be reprocessed only under their saved event and deduplication contract.

OpenAPI plus per-model JSON Schemas and generated TypeScript declarations are versioned in `frontend/src/api/`; the UI validates responses before rendering them.
