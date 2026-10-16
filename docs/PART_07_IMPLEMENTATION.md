# Part 7 — Scenario Intelligence

Part 7 adds persistent A/B what-if experiments, measured baseline-versus-optimized rescue analytics, Scenario Lab experiment controls, a single-canvas saved-state Digital Twin view, and a guided ten-stage hackathon demonstration.

## Architecture

- `backend/app/experiments.py` stores experiment inputs, exact base snapshots, progress and results in a dedicated `experiments.sqlite3` database beside the operational database. Each variant imports the same serialized physical snapshot into a separate experiment scenario namespace and advances the existing `ScenarioStore` flood engine. Experimental outbox rows and rescue proposals remain in that database; the operational `AgentOrchestrator` only reads the operational database.
- Resource-only variants reuse the same starting depth grid and do not advance different physical states. Flood parameter variants run the existing five-minute simulation step for an equal bounded duration. Manual road closures modify the experimental `PlanStore` graph state without changing flood parameters or depth.
- Experiment plans are computed in memory from the existing route graph and Part 5 allocation functions. They are never saved as operational proposals and never reserve operational units.
- `ml_service.predict_state` performs local inference against an explicit immutable `ScenarioState`, avoiding a read of the live operational scenario during an experiment. If the local artifact is unavailable, the experiment labels ML as unavailable while retaining measured physical exposure and routes.
- Experiment creation validates the base scenario version and city road IDs. Cancellation is checked between simulation steps. On service restart, an unfinished durable experiment is labeled `interrupted` with its snapshot and metadata preserved.
- The frontend uses saved experiment points for charts and loads only one lazy `CityScene` canvas while switching A/B states, preserving the camera component between variants.

## Contract and metric notes

The request accepts exactly variants A and B, a base scenario ID and expected version, a common simulation duration (0–120 five-minute ticks), parameter interventions, up to two ambulances and two ground teams per variant, and up to ten unique road closures. Results record seed, base tick/version/epoch, canonical snapshot SHA-256, engine versions, actual timings and payload size.

The route comparison supplies the same reachable route candidates, vehicle compatibility, capacities, destination scores and inventory to both methods. See [BASELINE_COMPARISON_METHOD.md](BASELINE_COMPARISON_METHOD.md) for formulas and limitations.

The guided demo creates a separate operational scenario at seed 2026, applies 90 mm/h rainfall, river stage 1.4 m and 20% drainage for 12 ticks, uses locally installed model inference, waits for real persisted agent traces, closes a road from an assigned route, verifies closure-triggered replanning, and requires an explicit commander decision. The Part 7 milestone left approved reservations until reset; Part 8 added explicit simulated mission completion and commander return-to-service. Neither release nor completion is automatic.

## Reproduction

From `backend/`, run `.\.venv\Scripts\python.exe demo_acceptance.py`. From `frontend/`, run `npm test`, `npm run typecheck`, `npm run lint`, and `npm run build`. The hosted CI workflow runs backend and frontend jobs independently.

## Limits

The city, flood process, exposure labels, travel speeds, occupants and capacities are synthetic. The model score is uncalibrated and does not constitute a forecast. The flood model is a deterministic educational grid, not a hydraulic solver. Ground rescue routing and Part 8's simulated mission lifecycle are supported; boat routing is not modeled. An experiment interrupted by process restart must be rerun; it is not resumed mid-variant.
