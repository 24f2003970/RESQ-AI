# Part 13 — Decision Robustness Lab

## Scope and safety boundary

Part 13 adds persisted, deterministic counterfactual studies around the existing RESQ-AI rescue planner. Studies are analytical only. Their inputs and results live in `experiments.sqlite3`; the operational scenario database is read to freeze a baseline and to verify its identity, but studies do not write scenario events, rescue proposals, missions, unit reservations, closures, or agent-outbox events. Results cannot approve or dispatch anything.

## Study lifecycle

1. The UI obtains the current state version, epoch, infrastructure revision, unit reservations and positions, current local-model reliability, and eligible rescue proposals.
2. Creation checks the client identity against the live state. A short SQLite `BEGIN IMMEDIATE` recheck protects snapshot persistence from racing a scenario/closure/reservation update.
3. The canonical snapshot and original plan are serialized, hashed, and stored in an isolated analytical database. Repeated identical requests use the same input hash and return the same study record.
4. One bounded local worker evaluates up to 12 conditions at up to 12 simulator ticks. A process restart marks unfinished work `interrupted`; partial results are not presented as complete.
5. Reads compare the study epoch, state version, and infrastructure revision with live state. A mismatch marks the study historical. Historical evidence cannot be selected as a current rescue proposal.

## Algorithms

Environmental variants call the existing deterministic flood `step` repeatedly, preserve its volume accounting, and recompute building/road/bridge impacts from the resulting depth grid. Road closures use `build_road_graph`; bridge closures set the matching bridge impact to closed so the existing graph closes the bridge span. Resource variants remove only units in the frozen standby inventory or explicitly identified units. The local Part 12 prediction service supplies model evidence; if unavailable, the established physical-only fallback is used. Explicit analytical injection can suppress predictions or simulate model unavailability, and is labeled as such.

Each condition has two distinct calculations. Original-plan feasibility retains the saved assignments and checks saved route edges, resource availability, destination accessibility, and route reachability under the variant. It never silently moves an original assignment. Reoptimization then runs `generate_plan`, including current priority calculation, accessible routes, capacity constraints, and SciPy `linear_sum_assignment`. The solver result is marked `optimal_linear_sum_assignment` only when that existing solver returns successfully.

Critical road/bridge dependencies are ranked by closing each infrastructure asset traversed by the original plan and rerunning the same planner. Contingency suggestions are extracted from actual changed assignments, include their computed route geometry and trade-offs, and are explicitly marked commander-review-only.

## Data and metric interpretation

See [DECISION_ROBUSTNESS_CONTRACT.md](DECISION_ROBUSTNESS_CONTRACT.md), [COUNTERFACTUAL_EVALUATION.md](COUNTERFACTUAL_EVALUATION.md), [ROBUSTNESS_METRICS.md](ROBUSTNESS_METRICS.md), and [CONTINGENCY_PLANNING.md](CONTINGENCY_PLANNING.md).

The baseline is the saved live proposal (or a non-persisted proposal generated from that frozen snapshot). Counterfactual metrics are measured at the selected evaluation horizon. Environmental changes can change the physically exposed and forecast-eligible destination set; the report therefore shows each condition’s priority denominator and does not present a likelihood-weighted score.

## Product integration

The Robustness Lab reuses the existing `CityScene` with one canvas. Hypothetical routes and closures use dashed overlays and a persistent “Hypothetical” label; no mission entity or animation is created. The results matrix, fragility view, dependency inspector, and contingency list render only saved computation results. Command Center and Judge Mode link to the lab; Judge Mode adds no approval or dispatch controls.

## Reproduction

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe benchmark_robustness.py
```

For the benchmark contract and measured results, see [PART_13_VERIFICATION.md](PART_13_VERIFICATION.md). Assumptions and current limitations are listed in [COUNTERFACTUAL_EVALUATION.md](COUNTERFACTUAL_EVALUATION.md).
