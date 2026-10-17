# RESQ-AI Release Candidate 1 manifest

| Field | RC1 value |
|---|---|
| Candidate | `RESQ-AI-RC1` (Part 14) |
| Repository branch | `feature/part-14-release-candidate` |
| Base | Part 13 merge `f93b20e41b7c091be93ed72e31793576f7c8c466` |
| Commit | RC1 implementation commit `3da8c11757cc5211c6ddd694bc0e0def53370734`; hosted verification may append a documentation-only commit |
| Application | Backend API 0.4.0; frontend package 0.2.0 |
| Python / Node | Python 3.12.5; Node 24.12.0 (frontend minimum 22.12; CI uses Node 22) |
| Tested OS / browser | Windows 11 workstation; Codex in-app Chromium-backed browser, WebGL 2. Exact browser build/user-agent unavailable. |
| Hardware sample | Intel Core i5-13500HX, 14 cores / 20 threads; Intel UHD Graphics and NVIDIA RTX 4050 present. Captured WebGL renderer: Intel UHD Graphics (0x468B), Direct3D11. |
| Model artifact | `backend/ml_artifacts/flood_exposure_v1.joblib`, SHA-256 `9375c9f2bd919d5124f1320eab04b406c4bf2ae7e63c791fee713122ff843b73` |
| Model metadata | Normalized LF SHA-256 `7542b7d10be467ef560ec76bbe105ffc8001c063dfff177375cbef42cb0bf2d4` |
| Calibration artifact | `flood_exposure_platt_v1.joblib`, SHA-256 `64d50451b051092b0652a774064349d936c30eae93ce9b73f3790e3a29687ec6` |
| Distribution support artifact | `distribution_support_v1.json`, SHA-256 `f01bcc84be76cc94b2df955ba5c9a90881e9823454c7aaa6da675833dc5f26f3` |
| Dataset | SHA-256 `c560bdb345ad083f3f8e1d9d8a2d4928d2705bd7787f4e9640567a439040387d` |
| Startup | `scripts\start-resq-ai.ps1`; launcher prints loopback UI URL after backend health |
| Generated assets | None required beyond checked-in local model/reliability assets and installed dependencies |
| Database | SQLite initialized/migrated by the app. Preserve existing data; launcher quick-check is read-only. |
| Supported demo modes | Local Command Center, Guided Demo, deterministic positive Demo A and all-corridors-closed Demo B |
| External runtime dependency | No cloud inference/API key; Python/npm dependencies required locally. No formal OS-level isolation test. |
| Verification totals | 89 backend; 40 frontend; lint/typecheck/contracts/build pass; Part 10 17/17; Part 14 14/14; see verification file. |
| Known limitations | Synthetic-only assumptions; boat routing/field safety unsupported; CityScene chunk warning; partial browser mission walkthrough; React console errors require review. |
| Verification timestamp | Local verification completed 2026-10-17; hosted checks were triggered at 2026-10-17 09:23 UTC; final run URL is in `PART_14_VERIFICATION.md` |

This manifest describes an educational simulation prototype. It is not an operational certification, public production release, or emergency-response safety determination.
