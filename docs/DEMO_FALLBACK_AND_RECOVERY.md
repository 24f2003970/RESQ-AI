# Demo fallback and recovery

## Before judges arrive

1. Follow `LOCAL_DEMO_QUICKSTART.md` and run `scripts/demo-preflight.ps1`.
2. Use a disposable demo database and confirm its path is separate from any work or operational database. Never delete an existing database to prepare a demo.
3. Prepare a fresh Demo A seed 2026 scenario: mild preset, rainfall 30 mm/h, river 0.6 m, drainage 0.2, six flood ticks.
4. Verify local model status, six-agent trace, a supported proposal, route list, mission controls, and UI reachability. Preflight verifies loopback HTTP/API readiness; it is not browser visual QA.
5. Rehearse road closure while a vehicle is moving. Expect a blocked state. Verify whether a route can be proposed under current closures; do not promise one. The recorded successful route revision followed reopening the relevant road.
6. Keep Demo B prepared separately: all ten modeled corridors closed, zero supported ground assignments.
7. Keep a genuine Part 15 screenshot and checked-in evaluation data ready as saved evidence. Label its actual capture time, scenario and epoch; never present it as current live state.

## If a live action fails

- **API becomes disconnected:** Stop issuing commands. Use the application's reconnect control once. If service health is not restored, switch to a genuine prior screenshot or checked-in evaluation data and narrate that the live backend is unavailable. Do not claim a stale screen is current.
- **Flood advance fails or shows different values:** Read the actual backend response, verify the scenario seed and parameters, and report the current measured result. If values still differ, prepare a fresh disposable Demo A after the presentation or describe the saved acceptance as a separate run.
- **No route is available:** Show the blocked state and explain the closure, depth, bridge or connectivity constraint. Leave the mission blocked. Do not approve a speculative route or imply the all-road-closed case has an alternative.
- **Route revision fails:** Check whether the closing road remains closed and whether the saved route starts at current progress. Reopen only through the documented control when the demo narrative permits, request a new proposal and require explicit approval. A replacement route is not guaranteed.
- **Mission clock or UI is stale:** Refresh from the backend. Do not infer progress from animation; the backend's traversed-distance value is authoritative.
- **Model is unavailable:** Show the actual degraded state and physical-simulator fallback. Do not describe a fabricated probability as an ML result.
- **WebGL fails:** Use the supported error fallback and backend-derived tables. The WebGL context-loss path was not browser-verified in Part 16. If you show a saved screenshot, label it as prior genuine evidence.
- **All else fails:** Stop commands; present the architecture, actual checked-in report, reliability chart and explicit limitations. Do not synthesize a composite success story.

## Recovery boundaries

1. Run `scripts/demo-preflight.ps1` and inspect readiness output.
2. Check Python 3.12, Node 22.12+, dependencies, model artifact and configured ports.
3. Do not terminate unrelated processes to resolve a port conflict. Inspect ownership first and use the supported launcher.
4. Restart with `scripts/start-resq-ai.ps1` and wait for loopback health checks.
5. Keep the existing SQLite database. Never delete it as a routine recovery step.

After dependencies and artifacts are installed, the configured demo uses local inference and loopback services without required hosted inference or map tiles. Package installation and GitHub CI require connectivity unless dependencies are already cached. The project has not passed formal OS network isolation or penetration testing.

Related: `LOCAL_DEMO_QUICKSTART.md`, `DEMO_PREFLIGHT.md`, `OFFLINE_AUDIT.md`, `FINAL_DEMO_REHEARSAL.md`, `FINAL_VISUAL_QA.md`.
