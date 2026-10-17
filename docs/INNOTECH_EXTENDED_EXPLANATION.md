# RESQ-AI · seven-minute extended explanation

## 0:00–0:40 · Problem

Flood response involves changing physical exposure, uncertain near-future conditions, constrained access and scarce units. RESQ-AI makes these linked decisions inspectable in a fictional city. It is a synthetic research prototype, not a certified or field-tested emergency system.

## 0:40–1:35 · Digital Twin and simulator

The Python backend generates a seed-based fictional city: buildings, ten road corridors, bridges, response units, terrain and a canal. A deterministic grid process advances in fixed five-minute steps. Rainfall, river stage, local storage, terrain, drainage and neighbor flow influence modeled depth. The frontend renders the returned grid, buildings and infrastructure in Three.js. It does not calculate authoritative water or damage. The simulator is deliberately simpler than a hydraulic solver.

## 1:35–2:35 · Local model and reliability

The random forest estimates one explicit target: a building crossing the simulator's future-exposure threshold six ticks later. The dataset contains 72 scenario groups and 25,920 building observations. We split by full scenario IDs into 42 train, 15 validation and 15 untouched test groups. Calibration adoption used nested grouped development folds. The Platt calibrator passed the fixed development gate. The test results remain synthetic and were never used to select the gate. Feature-support checks disclose observations outside the training ranges and do not claim in-support accuracy.

## 2:35–3:35 · Six event-driven agents

Committed scenario and infrastructure events enter a SQLite outbox. The coordinator runs Hazard Intelligence, Impact Assessment, Rescue Priority, Routing, Resource Allocation and Commander / Strategy in order. Each stage records status and evidence. Stale state is rejected. A failure is visible and downstream work can be retried. The final agent writes a proposal only; it cannot approve a plan or dispatch a unit. These agents are local deterministic algorithms, with no hosted inference or LLM credentials.

## 3:35–4:45 · Routes and assignment

The router builds a graph from crossing-aware road geometry and explicit bridge spans. Manual closures, modeled road impacts, bridge status, flood depths and unit-specific depth limits filter edges. Building and unit access spurs have a finite documented length and must connect to open road geometry. An isolated node or spur-only path is not a vehicle route. The assignment solver maximizes the documented priority/capacity utility minus a route-time penalty, with one destination per unit and one unit per destination. A fairer, transparent comparison reuses the same priority and feasible route inputs in a nearest-feasible greedy baseline.

Across ten deterministic scenario groups, the optimization objective improved in eight and tied in two. Two cases returned zero assignments. All roads closed returned zero. This demonstrates behavior under this tested synthetic set; ten designed cases are not a statistical estimate of rescue success.

## 4:45–5:55 · Human control and missions

An approved plan reserves units and creates ready missions. A commander still must dispatch. The separate simulated mission clock persists traveled distance along the approved route. A road closure ahead blocks progress at the last traversed distance. The router proposes a current route revision; the commander approves it after checking the changed infrastructure revision. Arrival and explicit completion are separate states. Completed or dispatched-cancelled resources remain unavailable until explicitly returned to service. The system does not invent an evacuation, mission outcome or return trip.

## 5:55–6:35 · Robustness

Scenario Lab compares analytical variants from a shared snapshot. Decision Robustness freezes scenario epoch, state version, infrastructure revision, closures and resource state, then applies explicit hypothetical conditions in isolated storage. Original plan feasibility and new optimization are reported separately. Neither analysis commands the live operational system. The extreme-flood benchmark invalidated both starting routes; the all-closed graph returned zero reassignments.

## 6:35–7:00 · What is next

The engineering contributions are the reproducible pipeline, group-aware model evaluation, strict route feasibility, explicit commander boundary, persisted mission lifecycle and disposable acceptance. Future real-world work would require external domain partners, surveyed data, calibrated models, prospective evidence, safety engineering and field validation. None of those are claimed in this prototype.
