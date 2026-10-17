# Part 14 RC1 verification

Baseline: Part 13 merge `f93b20e41b7c091be93ed72e31793576f7c8c466`; feature branch `feature/part-14-release-candidate`. Verification on Windows 11, 2026-10-17, with isolated operational databases under `%TEMP%`.

## Deterministic acceptance evidence

**Demo A:** seed 2026; mild preset, then rainfall 30 mm/h, river 0.6 m, drainage 0.2; six five-minute ticks. The production simulator recorded 10 physically impacted buildings and 0.1613 m peak cell depth; the local classifier returned 72 predictions and the persisted trace contains all six completed agents. The proposal contained four assignments with supported graph routes, including three-corridor routes. The selected route for the automated mission was 606.0 m. `unit-2` was explicitly dispatched; after 17 seconds mission time its authoritative progress was 91.7 m. Closing `road-ns-0` stopped it at that exact distance and advanced infrastructure revision to 1. The router proposed a supported 1053.6 m alternate route `road-ew-1 → road-ns-5 → road-ew-2`; the commander approved route revision 2 against current versions. The mission arrived at 1053.6 m, was explicitly completed, remained reserved, and became available only after explicit return-to-service. Read-only replay contained 17 durable mission events.

**Demo B:** a separate seed-2026 scenario with the same forcing and six ticks had all 10 modeled corridors closed through the normal API. The planner returned zero assignments, created zero missions, and reported 12 unreachable destinations with concrete constraints. No unsupported route or mission was created.

The focused RC1 runner passed **14 assertions in 17,537.199 ms**. Its JSON and Markdown outputs were written to the ignored `backend/artifacts/part14-rc1-acceptance/` folder; the runner used and removed a separate temporary operational DB. The Part 10 disposable acceptance workflow passed **17/17** checks, including A/B isolation, interrupted-agent recovery, persisted mission/resource state, blocked movement, completion, return-to-service and restart recovery. `demo-preflight.ps1` passed 24/24 read-only checks in the local startup rehearsal.

## Performance and build evidence

The existing robustness benchmark evaluated 11 conditions in **341.379 ms** total, **22.473–51.932 ms** per condition, with a **264,817-byte** completed-study payload. At the extreme-flood horizon the original two routes were unsupported; zero reassignments and 72 unserved destinations were reported. All-road-closed also returned zero assignments. The existing mission benchmark ran 100 persisted one-second advances for one moving unit on a 2 km route: mean **4.483 ms**, p95 **4.985 ms**, max **5.581 ms**; interpolation mean **0.0017 ms**.

| Build metric | Baseline | RC1 | Change |
|---|---:|---:|---:|
| Initial app JS min / gzip | 761.99 / 223.60 kB | 636.49 / 190.24 kB | −125.50 / −33.37 kB |
| Lazy CityScene JS min / gzip | 979.30 / 262.11 kB | 980.87 / 262.75 kB | +1.57 / +0.64 kB |

Production build passed. Vite's existing >500 kB chunk warning remains; it was not raised. The initial app improvement comes from route-level lazy loading of analytical and presentation workspaces.

## Browser and GPU

The URL-verified Codex in-app browser inspected the Command Center, Scenario Lab, Model Intelligence Lab, AI Decision Explorer, Decision Robustness Lab and Judge Mode. The seeded current/future exposure distinction, six completed agents, synthetic model reliability warnings, read-only judge boundary, route/mission panel, and explicit dispatch action were visible. One mission was dispatched through the UI and its persisted event was visible in Decision Explorer. The full multi-corner movement, closure/reroute, arrival/completion and restore sequence was verified by the isolated backend runner, not the browser. All three requested desktop viewport sizes (1366×768, 1440×900, 1920×1080) were inspected. No screenshot was saved into the repository.

The foreground WebGL 2 `?perf=1` snapshots are recorded in `GPU_PERFORMANCE_RC1.md`: Standard 742 samples, 6.1/10.0/30.1 ms median/p95/p99, 72 draw calls, 90,018 triangles; Low 778 samples, 6.0/9.0/21.3 ms, 56 draw calls, 55,344 triangles. The probe forces continuous frames, so its rate estimate is not a guaranteed FPS. The WebGL renderer identified Intel UHD Graphics (0x468B), Direct3D11; browser build, memory, context-loss recovery, and matched movement/camera samples were unavailable. Repeated React “Maximum update depth exceeded” errors occurred in the browser console while Command Center was active; source was not isolated and remains an RC1 review item.

## Automated checks

| Check | Result |
|---|---|
| Backend pytest | **89 passed**, 1 upstream Starlette/httpx deprecation warning |
| Frontend Vitest | **40 passed, 13 files** |
| ESLint | Passed |
| TypeScript | Passed |
| OpenAPI export and TypeScript contract generation | Passed |
| Production build | Passed; existing CityScene chunk-size warning |
| Part 10 preflight / disposable acceptance | **24/24 / 17/17 passed** |
| Part 14 disposable Demo A/B acceptance | **14/14 passed** |
| Part 13 robustness benchmark | **11 conditions passed; 341.379 ms total** |
| Mission persistence benchmark | **100 advances; mean 4.483 ms, p95 4.985 ms** |
| ML artifact integrity | Model, metadata (normalized LF), calibrator and support hashes match saved metadata |
| Windows startup/shutdown | Loopback health-gated start and Ctrl+C child shutdown verified with disposable DB |
| Browser visual walkthrough | Partial; full mission lifecycle and Demo B browser flow remain unverified |
| Hosted GitHub Actions | Pending PR creation and hosted run |

Model artifact SHA-256: `9375c9f2bd919d5124f1320eab04b406c4bf2ae7e63c791fee713122ff843b73`. Normalized `model_metadata.json` SHA-256: `7542b7d10be467ef560ec76bbe105ffc8001c063dfff177375cbef42cb0bf2d4`. Calibration artifact SHA-256: `64d50451b051092b0652a774064349d936c30eae93ce9b73f3790e3a29687ec6`. Support artifact SHA-256: `f01bcc84be76cc94b2df955ba5c9a90881e9823454c7aaa6da675833dc5f26f3`. Dataset SHA-256: `c560bdb345ad083f3f8e1d9d8a2d4928d2705bd7787f4e9640567a439040387d`.

PR #14: https://github.com/24f2003970/RESQ-AI/pull/14 (open, unmerged). Hosted workflow: https://github.com/24f2003970/RESQ-AI/actions/runs/39021015304 on revision `41ddae0d2394dcf7a6e38ac032e2e3dfa577c929`; backend and frontend jobs both succeeded at 2026-10-17 09:25 UTC. A documentation-only follow-up records the completed outcome and triggers a fresh run for the updated PR head.





## Bounded offline/security review

Static review of the launcher, Vite proxy, API CORS configuration and checked-in assets found loopback service binding, local font assets, and no external inference, CDN, map-tile or telemetry requirement. The preflight confirmed configured loopback URL/origin consistency. No formal OS network-isolation or penetration test was performed.
