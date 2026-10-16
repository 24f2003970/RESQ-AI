# RESQ-AI technical pitch

## 90-second introduction

RESQ-AI is an offline-capable, synthetic disaster decision-support prototype. It connects a deterministic flood simulation to a locally trained exposure classifier, six event-driven algorithmic agents, constrained rescue routing and assignment, explicit commander review, and persistent simulated missions. The 3D city is a view of backend-owned scenario state; it does not calculate the flood or invent vehicle progress.

In the demo, heavy rainfall advances the flood model. We show the physical exposure it computes separately from the local model's prediction of future exposure. The agent pipeline records what changed and why. Routing and resource allocation then produce a versioned proposal with a conventional baseline for comparison. A commander reviews that proposal; the software never approves it automatically. If a relevant road closes, a new route is evaluated against the changed infrastructure. Mission movement only advances on the separate simulated mission clock, and arrival remains separate from explicit completion and resource restoration.

The city, population, training labels and mission outcomes are synthetic. Model evaluation is a held-out synthetic-scenario test, not validation against real floods. Rescue scores are transparent planning heuristics, not clinically validated triage. The prototype is intended to demonstrate an auditable engineering loop, not to direct real emergency response.

## Engineering explanation

The local FastAPI modular monolith owns versioned scenario state, deterministic flood stepping, model inference and rescue contracts. SQLite persists scenarios, events, agent outbox/runs/traces, plans, approvals, missions and resource state. The six algorithmic agents run from durable events. They emit a recommendation; only a separate commander decision can approve it. The assignment solver is maximum-weight with resource and route constraints and reports a deterministic status; the UI presents its stored comparison with the baseline.

The frontend uses React and TypeScript with a lazily loaded React Three Fiber scene. City objects retain backend IDs. Flood, prediction, roads, routes and units are separate layers. Vehicle display follows approved backend route geometry and authoritative traversed distance. It does not create progress. REST polling reads committed state; no hosted model, cloud API or external map service is needed at runtime.

The local model is trained on generated flood scenarios with group separation by scenario ID. Its labels come from the same synthetic simulator, so held-out evaluation measures consistency on generated cases, not generalization to observed disasters. See Model Intelligence Lab for artifact version, dataset provenance, test metrics, rule baseline, confusion matrix and feature information available in the current build.

## Differentiators to demonstrate

- A connected simulation → inference → agent trace → route/assignment → human review loop.
- A persisted event trace and explicit stale-state checks rather than an untraceable chat answer.
- A computed assignment and documented baseline on the same scenario constraints.
- Infrastructure changes can block travel and require a fresh reviewed route.
- Mission dispatch, progression, arrival, completion and resource restoration are distinct persisted states.
- Local operation and a disposable acceptance workflow support a reproducible offline demo.

These are prototype capabilities; they do not establish superiority over operational response platforms.
