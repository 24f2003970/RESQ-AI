# RESQ-AI visual evidence gallery

## Part 15 captures

These are untouched JPEG captures returned by the visible local Edge window while RESQ-AI was running. The app used a unique disposable SQLite database. Images were not generated, composited, or retouched. The captured window included Edge chrome and a video-downloader extension overlay in the lower-left corner; it remains visible in the original files.

The capture metadata identified the Edge window and full-window image dimensions: 807×729 initially, then 1536×912 maximized. These are outer-window screenshot dimensions, not measured CSS viewport dimensions. Captures show `scenario-riverside-2026`, epoch 0. The flood demo used seed 2026, rain 30 mm/h, river stage 0.6 m, drainage 20%, six five-minute steps, backend version 8, 10 physically impacted buildings, and maximum modeled cell depth about 0.16 m. These values came from the observed local application response at capture time.

| Image | Observed content |
|---|---|
| `evidence/part15/screenshots/command-center-baseline-1536x912.jpg` | Command Center and 3D Riverside baseline |
| `evidence/part15/screenshots/command-center-baseline-807x729.jpg` | Smaller-window baseline layout |
| `evidence/part15/screenshots/scenario-lab-flood-demo-a-seed2026-epoch0-tick6-1536x912.jpg` | Scenario Lab after six simulation steps |
| `evidence/part15/screenshots/command-center-flood-proposal-seed2026-epoch0-tick6-1536x912.jpg` | Physical flood state and proposal view |
| `evidence/part15/screenshots/proposal-routes-and-resources-seed2026-epoch0-tick6-1536x912.jpg` | Proposed routes and assignment details |
| `evidence/part15/screenshots/model-intelligence-synthetic-heldout-1536x912.jpg` | Local model synthetic held-out metrics and support |
| `evidence/part15/screenshots/model-reliability-and-support-1536x912.jpg` | Reliability and training-support UI |
| `evidence/part15/screenshots/agent-decision-trace-six-complete-1536x912.jpg` | Six completed deterministic agent records |
| `evidence/part15/screenshots/approved-ready-mission-unit1-reserved-epoch0-1536x912.jpg` | Four explicitly approved simulated missions; unit 1 reserved |
| `evidence/part15/screenshots/mission-en-route-progress-13m9-seed2026-epoch0-1536x912.jpg` | Persisted en-route state after a 10-second clock action; 13.9 m authoritative route progress |

The mission route shown in the approval capture was a stored 490 m synthetic route for unit 1 to Northbank 25. The movement capture reports 13.9 m traveled, about 476.1 m remaining, and a 10-second mission clock. It is a genuine early-progress state, not a completion claim. The separate `evidence/part15/calibration_reliability.svg` is generated from saved grouped evaluation bins; it is a plot, not a screenshot.

## Coverage limits and Part 16 status

The Part 15 gallery does not contain separate captures of a blocked mission, route revision approval, arrival/completion, resource restoration, Robustness Lab, Judge Mode, or Demo B all-roads-closed. Part 14 acceptance records cover some of those interactions, but those records have no saved screenshot artifacts. Do not treat the Part 15 captures as evidence for absent screens.

No Part 16 captures were made. The browser helper stopped because it could not verify the active Edge URL. Per the recovery instruction, no browser operation was retried or routed around. The exact Part 16 viewport, accessibility, reduced-motion, low-graphics and WebGL checks remain BLOCKED in `FINAL_VISUAL_QA.md`; this tool safety restriction is not evidence of an app defect.

No generated or composited image is accepted as evidence of the live application. For offline presentation, label saved screenshots as prior evidence and include their scenario/epoch context. Add new captures only after an authorized, URL-verified browser session and pair mission images with backend/acceptance evidence.
