# RC1 browser visual acceptance

## Verified walkthrough

**Browser:** Microsoft Edge, URL independently verified as `http://127.0.0.1:5173/`; app/API used a disposable SQLite database under `%TEMP%`. The available client viewport was 807×729 CSS pixels. Browser build/user-agent and requested 1366×768, 1440×900, and 1920×1080 viewport checks were not available in this session. Genuine screenshots were viewed in the helper but its supported interface did not save them as evidence files.

The Command Center rendered the 3D Riverside scene, current simulated flood values (tick 6, 0.16 m maximum, 10 physically exposed buildings), road/bridge legend, local inventory and mission operations. Camera controls and scroll layout were inspected. The browser showed four ready missions after commander approval and kept dispatch as a separate control. One mission was dispatched through the UI; its persisted dispatch event was visible. Six completed agent records and the 2608 m, three-road route were visible. A browser clock action displayed success feedback, but the selected mission remained at 20 seconds and 76.7 m in the last authoritative UI snapshot. Therefore multi-corner movement, closure/reroute, arrival, completion and return-to-service are **not verified in the browser**; those lifecycle stages pass the disposable backend acceptance workflow only.

The following workspaces were opened and their actual loaded content inspected: Scenario Lab (seeded flood forcing, computed depth, events/replay and isolated A/B controls), Model Intelligence Lab (synthetic grouped evaluation, held-out reliability, calibration status, support warning, current-state prediction inspector), AI Decision Explorer (six completed agent records and persisted mission-dispatch event), Decision Robustness Lab (frozen scenario/version/revision and analytical-only warning), and Judge Mode (read-only live evidence and explicit commander-review cue). Demo A and Demo B detailed end-to-end assertions are from the isolated acceptance runner.

First-visit navigation showed a route-specific loading screen before the destination workspace loaded. Back and Forward were exercised and displayed the matching route content. Deep-link refresh for all requested paths and requested desktop viewports were not tested. After the Command Center, scenario, selection, dispatch, clock-action and navigation sequence, the visible DevTools console contained the React DevTools info message and two repeated `THREE.Clock` deprecation warnings; no React maximum-update-depth error or other console error was present. The pre-fix first stack was not captured, so source attribution remains provisional; see [React render-loop review](REACT_RENDER_LOOP_REVIEW.md).

## Display sizes inspected

Requested desktop sizes **1366×768**, **1440×900**, and **1920×1080** remain pending. The captured client surface was 807×729 CSS pixels; the inspected controls at that size were reachable by scrolling.

## Remaining manual checklist

- [x] Confirm actual loopback URL, local connection, 3D city, flood values, current-versus-future labeling and camera controls.
- [x] Open the five requested analytical/presentation workspaces; inspect their loaded state labels and read-only/analytical boundaries.
- [x] Inspect a commander-approved mission and dispatch it through the visible UI; verify the persisted dispatch event.
- [ ] In the browser, advance a multi-corner mission, observe two corners and bridge elevation, close an ahead road, inspect a blocked stop and approve a genuine replacement route.
- [ ] In the browser, continue to arrival, explicitly complete the simulation and explicitly restore the unit.
- [ ] Inspect all three requested desktop viewport sizes.
- [ ] Browser verification of Demo B's unreachable presentation (automated acceptance passed).
- [ ] WebGL context-loss/recovery interaction; no context-loss event was induced.

Mission progression, closure/reroute geometry, arrival and restore are proven by backend acceptance and API state, not by the partial browser mission walkthrough. The browser observations above do not establish real-world visual fidelity or operational safety.
