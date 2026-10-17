# Demo A — positive synthetic rescue

## Deterministic setup

- Seed: `2026`
- Preset: `mild`, then parameters set to rainfall `30 mm/h`, river stage `0.6 m`, drainage effectiveness `0.2`
- Flood steps: `6`
- Fresh scenario tick/state: `6 / 8`; epoch `0`
- Solver: `optimal_linear_sum_assignment`

The production simulator produced **10 physically impacted buildings** with a maximum cell depth of **0.1613 m**. The local model returned 72 predictions. The current verified run proposed four missions. Two candidate assignments traversed three corridor IDs, showing two road transitions: `road-ew-1 → road-ns-0 → road-ew-2` at 490.0 m and 606.0 m.

## Disruption and response

The acceptance run approved the plan and explicitly dispatched `unit-2` to `building-1-2-1`. After 17 seconds of persisted mission time, authoritative progress was **91.7 m** at `(-217.6667, -100, elevation 1.3883 m)`. Closing `road-ns-0` blocked the mission at that same progress and advanced infrastructure revision to `1`.

The real router proposed `road-ew-1 → road-ns-5 → road-ew-2`, avoiding the closed segment and starting from the saved current position. This route was **1053.6 m** under the synthetic graph. The explicit version-checked commander action approved route revision 2. The mission then arrived at 1053.6 m, was explicitly marked completed, remained unavailable until return-to-service, and became available at its persisted location after explicit restore. The durable read-only replay contained 17 mission events.

## Reproduction

Run `backend/.venv/Scripts/python.exe backend/demo_acceptance_rc1.py`. The command creates and deletes a temporary operational SQLite database and emits JSON/Markdown evidence in the ignored `backend/artifacts/part14-rc1-acceptance/` folder. Scenario and mission IDs vary by run; seed, forcing, tick, assignments and route behavior are deterministic. Do not imply occupants were rescued or that the route is field-safe.
