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

The URL-verified Edge browser inspected the Command Center, Scenario Lab, Model Intelligence Lab, AI Decision Explorer, Decision Robustness Lab and Judge Mode. The seeded flood, six completed agents, route/mission panel, and explicit dispatch action were visible. One mission was dispatched through the UI and its persisted event was visible. First navigation showed route-specific loading, then the selected route; Back and Forward returned to matching content. The final console showed only the React DevTools info message and repeated upstream `THREE.Clock` deprecation warnings; no React maximum-update-depth or other console error was observed during the bounded walkthrough. Browser mission progression did not advance beyond its 20-second/76.7 m UI snapshot after the clock action, so browser closure/reroute/arrival/completion/restore and Demo B remain pending. The available client viewport was 807×729 CSS px; the three requested display sizes, direct refresh of every deep link, low-graphics/reduced-motion acceptance, and WebGL context-loss recovery were not fully retested. No screenshot was saved into the repository.

The prior foreground WebGL 2 `?perf=1` snapshots are recorded in `GPU_PERFORMANCE_RC1.md`; this correction did not rerun a controlled graphics sample. The probe forces continuous frames, so its rate estimate is not a guaranteed FPS. Browser build, memory, context-loss recovery, and matched movement/camera samples remain unavailable. The maximum-update-depth error was not observed during this browser retest; the original first stack was unavailable, so source attribution remains provisional. See `REACT_RENDER_LOOP_REVIEW.md`.

## Automated checks

| Check | Result |
|---|---|
| Backend pytest | **89 passed**, 1 upstream Starlette/httpx deprecation warning |
| Frontend Vitest | **43 passed, 13 files** |
| ESLint | Passed |
| TypeScript | Passed |
| OpenAPI export and TypeScript contract generation | Passed |
| Production build | Passed; existing CityScene chunk-size warning |
| Part 10 preflight / disposable acceptance | **24/24 / 17/17 passed** |
| Part 14 disposable Demo A/B acceptance | **14/14 passed; 18,515.629 ms** |
| Part 13 robustness benchmark | **11 conditions passed; 844.701 ms total** |
| Mission persistence benchmark | **100 advances; mean 21.054 ms, p95 28.994 ms, max 31.289 ms** |
| ML artifact integrity | Model, metadata (normalized LF), calibrator and support hashes match saved metadata |
| Windows startup/shutdown | Loopback health-gated start and Ctrl+C child shutdown verified with disposable DB |
| Browser visual walkthrough | Partial; route navigation verified; movement stalled at 20 s/76.7 m in UI; Demo B and requested viewports pending |
| Hosted GitHub Actions | Pending commit and hosted run |

Model artifact SHA-256: `9375c9f2bd919d5124f1320eab04b406c4bf2ae7e63c791fee713122ff843b73`. Normalized `model_metadata.json` SHA-256: `7542b7d10be467ef560ec76bbe105ffc8001c063dfff177375cbef42cb0bf2d4`. Calibration artifact SHA-256: `64d50451b051092b0652a774064349d936c30eae93ce9b73f3790e3a29687ec6`. Support artifact SHA-256: `f01bcc84be76cc94b2df955ba5c9a90881e9823454c7aaa6da675833dc5f26f3`. Dataset SHA-256: `c560bdb345ad083f3f8e1d9d8a2d4928d2705bd7787f4e9640567a439040387d`.

PR #14: https://github.com/24f2003970/RESQ-AI/pull/14 (open, unmerged). The latest hosted run on the new commit is pending; do not treat the earlier passing run as validation of this revision.





## Bounded offline/security review

Static review of the launcher, Vite proxy, API CORS configuration and checked-in assets found loopback service binding, local font assets, and no external inference, CDN, map-tile or telemetry requirement. The preflight confirmed configured loopback URL/origin consistency. No formal OS network-isolation or penetration test was performed.
