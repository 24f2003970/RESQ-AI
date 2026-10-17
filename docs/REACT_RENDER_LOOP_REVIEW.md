# Part 14.1 React render-loop review

## Reported symptom

The PR #14 technical review reported repeated `Maximum update depth exceeded` errors while the Command Center was active. The first full browser stack and the exact triggering action were not preserved in that review, and the original state could not be reproduced from this local post-review session. This record does not claim a stack-trace-proven root cause.

## Source-level defects corrected

`MissionOperations` previously kept a local `selectedId` while its parent also owned `selectedMissionId`. Two effects copied selection in both directions. That duplicate authority made scenario changes and removal of the selected mission sensitive to effect ordering and stale selections. The child now renders the parent's selection and emits user/refresh selections through `onSelectMission` only.

The mission poll also published every newly fetched object snapshot to the parent even when values were unchanged. It now compares a deterministic snapshot identity before updating local mission state or publishing to the parent. Poll requests are sequence-guarded, aborted on scenario changes, and old mission, event, unit, clock, and selection state is cleared at the epoch boundary.

These changes remove concrete repeated-update paths and stale asynchronous writes. They are a source-level correction consistent with the review symptom, but without the original stack cannot establish that they were the sole cause of the earlier console error.

## Regression and browser evidence

- The frontend regression suite now covers authoritative clock responses, polling/mutation races, older responses arriving later, duplicate clicks, stale-version errors, blocked/arrived states, same-ID epoch reset, selection clearing and stale overlay suppression, in addition to prior navigation and empty-state cases.
- Browser URL was independently verified as `http://127.0.0.1:5173/`. The retest exercised the Command Center, six completed agents, proposal/approval, dispatch, route-segment movement, road closure/blocking, route request, route revision approval after reopening the closed road, arrival, simulated completion, explicit unit restoration and all-roads-closed refusal. No `Maximum update depth exceeded` warning was observed. The Vite log showed the known `THREE.Clock` deprecation notice and transient proxy connection errors during the controlled backend restart; service calls succeeded after restart.
- The first historical error stack remains unavailable, so source attribution remains provisional. A paired before/response/fresh-GET clock trace agreed; the earlier 20-second / 76.7 m snapshot remains inconclusive because it lacked a matching before-state.
- Screenshots were captured and displayed by the supported browser helper but could not be saved as evidence files. The viewport was 807×729 CSS px. Requested desktop sizes and WebGL context-loss checks remain pending.

## Release status

The React error was not re-observed during the bounded browser retest after the source corrections. The symptom is clear in this retest, but attribution to the corrected selection/polling update paths remains provisional because the original triggering stack was not captured. Continue monitoring the browser console during the full mission walkthrough and capture the first complete stack if it recurs.
