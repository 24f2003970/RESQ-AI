# Part 11 visual acceptance checklist

## Safe browser setup

1. Run `scripts\start-resq-ai.ps1` and note the frontend URL printed by the launcher.
2. Run `scripts\demo-preflight.ps1`; resolve any failed check before the walkthrough.
3. Use a browser session only after its current URL has been independently verified. If the computer-use helper cannot verify it, stop the browser workflow and record it as pending. Do not type a guessed localhost URL to work around that restriction.
4. Record browser name/version, URL as verified by the helper, viewport, OS/GPU if available, graphics setting, timestamp and actual outcome. Attach only screenshots captured from this session.

## Viewports

- [ ] 1366 × 768 laptop
- [ ] 1440 × 900 laptop
- [ ] 1920 × 1080 desktop

## Walkthrough and evidence

- [ ] Default city overview: current simulation version, depth legend, selection, available/committed resources.
- [ ] Severe flood: simulated water depth and physical building exposure update from the backend.
- [ ] Current flood versus predicted-risk overlays: separate labels; stale prediction count hidden.
- [ ] Six-agent trace: current version status, persisted trace link and error/degraded display.
- [ ] Proposal: route, solver status, baseline and explicit pending commander decision.
- [ ] Approval: only after the human uses existing commander controls.
- [ ] Mission dispatch: no movement before dispatch or mission-clock progression.
- [ ] Two road turns: vehicle remains on the approved route polyline; inspect corners and elevation where visible.
- [ ] Closure: vehicle stops before an impassable remaining edge; stale route cannot be represented as approved.
- [ ] Route revision: new route or explicit blocked/unreachable state; approval remains manual.
- [ ] Arrival, explicit completion and return-to-service appear as separate actions/states.
- [ ] Scenario A/B: same-snapshot experiment results and their saved labels.
- [ ] Guided Demo: stage changes only after successful API response and evidence checks; no auto-advance through commander review.
- [ ] Judge Mode: entry/exit, shared scenario version, live event, KPIs, next action, evidence links, approval requirement.
- [ ] Low graphics and system reduced-motion preference.
- [ ] Loading and offline/API failure messages; 3D fallback evidence table.
- [ ] Keyboard-only navigation through entry, mode controls, evidence links and exit; focus ring remains visible.

## Report

Record each checkbox as pass, fail, blocked or not applicable, with the observed reason. Do not report FPS, GPU utilization, draw calls or visual pass without actual instrumented measurements or inspection. Browser inspection remains pending unless this checklist is completed in a verified session.

### Part 11 attempt · 2026-10-16

The Part 10 launcher started both local services and the read-only preflight passed 24/24 checks. The computer-use helper stopped before browser selection with: “could not determine the current browser URL on Windows with enough confidence to enforce policy.” The requested browser workflow was stopped at that point. No screenshots were captured; all viewport and visual walkthrough items remain pending.
