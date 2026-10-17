# RC1 browser visual acceptance

## Verified walkthrough

**Browser:** Microsoft Edge, URL independently verified as `http://127.0.0.1:5173/`; app/API used a disposable SQLite database under `%TEMP%`. The available client viewport was 807×729 CSS pixels. Browser build/user-agent and requested 1366×768, 1440×900, and 1920×1080 viewport checks were not available in this session. Genuine screenshots were viewed in the helper but its supported interface did not save them as evidence files.

The Command Center rendered the 3D Riverside scene, current simulated flood values (tick 6, 0.16 m maximum, 10 physically exposed buildings), road/bridge legend, local inventory and mission operations. The browser showed four ready missions after commander approval, six completed agent records, a four-assignment proposal, and a separate dispatch control.

**Clock trace (scenario `scenario-riverside-2026`, epoch 0):** before the first advance, flood state version 8, mission `mission-5e0e85a8c7a554e5bac1` version 2 was en route at 0 seconds (clock v1), 0 m travelled / 605.953108 m remaining, segment index 0, position (-156.0, -70.0, elevation 1.0451 m). The UI issued one 10-second advance with idempotency key `70b97fce-3581-47d0-849d-146a14d61e48`. The successful response returned clock 10 seconds/v2, mission v3, 13.88889 m travelled / 592.064218 m remaining and position (-156.0, -83.8889, elevation 1.2038 m). Fresh reads of the clock, mission, current unit location and persisted `clock_advanced` event (`2678926f9dd0470aa4dbfcf83b1b48a7`) agreed. The earlier unpaired 20-second/76.7 m snapshot cannot establish a defect; that specific discrepancy remains **inconclusive**. The frontend now applies authoritative mutation results immediately and rejects older poll responses.

The browser verified a same-ID reset to epoch 1 and cleared the prior mission selection and route overlay. Demo A then produced four assignments; a unit was dispatched and moved across route segments and road turns. The approved 630 m route crossed the modeled bridge segment and stored elevation changes, though no separate bridge-elevation screenshot was saved. Closing `road-ew-1` at 80 m blocked the unit at that distance. With the road closed and this high-flood graph active, the route request returned an explicit no-safe-route response (the destination could not attach within the documented 90 m access limit). After reopening that road through the supported API, a replacement route was proposed and explicitly approved in the UI; the mission resumed from its recorded position, arrived at 630 m, was explicitly completed and returned to service. Persisted events showed arrival, completion and return; availability increased only after return. This verifies mission lifecycle and route-revision handling, but not a detour while the closure remained active.

For Demo B, the browser UI closed all ten modeled corridors. A fresh proposal showed **0 assignments, 0 m optimized distance and 12 unreachable destinations**, with no new mission created. Previously approved missions remained visible as their own records. Screenshot capture was shown inline, but the helper did not save an evidence file.

The following workspaces were opened and their loaded content inspected: Scenario Lab (seeded flood forcing, computed depth, events/replay and isolated A/B controls), Model Intelligence Lab (synthetic grouped evaluation, held-out reliability, calibration status, support warning, current-state prediction inspector), AI Decision Explorer (six completed agent records and persisted mission-dispatch event), Decision Robustness Lab (frozen scenario/version/revision and a saved analytical-only study), and Judge Mode (read-only evidence, zero-assignment current plan and explicit commander-review cue). Demo A and Demo B details are also covered by the isolated acceptance runner.

First-visit navigation showed a route-specific loading screen before the destination workspace loaded. Back and Forward displayed matching route content. Deep-link refresh for all requested paths and requested desktop viewports were not tested. No React maximum-update-depth error was observed during the bounded walkthrough. The Vite terminal showed upstream `THREE.Clock` deprecation warnings and transient proxy connection errors only during the controlled backend restart; after restart, API requests and the browser walkthrough succeeded. The pre-fix first stack was not captured, so source attribution remains provisional; see [React render-loop review](REACT_RENDER_LOOP_REVIEW.md).

## Display sizes inspected

Requested desktop sizes **1366×768**, **1440×900**, and **1920×1080** remain pending. The captured client surface was 807×729 CSS pixels; the inspected controls at that size were reachable by scrolling.

## Remaining manual checklist

- [x] Confirm actual loopback URL, local connection, 3D city, flood values, current-versus-future labeling and camera controls.
- [x] Open the five requested analytical/presentation workspaces; inspect their loaded state labels and read-only/analytical boundaries.
- [x] Inspect a commander-approved mission and dispatch it through the visible UI; verify the persisted dispatch event.
- [x] In the browser, advance the mission and observe route-segment/corner movement; close an ahead road and confirm a blocked stop. No safe route was supported while this road remained closed; after reopening it through the supported API, approve a genuine route revision. A closure-avoiding detour was not demonstrated in this high-flood scenario.
- [x] In the browser, continue to arrival, explicitly complete the simulation and explicitly restore the unit; verify persisted events and resource availability.
- [ ] Inspect all three requested desktop viewport sizes.
- [x] Browser verification of Demo B: all ten corridors closed, refreshed proposal showed zero assignments and 12 unreachable destinations, and no new mission was created.
- [ ] WebGL context-loss/recovery interaction; no context-loss event was induced.

The browser observations verify the local application flow only. They do not establish real-world visual fidelity, surveyed connectivity or operational safety. The first React maximum-update-depth stack was not captured, and a detour around the closed road could not be generated in the actual Demo A graph/flood state.
