# Part 11 implementation

## Experience

- Added `/judge`, a presentation view inside the existing React app. Entry is in the shared header; exit returns to Command Center.
- Judge Mode receives the same `scenario`, `city`, `events`, model and current-version predictions already held by `App`. It reads the existing agent dashboard, latest rescue recommendation, mission records and unit lifecycle records.
- The city occupies the primary canvas. Current physical flood depth, physical building exposure, model-predicted future exposure, resource availability, latest persisted agent trace, current proposal and mission lifecycle are separate evidence cards.
- Agent trace navigation includes the persisted event ID. Supporting links lead to the existing Model Lab, Decision Explorer, Scenario Lab and Guided Demo.
- Proposed plans remain unapproved. Judge Mode links to the existing commander controls and has no approve action.
- Stale predictions require matching scenario ID, state version, tick and loaded model version. Current traces also match scenario epoch, state version and infrastructure revision. Current proposals require matching scenario ID, epoch, state version and infrastructure revision. Historical records are not labeled current.
- Low-graphics mode is available at entry. A scene error boundary falls back to a backend-derived exposed-building table with simulated depth and local coordinates.
- The Command Center now labels buildings as physically exposed and reads unit availability from mission resource records rather than implying all inventory is on standby.
- Shared typography, panel headings, focus rings, controls, Guided Demo captions, and badges were made more legible and consistent across the existing workspaces. No UI framework or backend endpoint was added.

## Demonstration truth

The current event and all KPI values come from the shared app scenario or existing local API records. Physical flood exposure is distinct from ML-predicted future exposure. A model value without a current state-version match is withheld. Mission arrival remains distinct from explicit simulated completion. No lives-saved metric, real city fact, clinical triage claim, or automatic approval is presented.

## Scope boundaries

Judge Mode does not create a second scenario or a separate demo state. It does not execute a commander action. Approval, dispatch, mission time, route revision and return-to-service remain in the existing operational controls. The feature relies on existing REST polling and has no new backend service or online dependency.
