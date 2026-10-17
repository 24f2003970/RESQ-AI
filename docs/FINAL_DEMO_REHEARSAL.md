# Final demo rehearsal runbook

This is a five-minute sequence with a separately prepared Demo A and Demo B. Start from the supported disposable setup in `LOCAL_DEMO_QUICKSTART.md`. Run preflight before opening the presentation browser; do not reset or delete an existing user database to prepare the demo.

## Setup before judges arrive

1. Use a clean disposable demo database and keep the operational database untouched.
2. Run `scripts/demo-preflight.ps1`; verify backend health, model readiness, API availability, and frontend HTTP response. The preflight checks loopback endpoints; it does not perform browser visual QA.
3. Prepare Demo A with seed 2026, mild preset, rain 30 mm/h, river 0.6 m, drainage 0.2, and six five-minute ticks. Confirm the current backend version and scenario epoch in the UI.
4. Prepare Demo B separately with all ten modeled corridors closed; verify zero assignments and unreachable reasons.
5. Have a genuine screenshot from the relevant prior state ready in `docs/evidence/part15/screenshots/` and label it as saved evidence if used as a fallback.
6. **Before live presentation:** visually verify low-graphics mode and Model Intelligence fallback tables in a URL-verified browser session. Part 16 did not perform this browser check.

## Five-minute cue sheet

| Time | Action | Expected state | Fallback |
|---|---|---|---|
| 0:00–0:30 | Open Command Center | 3D fictional city; local status | Use baseline screenshot if graphics are unavailable |
| 0:30–1:15 | Show prepared Demo A | Six ticks; physical exposure in current backend state | Narrate observed values; do not force stored historic numbers |
| 1:15–2:00 | Show Model Intelligence and Decision Explorer | Synthetic future estimate and six deterministic completed agents | Show saved calibration plot and trace capture, labeled as saved evidence |
| 2:00–3:15 | Review proposal; explicitly approve and dispatch | Only supported current assignments are approved; mission clock advances | If current proposal differs, explain actual result; no synthetic approval claim |
| 3:15–4:10 | Close a required edge, request route, reopen, review revision | Blocked while closed if a traversed route edge is closed; no-route may be the correct answer; revision follows reopening and requires human approval | Stay on blocked status if the current router finds no path |
| 4:10–5:00 | Show arrival/completion evidence and Demo B | Completion and resource restoration are explicit; all-roads-closed shows zero assignments | Use persisted acceptance evidence with scenario/epoch attribution |

The five-minute narration is in `INNOTECH_FINAL_PITCH.md`. Target setup should be completed before the clock starts. The route revision in the verified Demo A occurred after reopening the relevant road; no closed-road detour is promised.

## Rehearsal record

Fill in after the team performs a timed spoken rehearsal:

| Date/time | Build commit | Presenter(s) | Total spoken time | Slowest stage | Deviations / recovery |
|---|---|---|---|---|---|
| Pending live team rehearsal | — | Team to complete | Pending | Pending | Not claimed as rehearsed |

Automated disposable acceptance proves backend actions, not speaking pace or live-demo readiness. Record the actual rehearsal before submission.
