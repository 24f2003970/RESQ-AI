# RESQ-AI · judge Q&A

## Model and evidence

**Why a random forest?**
It fits the small, tabular synthetic feature set, handles nonlinear thresholds, runs locally, and is easier to inspect and package than a large hosted model. Validation selected it against logistic regression and two decision-tree baselines; it was not chosen from final test results. See `backend/ml_artifacts/evaluation.json`.

**How was it trained, and what is the target?**
The generator produces 72 deterministic scenario groups and 25,920 building observations. The target is whether the building crosses the simulator's exposure threshold six five-minute ticks later. The split is 42 training, 15 validation and 15 untouched test groups. Labels are synthetic.

**Why synthetic data?**
The hackathon prototype can be reproduced without incident records or external services. Synthetic data allows a safe deterministic demo but cannot validate real-world predictive skill.

**How did you prevent scenario leakage?**
Train, validation, test, nested calibration folds and OOF predictions split by scenario ID. Repeated observations from one disaster history do not appear on both sides of the model evaluation. The Part 12 reliability report retains the outer-fold fit group audit.

**How was calibration evaluated?**
Platt scaling passed a predetermined adoption gate on fully nested GroupKFold development predictions: Brier improved by 0.002397 and log loss by 0.010955. The final 15 groups were excluded from fit and adoption. Their results are descriptive synthetic holdout measurements, not real-disaster validation.

**What happens outside training support?**
The inference service labels marginal feature range support, edge support and missing/invalid artifacts. Future model labels outside supported evidence are excluded from forecast-driven rescue eligibility. Support checks do not detect every implausible feature combination and do not guarantee accuracy.

**Does calibration mean the probabilities are reliable in a real flood?**
No. The model, labels and evaluation all use the same synthetic simulator family. Calibration is measured only against its synthetic future-exposure labels.

## Agents, routing and assignment

**Are the agents language models?**
No. They are six deterministic, event-triggered algorithms with persisted traces: Hazard Intelligence, Impact Assessment, Rescue Priority, Routing, Resource Allocation, and Commander / Strategy.

**Why NetworkX?**
The generated road network is a small weighted graph. NetworkX supplies explicit graph paths, while project code filters closed, flooded, bridge and unit-depth-incompatible edges and verifies access connections.

**Why SciPy?**
`linear_sum_assignment` solves the finite maximum-weight assignment problem with each unit and destination used at most once. Dummy columns permit unused units. Stable ordering and a deterministic tie perturbation make results repeatable.

**Does the optimizer guarantee a globally optimal rescue outcome?**
It optimizes the declared synthetic objective over the generated feasible route map. It does not optimize a real response, route uncertainty, team coordination, casualty outcomes or field safety.

**What if every road is blocked?**
The router removes unusable graph edges and does not treat endpoint spurs as roads. The verified all-roads-closed case returns zero assignments and reports unreachable destinations.

**Can commanders override a recommendation?**
They can review, reject, edit assignments subject to route/resource validity, close roads and approve a current proposal or route revision. Approval and dispatch are separate explicit actions.

## Missions and analytical studies

**Are missions dispatched automatically?**
No. Plan approval creates a reserved ready mission. Dispatch requires a separate commander action.

**How is simulated progress persisted? What happens on restart?**
The mission store persists route progress, versions, events and per-scenario mission clock in SQLite. The frontend displays backend-authoritative progress. Read-only replay is available after restart.

**What happens after arrival?**
Arrival is a persisted state. A commander must explicitly complete it. The resource remains unavailable until explicit return-to-service; no return trip is invented.

**How do Scenario Lab and Robustness Lab differ?**
Scenario Lab runs isolated A/B variants from a shared starting snapshot and compares the same existing simulation/planner methods. Robustness Lab freezes live identity and closures, then tests explicit hypothetical disruptions. Neither study auto-approves or dispatches a mission.

**What if there is no feasible alternative?**
The system reports no supported route and may leave destinations unassigned. Inaccessible cases are preserved as failure evidence.

## Product claims and limits

**What distinguishes this from a map dashboard?**
It connects deterministic flood state, locally evaluated predictions, durable agent traces, connected route feasibility, constrained resource allocation, human approval and a persisted simulated mission lifecycle. The whole chain is inspectable and reproducible.

**Can emergency services use it today?**
No. It is a fictional engineering and research prototype. It has no real incident feeds, surveyed roads, operational communications, validated hydraulic model, field-tested logistics or regulatory safety case.

**What are the biggest limitations?**
Synthetic geography and labels, simplified flood physics, stylized road speeds and occupants, unsupported boat routing, small scenario-group evaluation, marginal support checks, laptop-scale performance, and limited browser viewport/context-loss verification.

**What would be needed for real-world validation?**
Partnered requirements and safety analysis; licensed, surveyed geospatial and infrastructure data; calibrated hydrology and road-condition models; representative real incident outcomes; prospective group/time/geographic validation; human-factors evaluation; fail-safe operational procedures; security/privacy review; and field exercises with emergency professionals.

Relevant sources: `SCIENTIFIC_EVALUATION.md`, `RESQ_AI_ARCHITECTURE_OVERVIEW.md`, `PART_14_VERIFICATION.md`, and the linked Part 4–13 technical documentation.
