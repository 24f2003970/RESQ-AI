# Product Requirements

## Purpose and users

RESQ-AI is a local, hackathon-scale decision-support prototype for demonstrating how a changing flood scenario can drive risk assessment and rescue replanning in a fictional city. Its primary users are a command-center operator and a judge evaluating the demo. It does not issue public warnings, connect to emergency services, or dispatch real responders.

## Product promise

Given a saved scenario and city seed, RESQ-AI produces a repeatable simulated city state, displays affected places, proposes explainable priorities and routes, and updates its proposal when conditions change. An operator reviews and approves every simulated action.

## Functional requirements

### Mandatory hackathon MVP

1. **Deterministic scenario:** load a named fictional city from a seed; reset returns the same initial state.
2. **Flood progression:** advance rainfall and river-stage inputs through a documented, bounded grid model. Display simulated depth and affected buildings, roads, and facilities.
3. **Risk assessment:** compute a rule baseline and a locally trained classifier output for supported features; show model version, label meaning, and uncertainty/limitations.
4. **Prioritization:** score affected zones using exposed population, severity, vulnerability, and access. Show component contributions and stable tie-breaking.
5. **Routing:** find routes over a road graph, applying costs for travel length and hazard exposure and excluding closed edges. Return a clear no-route result when disconnected.
6. **Resource assignment:** assign available units to prioritized missions using a deterministic minimum-cost or greedy method with explicit capacity constraints.
7. **Replanning:** a changed flood state or road/bridge closure emits an event and recalculates affected risk, routes, and assignments.
8. **Human review:** plans are proposals. The operator can approve or reject; only approval commits simulated unit movement/mission state.
9. **Explainability and replay:** persist timestamped scenario events and decisions and replay them in order.
10. **Baseline comparison:** run both proposed and conventional fixed-priority response on the same seed, scenario, and resources. Show computed outcomes, assumptions, and uncertainty.
11. **Offline operation:** after dependency installation and optional dataset preparation, application features work without hosted inference or network calls.
12. **Honest status:** all metrics are generated from backend state or reproducible experiments; synthetic and illustrative content is labeled.

### Important enhancements

- Scenario presets and side-by-side what-if comparison.
- Expanded Digital Twin inspection of buildings, hospitals, shelters, bridges, and rescue units.
- Scenario snapshots, exportable replay, and accessible keyboard controls.
- Per-agent event timeline with before/after state diffs.
- Saved model evaluation report and feature importance view.

### Stretch goals

- Optional import of a small, attribution-compliant real flood observation set for a separate flood-mapping experiment.
- Calibrated elevation raster and geospatial map import.
- Earthquake scenario after the flood vertical slice is reliable.
- OR-Tools optimization if simple deterministic assignment shows a measured shortcoming.

## Non-functional requirements

- Backend state is canonical; UI state cannot silently overwrite simulation truth.
- A seed plus scenario inputs and engine version identify a reproducible run.
- API schemas validate units, ranges, IDs, and state transitions.
- Each agent decision has a trigger, inputs, outputs, explanation, and event reference.
- Failures appear as actionable UI messages; the UI must not imply a rescue plan exists if routing or assignment failed.
- 3D geometry and simulation resolution remain small enough for a typical student laptop.
- The interface works at laptop and presentation-screen widths and does not rely on color alone.

## Acceptance criteria for the signature demo

- Resetting a scenario restores identical city and resource state for the same seed.
- Increasing rainfall changes the flood grid and at least one rendered risk or access state.
- A closed bridge cannot be included in a returned route.
- A change to a critical road triggers a logged plan revision.
- The plan remains pending until a human approves it.
- The dashboard shows the model's synthetic-data basis and compares its scores with a transparent baseline.
- Every claimed response-time or coverage improvement is computed over named deterministic scenarios and is not presented as real-world effectiveness.

## Explicit exclusions

No real emergency dispatch, operational hazard forecast, public alert, external AI API, cloud dependency, medical triage recommendation, unsupported real-world performance claim, or public source-code license is in scope for Part 1.
