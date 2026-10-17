# Part 14.1 React render-loop review

## Reported symptom

The PR #14 technical review reported repeated `Maximum update depth exceeded` errors while the Command Center was active. The first full browser stack and the exact triggering action were not preserved in that review, and the original state could not be reproduced from this local post-review session. This record does not claim a stack-trace-proven root cause.

## Source-level defects corrected

`MissionOperations` previously kept a local `selectedId` while its parent also owned `selectedMissionId`. Two effects copied selection in both directions. That duplicate authority made scenario changes and removal of the selected mission sensitive to effect ordering and stale selections. The child now renders the parent's selection and emits user/refresh selections through `onSelectMission` only.

The mission poll also published every newly fetched object snapshot to the parent even when values were unchanged. It now compares a deterministic snapshot identity before updating local mission state or publishing to the parent. Poll requests are sequence-guarded, aborted on scenario changes, and old mission, event, unit, clock, and selection state is cleared at the epoch boundary.

These changes remove concrete repeated-update paths and stale asynchronous writes. They are a source-level correction consistent with the review symptom, but without the original stack cannot establish that they were the sole cause of the earlier console error.

## Regression and browser evidence

- The frontend regression suite covers mission listing, selection, empty lists, offline behavior, selection clearing when switching to an empty scenario epoch, route-specific loading state, first client navigation, Back/Forward, and a second visit to an already-loaded workspace.
- Browser URL was independently verified as `http://127.0.0.1:5173/`. The retest exercised the Command Center, scenario controls, six completed agent records, proposal/approval, mission selection and dispatch, clock action, first workspace navigation and Back/Forward. The visible console contained the React DevTools info message and two repeated `THREE.Clock` deprecation warnings; no `Maximum update depth exceeded` or other console error was observed.
- The original error stack remains unavailable. Mission clock feedback did not advance the visible authoritative mission snapshot beyond 20 seconds / 76.7 m, so no claim is made about browser movement, blockage, rerouting, arrival or restore.
- Screenshots were viewed in the supported browser helper but could not be saved by its available interface. The retest viewport was 807×729 CSS px. Requested display-size and WebGL context-loss checks remain pending.

## Release status

The React error was not re-observed during the bounded browser retest after the source corrections. The symptom is clear in this retest, but attribution to the corrected selection/polling update paths remains provisional because the original triggering stack was not captured. Continue monitoring the browser console during the full mission walkthrough and capture the first complete stack if it recurs.
