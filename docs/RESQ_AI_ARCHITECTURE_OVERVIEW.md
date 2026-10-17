# RESQ-AI architecture overview

Editable Mermaid sources below reflect the implementation through Part 15. Part 15 adds evaluation and evidence tooling without changing the application's operational architecture. Diagrams describe local software boundaries and the deterministic synthetic prototype.

## System architecture

```mermaid
flowchart LR
  UI[React + TypeScript frontend] --> API[FastAPI local REST service]
  TWIN[React Three Fiber / Three.js Digital Twin] --> UI
  UI -->|versioned commands, safe polling| API
  API --> SC[Scenario and city services]
  SC --> FE[Deterministic flood engine]
  API --> ML[Local random forest + support and calibration layer]
  API --> ORCH[SQLite outbox / ordered event coordinator]
  ORCH --> A1[Hazard Intelligence]
  A1 --> A2[Impact Assessment]
  A2 --> A3[Rescue Priority]
  A3 --> A4[Routing]
  A4 --> A5[Resource Allocation]
  A5 --> A6[Commander / Strategy]
  A4 --> NX[NetworkX flood-aware road graph]
  A5 --> SP[SciPy linear-sum assignment]
  A6 -->|proposal only| REVIEW[Human commander review]
  REVIEW -->|explicit approval| MS[Mission state machine + simulated clock]
  SC --> OP[(SQLite operational scenarios, events, missions)]
  ORCH --> OP
  MS --> OP
  API --> EXP[Isolated scenario / robustness experiment services]
  EXP --> EXDB[(Separate experiment SQLite store)]
  ML --> ART[(Local model, calibration and support artifacts)]
```

The agents are deterministic algorithmic services. They are not language-model agents. The frontend displays backend truth and can emit commands; it does not calculate authoritative flood depth, model predictions, rescue routes or assignments.

## End-to-end flow

```mermaid
sequenceDiagram
  actor Commander
  participant UI as React / Digital Twin
  participant API as FastAPI
  participant Flood as Deterministic flood engine
  participant ML as Local ML and reliability
  participant Agents as Six ordered algorithmic agents
  participant Router as NetworkX routing + SciPy assignment
  participant DB as Operational SQLite
  participant Mission as Mission store / clock
  Commander->>UI: Choose seed and scenario inputs
  UI->>API: Versioned scenario command
  API->>Flood: Advance fixed simulation tick
  Flood->>DB: Persist physical state and events
  API->>ML: Estimate synthetic future exposure
  ML-->>Agents: Prediction status, support labels, warnings
  DB-->>Agents: Durable trigger event
  Agents->>Router: Current impacts, priorities, closures, resources
  Router-->>Agents: Supported routes, assignments, unreachable reasons
  Agents->>DB: Save trace and commander-review proposal
  UI->>API: Read committed proposal and trace
  Commander->>UI: Explicitly approve or reject
  UI->>API: Version-checked review action
  API->>Mission: Create reserved simulated mission after approval
  Commander->>UI: Explicitly dispatch, advance clock, review route changes
  Mission->>DB: Persist mission position and events
  UI->>API: Read current mission and read-only replay
  Mission-->>Commander: Arrival requires explicit completion and return-to-service
```

## Mission state machine

```mermaid
stateDiagram-v2
  [*] --> ready: approved plan creates reserved mission
  ready --> en_route: explicit dispatch
  ready --> cancelled: explicit cancellation / reservation released
  en_route --> blocked: closure intersects an untraversed route edge
  en_route --> arrived: authoritative mission clock reaches destination
  en_route --> cancelled: explicit cancellation / unit unavailable
  blocked --> en_route: route revision proposed and explicitly approved
  blocked --> cancelled: explicit cancellation / unit unavailable
  arrived --> completed: explicit simulated completion
  arrived --> cancelled: explicit cancellation / unit unavailable
  completed --> [*]
  cancelled --> [*]
  note right of completed: Resource remains unavailable until explicit return-to-service.
  note right of cancelled: A ready-mission cancellation releases its reservation; dispatched cancellation requires explicit return-to-service.
  note right of en_route: Pause / resume changes the scenario mission clock; it is not a mission status.
```

Arrival and completion do not verify evacuation or lives saved. No return journey is fabricated. Reset begins a new scenario epoch and retains history from the old epoch.

## Reliability and decision boundaries

```mermaid
flowchart TD
  PHYS[Authoritative simulated physical state] --> CUR[Current exposure and infrastructure impacts]
  FEAT[Current features] --> MODEL[Local random forest] --> FUT[Estimated future synthetic exposure]
  SUP[Feature support + saved calibration evidence] --> FUT
  CUR --> AGENT[Agent analysis and recommendation]
  FUT --> AGENT
  HYP[Hypothetical robustness study] -->|frozen copy; isolated DB| ANALYSIS[Counterfactual metrics only]
  AGENT --> PROP[Persisted proposed plan]
  PROP --> HUMAN[Human approval / rejection]
  HUMAN -->|approval only| OP[Persisted operational mission record]
  HUMAN -->|rejection| TRACE[Audit history]
  OP --> CLOCK[Explicit simulated dispatch and mission clock]
  CLOCK --> TRACE
  FUT -. never treated as physical water .-> PHYS
  ANALYSIS -. never approves or dispatches .-> OP
```

Physical exposure comes from the flood engine. Future exposure is an estimate from a model trained on synthetic simulator outputs and can carry unavailable, unsupported or edge-of-support warnings. A plan is a proposal until a commander approves it. Robustness results are hypothetical; they do not change live plans, closures, reservations or missions.

## Counterfactual isolation

```mermaid
flowchart LR
  LIVE[Live scenario snapshot + infra revision + closures + resources] -->|freeze exact identity| SNAP[Canonical analytical snapshot]
  SNAP --> VAR1[Counterfactual A]
  SNAP --> VAR2[Counterfactual B]
  VAR1 --> ENGINE[Existing flood, router and assignment functions]
  VAR2 --> ENGINE
  ENGINE --> STUDY[(Separate analytical SQLite database)]
  LIVE --> LIVEOPS[(Operational scenarios / outbox / plans / missions)]
  STUDY -. no write path .-> LIVEOPS
  HUMAN[Commander] -->|separate command, outside study| LIVEOPS
```

See [Part 10 implementation](PART_10_IMPLEMENTATION.md), [agent architecture](AGENT_ARCHITECTURE.md), [routing model](ROUTING_MODEL.md), [mission lifecycle](MISSION_LIFECYCLE.md), and [counterfactual evaluation](COUNTERFACTUAL_EVALUATION.md) for source-level contracts.
