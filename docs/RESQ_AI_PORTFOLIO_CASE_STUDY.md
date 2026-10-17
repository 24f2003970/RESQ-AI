# RESQ-AI: engineering a reproducible disaster-response decision prototype

## 1. Problem

During a flood, response teams need to combine evolving hazard conditions, exposed people and infrastructure, constrained routes, and limited resources. RESQ-AI is a synthetic prototype for exploring that decision workflow. It presents a deterministic flood Digital Twin, future-exposure estimates, route/resource proposals, and a human-controlled simulated mission lifecycle.

## 2. Requirements and constraints

The project needed a local-first hackathon demo that remained understandable and reproducible without paid inference APIs. It had to show changing simulation state in 3D, explain model uncertainty, reject unsupported routes, preserve resource reservations, and require a human commander to approve operationally meaningful simulated actions. Time and data limitations meant the city, outcomes, and model labels were synthetic.

## 3. Architecture decisions

React and TypeScript provide the interface; React Three Fiber and Three.js render the city. A local FastAPI service owns scenario and mission state. SQLite persists events, checkpoints, agent traces, proposals, missions, and analytical studies. Flood simulation, model inference, routing, and assignment are local computations. This keeps the demo reproducible and avoids external inference dependencies.

## 4. Flood simulation

The simulator advances a deterministic grid-based water state from scenario rainfall, river stage, and drainage inputs. Scenario epochs, versions, checkpoints, and events support replay and stale-state checks. Reported depths and impacts are simulator outputs for a synthetic city; they are not hydrological observations or validated inundation forecasts. Method and assumptions are in `FLOOD_SIMULATION_METHOD.md`.

## 5. Synthetic ML and validation

The random forest estimates a synthetic future-exposure target over a six-step horizon of five-minute simulation ticks. Data are organized into 72 independent scenario groups: 42 training, 15 validation, 15 untouched test. Grouped splits prevent overlapping observations from the same trajectory appearing on both sides of an evaluation boundary.

The Part 12 calibration gate uses nested grouped validation on development scenarios. The production Platt calibrator is fitted from grouped out-of-fold development scores; the original random-forest artifact remains unchanged. The adopted method's untouched synthetic test Brier score is 0.027917 versus raw 0.030526; log loss is 0.094190 versus raw 0.106666. Those measurements are not evidence of calibration on real floods. Warnings expose weak feature support and predictions outside the modeled support. See `ML_CALIBRATION.md`, `ML_RELIABILITY_MODEL_CARD.md`, and `SCIENTIFIC_EVALUATION.md`.

## 6. Event-driven agents

Six deterministic algorithmic agents evaluate hazard, exposure, priorities, routes, resources, and a command recommendation. Their persisted traces make each completed stage inspectable. They are local rules and computations, not autonomous language models. Proposal changes remain subordinate to stale-state validation and commander approval.

## 7. Routing and assignment

The road graph is modeled in NetworkX with flood-depth, closure, bridge, and unit constraints. Building access spurs are usable only when connected to traversable road geometry; isolated nodes and spur-only paths are rejected. SciPy solves the constrained assignment objective, with a conventional baseline recorded against compatible state, destinations, inventory, and graph constraints. In ten Part 15 evaluation groups, the priority-weighted objective improved in eight, tied within tolerance in two, and was lower in none. This small synthetic sample supports a bounded implementation comparison, not a claim of field efficiency.

## 8. Human-controlled mission lifecycle

Plan proposals do not dispatch anyone. A commander explicitly approves a plan; simulated missions are then created with units reserved. Dispatch and a separate mission clock produce backend-authoritative route progress. Closures can block progress, and route changes require review and approval. Arrival and completion are distinct explicit actions. A unit returns to service only through the explicit restoration control; the simulator does not fabricate a return trip.

## 9. Reliability and decision boundaries

The interface distinguishes physical simulation state from future ML estimates, and operational proposals from hypothetical robustness studies. Reliability/support notices communicate where the synthetic model has limited representation. A counterfactual study freezes its starting state and does not commit mission actions or mutate operational closure records.

## 10. Counterfactual analysis

The Decision Robustness Lab compares original-plan feasibility and reoptimized alternatives under frozen hypothetical conditions. It includes flood escalation, infrastructure closures, limited resources, and network inaccessibility. The corrected all-roads-closed case produces zero ground assignments. This is a valid failure result: a solver must not create a route by relaxing physical connectivity.

## 11. Engineering corrections and lessons

- Nested scenario-grouped calibration validation was needed because a calibrator trained on scores derived from outer-held-out groups would leak evaluation information.
- Road closures exposed the danger of unconditional access spurs; routing now requires connected, traversable geometry.
- A 3D vehicle marker must follow the approved route polyline using authoritative traveled distance, including corners and bridge elevations; straight interpolation can visually cross obstacles.
- Frontend mission clock state requires scenario epoch/version guards so stale responses cannot overwrite a reset scenario.
- Acceptance workflows use disposable databases so demos and regression checks do not alter an operator's persistent scenario store.
- Browser captures and test artifacts are labeled with what they actually measured; a screenshot of early movement is not presented as arrival.

## 12. Measured results

The final recorded Part 15 runner run evaluated ten fixed scenario groups in 3,768.693 ms. Route computation took 0.844–185.656 ms per group and assignment took 0.007–0.289 ms; an earlier exploratory run took 1,382.568 ms, showing that local timing varied. Eight group objectives improved, two tied within 0.01, and no group had a lower optimized objective. Two cases yielded zero assignments; the all-roads-closed case assigned zero and marked nine destinations unreachable. Per-case data and configuration are in `evidence/part15/scientific_evaluation.csv`.

The 15-group synthetic held-out ML results are reported separately from development model selection. Part 13/14 benchmark values are historical machine-specific records and are not merged with this ten-case runtime. The README and `PART_15_VERIFICATION.md` link the source evidence.

## 13. Limitations

The city, hydrology, labels, travel times, resource inventory, and outcomes are synthetic. Ten evaluation groups are insufficient for broad statistical conclusions. The graph is not surveyed or operationally validated. No live sensors, emergency-service integrations, boats, or earthquake response are implemented. Browser evidence covers selected local states; target desktop viewport sizes, reduced-motion behavior, and WebGL context-loss recovery remain unverified.

## 14. Further work and deployment requirements

Before any field use, this concept would need authoritative geospatial and hydrological data, validated hazard models, privacy and security review, resilient communications, accessibility work, human-factors studies, emergency-service co-design, independent safety assessment, extensive scenario validation, and clear governance. Part 16 should focus on release readiness and a final quality gate, not silently imply operational certification.
