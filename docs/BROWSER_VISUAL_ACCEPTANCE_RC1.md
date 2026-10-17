# RC1 browser visual acceptance

## Verified walkthrough

**Browser:** Codex in-app browser, Chromium-backed WebGL 2 context. The helper independently reported `http://127.0.0.1:5173/`; the app and API used the disposable `%TEMP%\resq-part14-browser\operational.sqlite3` database. The browser build string and user-agent were not exposed. Screenshots were reviewed in the browser tool but were not saved as repository evidence.

The Command Center rendered the 3D Riverside scene, current simulated flood values (tick 6, 0.16 m maximum, 10 physically exposed buildings), road/bridge legend, local inventory and mission operations. Camera preset, orbit/zoom/reset controls, visible low-graphics mode, and scrollable page layout were inspected. The browser showed four ready missions after commander approval and kept their dispatch as a separate control. One mission was dispatched using the UI and its event appeared in Decision Explorer; route advancement, mid-route closure, revision approval, arrival, completion and return-to-service were verified by the disposable backend acceptance runner, not by the browser walkthrough.

The following workspaces were opened and their actual loaded content inspected: Scenario Lab (seeded flood forcing, computed depth, events/replay and isolated A/B controls), Model Intelligence Lab (synthetic grouped evaluation, held-out reliability, calibration status, support warning, current-state prediction inspector), AI Decision Explorer (six completed agent records and persisted mission-dispatch event), Decision Robustness Lab (frozen scenario/version/revision and analytical-only warning), and Judge Mode (read-only live evidence and explicit commander-review cue). Demo A and Demo B detailed end-to-end assertions are from the isolated acceptance runner.

The first in-app sidebar navigation immediately after a page load briefly retained the previous workspace content while the selected navigation changed; a normal reload to the selected route loaded it correctly, and subsequent workspace navigation loaded its selected view. This is a browser observation to review, not claimed as fully resolved by the RC1 optimization. Console output also contained repeated React “Maximum update depth exceeded” errors while the 3D Command Center was active; source attribution was not established in this walkthrough. These observations are listed as outstanding browser review items.

## Display sizes inspected

The live page was inspected at **1366×768**, **1440×900**, and **1920×1080**. At each size the 3D twin remained dominant, the mission/controls column stayed visible, and lower panels remained reachable by scrolling; no clipped primary controls were observed. The browser helper supplied a 1265×720 DOM viewport in its initial state; later viewport resizing was supported and the three target sizes were set directly. The screenshot surface was 1920×1080 on the final capture.

## Remaining manual checklist

- [x] Confirm actual loopback URL, local connection, 3D city, flood values, current-versus-future labeling and camera controls.
- [x] Open the five requested analytical/presentation workspaces; inspect their loaded state labels and read-only/analytical boundaries.
- [x] Inspect a commander-approved mission and dispatch it through the visible UI; verify the persisted dispatch event.
- [ ] In the browser, advance a multi-corner mission, observe two corners and bridge elevation, close an ahead road, inspect a blocked stop and approve a genuine replacement route.
- [ ] In the browser, continue to arrival, explicitly complete the simulation and explicitly restore the unit.
- [x] Inspect all three requested desktop viewport sizes.
- [ ] Browser verification of Demo B's unreachable presentation (automated acceptance passed).
- [ ] WebGL context-loss/recovery interaction; no context-loss event was induced.

Mission progression, closure/reroute geometry, arrival and restore are proven by backend acceptance and API state, not by the partial browser mission walkthrough. The browser observations above do not establish real-world visual fidelity or operational safety.
