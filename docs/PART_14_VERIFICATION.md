# Part 14 RC1 verification

Baseline: Part 13 merge `f93b20e41b7c091be93ed72e31793576f7c8c466`; feature branch `feature/part-14-release-candidate`. Verification on Windows 11, 2026-10-17, with isolated operational databases under `%TEMP%`.

## Deterministic acceptance evidence

**Demo A:** seed 2026; mild preset, then rainfall 30 mm/h, river 0.6 m, drainage 0.2; six five-minute ticks. The production simulator recorded 10 physically impacted buildings and 0.1613 m peak cell depth; the local classifier returned 72 predictions and the persisted trace contains all six completed agents. The proposal contained four assignments with supported graph routes, including three-corridor routes. The selected route for the automated mission was 606.0 m. `unit-2` was explicitly dispatched; after 17 seconds mission time its authoritative progress was 91.7 m. Closing `road-ns-0` stopped it at that exact distance and advanced infrastructure revision to 1. The router proposed a supported 1053.6 m alternate route `road-ew-1 → road-ns-5 → road-ew-2`; the commander approved route revision 2 against current versions. The mission arrived at 1053.6 m, was explicitly completed, remained reserved, and became available only after explicit return-to-service. Read-only replay contained 17 durable mission events.

**Demo B:** a separate seed-2026 scenario with the same forcing and six ticks had all 10 modeled corridors closed through the normal API. The planner returned zero assignments, created zero missions, and reported 12 unreachable destinations with concrete constraints. No unsupported route or mission was created.

The focused RC1 runner passed **14 assertions in 18,515.629 ms**. Its JSON and Markdown outputs were written to the ignored `backend/artifacts/part14-rc1-acceptance/` folder; the runner used and removed a separate temporary operational DB. The Part 10 disposable acceptance workflow passed **17/17** checks in **14,913.748 ms**, including A/B isolation, interrupted-agent recovery, persisted mission/resource state, blocked movement, completion, return-to-service and restart recovery. The live `demo-preflight.ps1` passed **24/24** read-only checks.

## Performance and build evidence

The existing robustness benchmark evaluated 11 conditions in **844.701 ms** total, **43.543–133.639 ms** per condition, with a **264,828-byte** completed-study payload. At the extreme-flood horizon the original two routes were unsupported; zero reassignments and 72 unserved destinations were reported. All-road-closed also returned zero assignments. The mission benchmark ran after this correction for one moving unit on a 2 km route with 100 persisted one-second advances: mean **21.054 ms**, p95 **28.994 ms**, max **31.289 ms**; route-position interpolation averaged **0.001714 ms** and clock reads averaged **2.196 ms**.

| Build metric | Baseline | RC1 | Change |
|---|---:|---:|---:|
| Initial app JS min / gzip | 761.99 / 223.60 kB | 636.95 / 190.40 kB | −125.04 / −33.20 kB |
| Lazy CityScene JS min / gzip | 979.30 / 262.11 kB | 980.87 / 262.75 kB | +1.57 / +0.64 kB |

Production build passed. Vite's existing >500 kB chunk warning remains; it was not raised. The initial app improvement comes from route-level lazy loading of analytical and presentation workspaces.

## Browser and GPU

The URL-verified Edge browser inspected the Command Center, Scenario Lab, Model Intelligence Lab, AI Decision Explorer, Decision Robustness Lab and Judge Mode. A paired Demo A clock trace for scenario `scenario-riverside-2026`, epoch 0 recorded before-state flood version 8, mission `mission-5e0e85a8c7a554e5bac1` v2, clock 0s/v1, 0 m of 605.953108 m, segment index 0, position (-156.0, -70.0, elevation 1.0451 m). The UI's idempotent 10-second request (`70b97fce-3581-47d0-849d-146a14d61e48`) returned success with clock 10s/v2 and mission v3 at 13.88889 m travelled / 592.064218 m remaining, position (-156.0, -83.8889, elevation 1.2038 m). Fresh reads of clock, mission, unit location and persisted event `2678926f9dd0470aa4dbfcf83b1b48a7` matched. The old unpaired 20s/76.7m snapshot remains inconclusive, not evidence of a backend mutation failure.

The browser verified a same-ID reset to epoch 1 clearing the former mission/selection/route; six agent completions; proposal and explicit approval; dispatch; route segment and turn transitions across three corridors; road `road-ew-1` closure and blocking at 80m; route request returning an honest no-safe-route response while the road remained closed; supported API reopening; route revision approval; resumed progress to arrival at 630m; explicit simulated completion; explicit return-to-service; and persisted events/resource availability. The approved 630 m route crossed the modeled `road-ns-5` bridge segment, with elevation encoded in its saved route polyline; no separate bridge-elevation screenshot was saved. This does not claim a detour around the still-closed road. Demo B closed all ten corridors in the UI and showed zero assignments, 0m route distance and 12 unreachable destinations, with no new mission created. Previously approved missions remained visible as existing records.

Judge Mode displayed the same current zero-assignment proposal, six completed agent records, 0.16 m physical simulated depth, 10 currently exposed buildings, 12 model-predicted future exposures, and a commander-review requirement. The low-graphics control toggled and was restored. The Robustness Lab froze epoch 1/state version 16/infrastructure revision 12, ran a saved analytical study, and displayed zero original/replanned routes, a no-alternative explanation and its no-live-mutation boundary. These are correctly labeled synthetic/analytical outputs.

The final browser console showed no React maximum-update-depth error; the known non-blocking `THREE.Clock` deprecation warning remained. The viewport was 807×729 CSS px; three requested desktop sizes, direct refresh of every deep link, low-graphics/reduced-motion acceptance and WebGL context-loss recovery remain unverified. Screenshots were captured/displayed inline by the helper but were not saved as repository evidence files.

The prior foreground WebGL 2 `?perf=1` snapshots are recorded in `GPU_PERFORMANCE_RC1.md`; this correction did not rerun a controlled graphics sample. The probe forces continuous frames, so its rate estimate is not a guaranteed FPS. Browser build, memory, context-loss recovery, and matched movement/camera samples remain unavailable. The maximum-update-depth error was not observed during this browser retest; the original first stack was unavailable, so source attribution remains provisional. See `REACT_RENDER_LOOP_REVIEW.md`.

## Automated checks

| Check | Result |
|---|---|
| Backend pytest | **89 passed**, 1 Starlette/httpx deprecation warning |
| Frontend Vitest | **52 passed, 14 files** |
| ESLint / TypeScript | Passed / passed |
| OpenAPI export and TypeScript contract generation | Passed / passed |
| Production build | Passed; existing CityScene chunk-size warning; initial JS 638.95 kB min / 191.07 kB gzip; CityScene 980.87 kB min / 262.75 kB gzip |
| Part 10 preflight / disposable acceptance | **24/24 passed / 17/17 passed (21,578.520 ms)** |
| Part 14 disposable Demo A/B acceptance | **14/14 passed (11,279.879 ms)** |
| Part 13 robustness benchmark | **11 conditions; 370.001 ms total, 21.906–47.739 ms per condition** |
| Mission persistence benchmark | **100 advances; mean 4.412 ms, p95 5.077 ms, max 5.960 ms; position interpolation mean 0.001686 ms; clock-read mean 1.427 ms** |
| ML artifact integrity | Model, metadata (normalized LF), calibrator and support hashes match saved metadata |
| Windows startup/shutdown | Loopback health-gated start and Ctrl+C child shutdown verified with disposable DB; backend health readiness 3159.3 ms, frontend HTTP readiness 580 ms |
| Browser visual walkthrough | Demo A lifecycle and Demo B zero-assignment presentation verified; requested desktop viewports pending |
| Hosted GitHub Actions | Pending Part 14.2 commit and hosted run |

Model artifact SHA-256: `9375c9f2bd919d5124f1320eab04b406c4bf2ae7e63c791fee713122ff843b73`. Normalized `model_metadata.json` SHA-256: `7542b7d10be467ef560ec76bbe105ffc8001c063dfff177375cbef42cb0bf2d4`. Calibration artifact SHA-256: `64d50451b051092b0652a774064349d936c30eae93ce9b73f3790e3a29687ec6`. Support artifact SHA-256: `f01bcc84be76cc94b2df955ba5c9a90881e9823454c7aaa6da675833dc5f26f3`. Dataset SHA-256: `c560bdb345ad083f3f8e1d9d8a2d4928d2705bd7787f4e9640567a439040387d`.

PR #14: https://github.com/24f2003970/RESQ-AI/pull/14 (open, unmerged). Hosted CI run [39032141846](https://github.com/24f2003970/RESQ-AI/actions/runs/39032141846) passed on correction commit `3a57dc1ca60441f7b2630117f8f6c4aee0718b51`; both backend and frontend jobs succeeded. A documentation-only follow-up records this run and triggers a fresh check for the updated PR head.





## Bounded offline/security review

Static review of the launcher, Vite proxy, API CORS configuration and checked-in assets found loopback service binding, local font assets, and no external inference, CDN, map-tile or telemetry requirement. The preflight confirmed configured loopback URL/origin consistency. No formal OS network-isolation or penetration test was performed.
