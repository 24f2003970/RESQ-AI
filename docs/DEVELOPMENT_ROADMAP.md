# Development Roadmap

## Feature priority

- **Mandatory MVP:** deterministic city and flood slice, backend-owned state, risk rule plus locally trained model, priorities, route planning, resource assignment, road-closure replanning, human plan review, event replay, 3D command view, baseline comparison, offline startup.
- **Important enhancement:** scenario presets, expanded object inspector, model evaluation lab, what-if comparison, keyboard and 2D fallback, polished replay controls.
- **Stretch:** real flood raster experiment, imported elevation, earthquake, OR-Tools comparison, extra city scale or advanced rendering.

## Dependency order

1. Agree API schemas, city coordinate conventions, deterministic seed contract, and minimal scenario event types.
2. Build one vertical slice: create city → advance one flood step → return changed state → render it → close road → produce revised route.
3. Add risk model and agent chain around the stable state contract.
4. Add approval/replay, evaluation view, and scenario comparison.
5. Integrate offline packaging, tune performance, rehearse demo, freeze behavior.

Frontend and backend can start in parallel after a written API fixture exists. The ML label definition depends on the simulator fields and scenario grouping. Agent decisions depend on stable API schemas; avoid building six independent agents before the end-to-end event chain works.

## Two-week compressed plan

| Days | Shared milestone | Developer A: backend / ML | Developer B: frontend / 3D |
|---|---|---|---|
| 1–2 | Repo, API fixture, seed/city contract | generator, Pydantic schemas, health/city endpoints | shell, design tokens, static scene from fixture |
| 3–4 | Vertical slice checkpoint | flood grid step, road state, deterministic fixtures | API adapter, state rendering, depth/risk layer toggles |
| 5–6 | Replanning checkpoint | route graph, priority score, simple feasible assignment | selected object/road control, route/unit rendering |
| 7–8 | Model and agent chain | synthetic dataset, baseline, grouped split, local classifier, decision records | command center proposal/reason cards, event feed |
| 9–10 | Demo freeze candidate | approval/reject, SQLite replay, offline run docs | scenario controls, review flow, 2D fallback |
| 11–12 | Integration and defect fixes | integration fixes, locked evaluation report | accessibility/performance/layout fixes |
| 13–14 | Rehearsal and packaging | clean offline setup, seed scenarios, evidence | demo script, screenshots, rehearsal and contingency |

Defer real data, earthquakes, and complex animation in this schedule. Reserve at least three days for integration and demo stability.

## Four-week recommended plan

| Week | Shared deliverable | Developer A | Developer B |
|---|---|---|---|
| 1 — foundation and slice | Repeatable city visible with one advancing flood step | domain model, deterministic generator, API and event contract | app shell, 3D city scaffold, fixture-backed rendering and controls |
| 2 — response loop | Flood → risk → priority → route → assignment, with road closure replanning | flood assumptions, rule baseline, routing/allocation and event persistence | command center, layer controls, scenario lab, route and unit visuals |
| 3 — ML and review | Reproducible local training and human-approved plan replay | synthetic generation, grouped evaluation, artifact/versioning, agent explanations | decision explorer, model lab, approval/reject UI, replay timeline |
| 4 — hardening and presentation | Offline demo candidate, comparison evidence, polished presentation | integration, deterministic checks, packaging, performance/error handling | accessibility, visual polish, 2D fallback, demo rehearsal and narrative |

Real-data experiments happen only if the MVP works by the end of week 2. Freeze features by mid-week 4 and reserve the remainder for integration, profiling, offline verification, and rehearsal.

## Integration checkpoints

- **Checkpoint A (end day 2 / week 1):** API schema fixture and city object IDs render unchanged.
- **Checkpoint B (day 4 / week 1):** a simulation step visibly changes backend and frontend state for a fixed seed.
- **Checkpoint C (end week 2):** road closure invalidates a prior route and creates a new proposal; no stale assignment is shown as active.
- **Checkpoint D (end week 3):** locked model evaluation, approval flow, and event replay operate end to end.
- **Freeze (at least 3 days before event):** no feature additions without joint agreement; fix defects and rehearse on the actual demo laptop.

## Main risks and mitigations

| Risk | Mitigation |
|---|---|
| Scope exceeds 2–4 weeks | protect the vertical slice; stretch work is gated on the complete MVP |
| Fake or overstated ML value | synthetic label disclosure, grouped held-out seeds, rule baseline, narrow claims |
| Frontend/backend drift | versioned API contract and fixture from day 1 |
| 3D performance or WebGL failure | modest geometry/grid, profile early, keep a 2D summary fallback |
| Plans appear operationally authoritative | visible simulation labels, approval gate, limitations and no real dispatch |
| Internet/dependency failure at event | local dependency cache, offline start rehearsal, local model artifact and seed scenarios |
| Collaborator work collides | short-lived feature branches, pull requests, integration owner and daily sync |
