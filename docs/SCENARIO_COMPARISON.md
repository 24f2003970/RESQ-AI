# Scenario Comparison Contract

## Reproducible starting point

An experiment records its ID, name, base scenario ID, seed, starting tick, state version, epoch, SHA-256 snapshot reference, equal duration, A/B inputs, timestamps, status, engine versions and reproduction metadata. Creation rejects a changed expected state version and road IDs that are not part of the generated city. Each run is tied to one exact base snapshot; two variants cannot silently start from separate seeds or horizons.

## Supported interventions

Each variant can select a mild/heavy/extreme preset and/or explicit rainfall (0–300 mm/h), river stage (−2–5 m), drainage effectiveness (0–1), available ambulances (0–2), available ground teams (0–2), and up to ten unique manually closed roads. Both variants advance the same number of fixed 300-second ticks (0–120). Resource-only comparisons use the same physical state. Road closures affect the routing graph only.

## Isolation and operations

Experiments persist in a dedicated SQLite database. Imported variant scenarios, closure records, event rows and analytical plans stay in that database. The live scenario, operational event outbox, decision traces, plans and resource reservations are not modified. Experiments cannot approve plans. Local ML inference accepts the experiment snapshot directly rather than fetching the live scenario.

The service reports pending/running/completed/failed/cancel_requested/cancelled/interrupted and a progress percentage. Cancellation is checked between flood ticks. A restart marks unfinished jobs interrupted; users can inspect the stored inputs and rerun a new experiment.

## Result provenance

Every time-series point is captured from the existing backend flood simulation or derived from that saved state. Summaries retain flood depth, exposed buildings, roads and bridges; high-priority and reachable destinations; baseline and optimized assignments; routes; per-phase timings; model status; explanatory A/B deltas; and serialized payload size. JSON export includes the experiment metadata and results.

For a metric where Variant A is nonzero, the relative change is `(B − A) / abs(A) × 100`; when A is zero, relative change is null and only the absolute difference is shown. These values describe the selected synthetic experiment only. They are not generalized forecasts.
