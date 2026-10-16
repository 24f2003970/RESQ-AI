# Part 8 Verification

Verification commands and actual results are recorded here after the final run. Backend: `python -m pytest -q`. Frontend: `npm test`, `npm run lint`, `npm run typecheck`, and `npm run build`. Contract: `python export_contract.py` and `npm run generate-api`. Benchmark: `python benchmark_missions.py`.

The reproducible benchmark creates a temporary SQLite scenario, approves and dispatches one synthetic unit over a 2 km route, then records 100 persisted one-second advances. It also measures repeated 3D route-position interpolation and clock reads. On the local Windows bundled Python run on 2026-10-16: 100 advances at 1, 30-second step bound (one unit) averaged **2.691 ms**, p95 **4.526 ms**, max **5.702 ms**; 10,000 position interpolations averaged **0.001969 ms** each; 100 persisted clock reads averaged **0.749 ms** each. These are single-run laptop measurements, not a capacity guarantee; frontend interpolation and GPU load were not instrumented.

Coverage includes approval/backfill and idempotency, unit reservation, dispatch gate, deterministic segment progression, pause and arrival/completion separation, closure on passed versus remaining segments, reviewed route revision, cancellation/restore and epoch isolation, concurrent dispatch, typed API behavior, durable agent events, and frontend dispatch, blockage, completion, and offline error states.
