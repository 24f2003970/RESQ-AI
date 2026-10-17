# Part 16 verification and release matrix

Date: 2026-10-17. Base: `main` at Part 15 merge `156b88dfda55728a3e8ecc3ff23fc5d5826b9ddb`. Branch: `feature/part-16-final-release`. Candidate: `RESQ-AI v1.0.0-rc-final`; not published. The worktree began with local Part 16 changes and two pre-existing untracked baselines, both preserved. The browser helper's URL safety stop was respected; no browser was retried or bypassed.

Statuses: **PASS**, **FAIL**, **PENDING**, **BLOCKED**, **ACCEPTED LIMITATION**. A blocked or pending item is not a test pass.

## Release approval matrix

| Requirement | Verification / observed result | Evidence | Severity | Owner / next action | Status |
|---|---|---|---|---|---|
| Backend suite | 91 passed in 66.57 s; one upstream Starlette/httpx deprecation warning | Full Pytest output; `backend/tests/` | High | Review warning during dependency upgrade | PASS |
| Frontend suite | 52 passed across 14 test files in 19.90 s; intentional WebGL-unavailable test logs expected error-boundary output | Vitest output | High | None for this run | PASS |
| ESLint | `npm run lint` exit 0 | Frontend check | High | None | PASS |
| TypeScript | `npm run typecheck` exit 0 | Frontend check | High | None | PASS |
| OpenAPI export | `backend/export_contract.py` exit 0 | Generated local API schema | High | None | PASS |
| Frontend API types | `npm run generate-api` exit 0 | `frontend/src/api/schema.d.ts` | High | Review diff for unintended generated changes | PASS |
| Production frontend build | Vite build exit 0; CityScene chunk 980.87 kB and main chunk 638.95 kB, with >500 kB warning | Build output | High | Chunk-splitting optimization can be considered separately | PASS |
| Clean-machine reproducibility | No clean environment or fresh dependency installation was performed | This local verification record | Medium | Repeat from lockfiles on a clean machine | PENDING |
| Scientific outcome buckets | Decimal symmetric ±0.01 boundaries; finite deltas classified exclusively; 10 independent groups produce 8 improved, 2 tied, 0 lower | `backend/app/evaluation.py`, `backend/tests/test_part15_evaluation.py`, regenerated evidence | High | Keep reporting synthetic scope | PASS |
| Part 15 evaluation | 10 groups, 6 ticks/group; 2,312.418 ms; zero all-roads-closed assignments | `docs/evidence/part15/scientific_evaluation.{json,csv,md}` | High | Synthetic bounded evidence only | PASS |
| Part 10 disposable acceptance | 17/17 checks passed in 11,981.008 ms; explicit test commander actions; restart persistence, blocked route, approved revision, arrival/completion and return-to-service covered | `backend/artifacts/part10-acceptance/acceptance-report.json` (local ignored output) | High | None | PASS |
| Part 14 RC1 disposable acceptance | 14/14 checks passed in 15,343.648 ms | `backend/artifacts/part14-rc1-acceptance/acceptance-report.json` (local ignored output) | High | None | PASS |
| Part 13 robustness benchmark | 11 conditions; 339.489 ms total; payload 264,817 bytes; two starting assignments; all roads closed yields zero reoptimized assignments; at this tick all 72 destinations unserved | Benchmark output; `backend/benchmark_robustness.py` | High | Synthetic condition only | PASS |
| Preflight and startup | Launcher started backend and frontend; readiness 3,212.4 ms / 592.3 ms; preflight passed all checks while services ran. `RESQ_DB_PATH` was unset, so the existing default `backend/data/resq.sqlite3` was opened and passed the launcher's read-only `quick_check`. | `scripts/start-resq-ai.ps1`, `scripts/demo-preflight.ps1` output | High | No visual/browser validation implied | PASS |
| Shutdown | Ctrl+C sent to the exact launcher session; its `finally` stopped tracked children; no listeners remained on 8000/5173. Existing default SQLite file was preserved and not deleted; this run did not confirm it was disposable. | Launcher session + listener inspection | Medium | Keep local DB; verify ownership before any future cleanup | PASS |
| Model/calibration/support integrity | SHA-256 matches model `9375c9f2bd919d5124f1320eab04b406c4bf2ae7e63c791fee713122ff843b73`, normalized metadata `7542b7d10be467ef560ec76bbe105ffc8001c063dfff177375cbef42cb0bf2d4`, calibrator `64d50451b051092b0652a774064349d936c30eae93ce9b73f3790e3a29687ec6`, support `f01bcc84be76cc94b2df955ba5c9a90881e9823454c7aaa6da675833dc5f26f3`; dataset SHA is `c560bdb345ad083f3f8e1d9d8a2d4928d2705bd7787f4e9640567a439040387d`; nested split report records 0 overlap and test exclusion | `backend/ml_artifacts/reliability_evaluation.json`, `model_metadata.json`; manifest validation | High | None | PASS |
| Same-ID epoch reset | Covered by backend regressions and full suite; test name includes durable agent reset epoch | `backend/tests/test_agents.py`, `backend/tests/test_missions.py`, `backend/tests/test_robustness.py` | High | None | PASS |
| Mission clock synchronization | Clock version/idempotency, paused state, route revision and epoch reset tests included in full suite | `backend/tests/test_missions.py` | High | None | PASS |
| All-roads-closed and approval | Rescue tests and both disposable acceptance workflows; zero assignments verified in benchmark and scientific evaluation | `backend/tests/test_rescue.py`, acceptance outputs | High | None | PASS |
| Release manifest | Focused disposable validation passed 11/11 cases: valid artifacts and JSON, exact source SHA, frontend asset hashes, no secret-like values or personal paths, missing dependencies/model/calibration/support/report, empty build, and a report/model hash mismatch. The generator now fails closed and cross-checks authoritative report checksums. The commit-bound manifest is generated and validated after the source commit; it remains ignored/outside the tracked source tree. | `scripts/test-release-manifest.ps1`, `scripts/write-release-manifest.ps1`, final ignored `artifacts/part16-release-manifest.json` | High | Record exact commit and hosted run in PR delivery report; do not embed self-referential SHA here | PASS |
| Repository hygiene | `.gitignore` covers environments, node_modules, local DBs, caches and artifacts; the two pre-existing baseline folders and local SQLite database were preserved; only the intended Part 16.1 source/docs files were staged after path review | `.gitignore`, inspected staged-path list | High | None | PASS |
| Documentation / claim review | All local Markdown links resolve; no personal machine paths/usernames found; browser status explicitly blocked | `docs/README.md`, final docs | Medium | Finish final diff audit | PASS |
| Browser visual walkthrough | Not attempted after URL-safety stop | This record; `FINAL_VISUAL_QA.md` | Medium | Requires independent URL-verifiable session | BLOCKED |
| CSS viewport sizes | 1366×768, 1440×900, 1920×1080 and narrow viewport not measured | `FINAL_VISUAL_QA.md` | Medium | Measure `innerWidth`/`innerHeight` in approved browser session | BLOCKED |
| Accessibility | Keyboard flow, focus, labels/roles, screen reader announcements and contrast not browser-verified | `FINAL_VISUAL_QA.md` | Medium | Complete independent accessibility review | BLOCKED |
| Reduced motion / low graphics / WebGL | No Part 16 browser inspection or context-loss test | `FINAL_VISUAL_QA.md` | Medium | Verify with approved browser helper | BLOCKED |
| Screenshot evidence | Existing Part 15 genuine gallery preserved; no Part 16 captures produced | `docs/VISUAL_EVIDENCE_GALLERY.md`, screenshot files | Medium | Add only authentic captures after authorized walkthrough | ACCEPTED LIMITATION |
| Offline isolation | Local inference and loopback demo verified; no OS firewall isolation test | `docs/OFFLINE_AUDIT.md`, preflight | Medium | Do not claim physical network isolation | ACCEPTED LIMITATION |
| Team live rehearsal | Automated workflows passed; no timed spoken rehearsal performed | `FINAL_DEMO_REHEARSAL.md` | Medium | Team must rehearse and fill presenter fields | PENDING |
| Submission details | Names, institution, mentor and registration fields remain placeholders; nothing submitted | `INNOTECH_SUBMISSION_KIT.md` | Medium | Team fills verified event information | PENDING |
| Hosted CI | Historical successful run 39050331892 on commit `f34c8ed3c8216deb8974aedcaee1199c1add9dea` passed both jobs. The final Part 16.1 PR-head run is checked separately after the source commit and its exact SHA, run URL and job conclusions are recorded in the PR delivery report. | [Historical successful run 39050331892](https://github.com/24f2003970/RESQ-AI/actions/runs/39050331892); current PR #16 delivery report | High | Keep PR open and unmerged; review the exact-head result in the PR | PASS |

## Executed commands

- `backend/.venv/Scripts/python.exe -m pytest --basetemp=.pytest-tmp-part16`
- `frontend/npm test -- --reporter=dot`
- `frontend/npm run lint`
- `frontend/npm run typecheck`
- `backend/.venv/Scripts/python.exe backend/export_contract.py`
- `frontend/npm run generate-api`
- `frontend/npm run build`
- `backend/.venv/Scripts/python.exe backend/demo_acceptance_part10.py --test-commander-actions`
- `backend/.venv/Scripts/python.exe backend/demo_acceptance_rc1.py`
- `backend/.venv/Scripts/python.exe backend/benchmark_robustness.py`
- `backend/.venv/Scripts/python.exe backend/run_part15_evaluation.py`
- `pwsh -NoProfile -File scripts/test-release-manifest.ps1` (11 disposable success/failure fixtures; source checkout artifacts were not renamed, removed or corrupted)
- `pwsh -NoProfile -File scripts/write-release-manifest.ps1` after the final commit, writing only the ignored `artifacts/part16-release-manifest.json`
- `scripts/start-resq-ai.ps1`, then `scripts/demo-preflight.ps1` while services were running, then Ctrl+C to the launcher.

The first preflight was run while services were stopped and returned expected API/frontend-unavailable failures. The launcher was then started, preflight was rerun and passed, and only that launcher session was stopped. No browser tool was used.

## Hosted results

PR #16: https://github.com/24f2003970/RESQ-AI/pull/16 (open and unmerged). Run 39050331892 is a historical successful run on `f34c8ed3c8216deb8974aedcaee1199c1add9dea`; it is not the Part 16.1 final-head check. The final source SHA and exact-head Actions result are reported in the PR delivery report after push. The PR's checks tab is authoritative for the newest head; keep the PR open and require both jobs to pass before review/merge.
