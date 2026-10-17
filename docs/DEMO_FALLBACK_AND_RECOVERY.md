# Demo fallback and recovery

## Before judges arrive

1. Follow `LOCAL_DEMO_QUICKSTART.md` and run `scripts/demo-preflight.ps1`.
2. Use the disposable demo database and confirm its path is separate from any work or operational database.
3. Prepare a fresh Demo A seed 2026 scenario: mild preset, rainfall 30 mm/h, river 0.6 m, drainage 0.2, six flood ticks.
4. Verify local model status, six-agent trace, one supported proposal, route list, mission controls, and UI reachability.
5. Rehearse road closure while the vehicle is moving. Expect a blocked state. Verify whether a route can be proposed under current closures; do not promise one. The recorded successful revision followed reopening `road-ns-0`.
6. Keep Demo B prepared separately: same forcing, all ten modeled corridors closed, zero supported ground assignments.

## If a live action fails

- **API becomes disconnected:** Stop making commands. Use the browser's reconnect control once. If service health is not restored, switch to the last committed screenshot or the checked-in evaluation data and narrate that the live backend is unavailable. Do not claim a stale screen is current.
- **Flood advance fails or shows different values:** Read the actual backend response, verify scenario seed and parameter values, and report the current measured result. If values still differ, use a fresh disposable Demo A after the presentation or describe the saved acceptance as a separate run.
- **No route is available:** Show the blocked state and explain the closure/depth constraints. Leave the mission blocked. Do not approve a speculative route or imply the all-road-closed case has an alternative.
- **Route revision fails:** Check whether the closing road is still closed and whether the saved route starts at the current segment/progress. Reopen only using the documented control when the demo narrative permits, then request a new proposal. Approval must reference the new revision.
- **Mission clock or UI is stale:** Refresh from the backend. Do not infer progress from the 3D animation. The mission API's traveled-distance value is authoritative.
- **Model is unavailable:** Show the degraded state and deterministic physical simulator. Do not describe a fabricated probability as an ML result.
- **WebGL fails:** Switch to accessible building inventory / backend tables. Use the fallback narration below.
- **All else fails:** Stop commands; present the architecture, actual checked-in report, reliability chart and explicit limitations. Do not synthesize a composite success story.

## WebGL fallback narration (about 30 seconds)

“The 3D scene is a read-only projection of backend state. The browser renderer is unavailable on this machine, so I will use the accessible inventory and the saved API evidence. The simulation and route calculations remain backend-controlled. This screen is evidence of an interface limitation, not a change in modeled flood or mission state.”

## Recovery boundary

Do not clear, delete or reset a live database to fix a demo. For a fresh presentation, create a new scenario in the disposable demo store using the documented setup. Preserve logs and screenshot context if a failure needs later diagnosis.
