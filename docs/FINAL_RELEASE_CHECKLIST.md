# Final release checklist

This is a **candidate handoff checklist**, not authorization to publish a production release. PR #16 must be reviewed and merged by the repository owner before a release decision. Do not publish, deploy, change repository visibility, or submit to Innotech from this workflow.

Statuses and evidence are maintained in [Part 16 verification](PART_16_VERIFICATION.md). Status terms: **PASS**, **FAIL**, **PENDING**, **BLOCKED**, **ACCEPTED LIMITATION**.

| Gate | Required evidence | Current status | Next action |
|---|---|---|---|
| Backend and frontend suites | Full Pytest and Vitest | PASS | Review upstream warning; no local failures |
| Lint, typecheck, API contract/types, build | All commands succeed | PASS | Address large chunks in later optimization work |
| Model and calibration artifacts | Cross-checked hashes, metadata, validated manifest on source commit | PASS | Regenerate manifest after final docs commit |
| Scientific evidence | Exclusive buckets and regenerated 10-group JSON/CSV/MD | PASS | Preserve synthetic caveat |
| Human approval and mission lifecycle | Part 10/14 disposable acceptance and regressions | PASS | Review acceptance reports |
| Demo A and Demo B | 14 RC1 checks, benchmark and all-roads-closed zero assignment | PASS | Run live rehearsal before judging |
| Startup, preflight, shutdown | Launcher and preflight pass; owned process stopped | PASS | Keep user DB untouched |
| Browser visual QA | URL-verified local walkthrough | BLOCKED | Do not bypass; obtain a separately authorized verifiable browser session |
| Viewports, accessibility, graphics | Measured CSS dimensions, keyboard/accessibility, reduced motion, low graphics, WebGL | BLOCKED | Complete independently when browser helper permits |
| Offline isolation | OS-level network isolation | ACCEPTED LIMITATION | No firewall isolation claim |
| Screenshot evidence | Genuine captures for final candidate | ACCEPTED LIMITATION | Part 15 evidence only; no Part 16 screenshots |
| Live spoken rehearsal | Timed team rehearsal | PENDING | Team fills rehearsal record |
| Submission details | Verified names, institution and event registration | PENDING | Team completes placeholders |
| Repository hygiene | Exact staging review; no envs, DBs, caches or baseline folders | PENDING | Complete before commit |
| Hosted CI | Runs 39049846395 and 39049998316 both passed backend and frontend on their recorded commits | PASS | Confirm newest PR run; keep PR open/unmerged |

The candidate is **not fully visually validated**. The browser safety stop is not evidence of an application defect. No tag, GitHub Release, deployment, or Innotech submission is part of this handoff.
