# Visual evidence gallery

These are untouched JPEG captures returned by the visible local Edge window while the RESQ-AI app was running at `http://127.0.0.1:5173/`. The launcher used a unique disposable SQLite database. Images were not generated, composited, or retouched. The captured window included Edge chrome and a video-downloader extension overlay in the lower-left corner; this is documented rather than edited out.

Capture metadata available from the computer-use helper identified the Edge window and full window image dimensions. The app was initially captured in an 807×729 window, then maximized to 1536×912. These are full-window screenshot dimensions, not verified CSS viewport dimensions. Scenario captures are from `scenario-riverside-2026`, epoch 0. The flood demo used seed 2026, rain 30 mm/h, river stage 0.6 m, drainage 20%, six five-minute steps, backend version 8, 10 physically impacted buildings, and maximum modeled cell depth about 0.16 m. Values shown are the actual local application response.

## Captures

| Image | Observed content |
|---|---|
| `evidence/part15/screenshots/command-center-baseline-1536x912.jpg` | Command Center and 3D Riverside baseline |
| `evidence/part15/screenshots/command-center-baseline-807x729.jpg` | Smaller-window baseline layout |
| `evidence/part15/screenshots/scenario-lab-flood-demo-a-seed2026-epoch0-tick6-1536x912.jpg` | Scenario Lab after six real simulation steps |
| `evidence/part15/screenshots/command-center-flood-proposal-seed2026-epoch0-tick6-1536x912.jpg` | Physical flood state and proposal view |
| `evidence/part15/screenshots/proposal-routes-and-resources-seed2026-epoch0-tick6-1536x912.jpg` | Proposed routes and assignment details |
| `evidence/part15/screenshots/model-intelligence-synthetic-heldout-1536x912.jpg` | Local model synthetic held-out metrics and support |
| `evidence/part15/screenshots/model-reliability-and-support-1536x912.jpg` | Reliability and training-support UI |
| `evidence/part15/screenshots/agent-decision-trace-six-complete-1536x912.jpg` | Six completed deterministic agent records |
| `evidence/part15/screenshots/approved-ready-mission-unit1-reserved-epoch0-1536x912.jpg` | Four explicitly approved simulated missions; unit 1 reserved |
| `evidence/part15/screenshots/mission-en-route-progress-13m9-seed2026-epoch0-1536x912.jpg` | Persisted en-route state after a 10-second clock action; 13.9 m authoritative route progress |

The mission route shown in the approval capture was a stored 490 m synthetic route for unit 1 to Northbank 25. The movement capture reports 13.9 m traveled, about 476.1 m remaining, and a 10-second mission clock. It is a genuine early-progress state, not a completion claim.

## Capture coverage limits

This Part 15 gallery does not contain separate screenshots of a blocked mission, route revision approval, arrival/completion, resource restoration, Robustness Lab, Judge Mode, or Demo B all-roads-closed. Those behaviors were covered by the prior Part 14 browser and acceptance record (see `PART_14_VERIFICATION.md`), but that record's screenshots were not saved as repository artifacts. Do not treat the Part 15 captures as evidence for those absent screens. For presentation, capture them from the app using `docs/FINAL_VISUAL_QA.md` and the Part 14 walkthrough; preserve each actual state and include its scenario/epoch label.

The separate `evidence/part15/calibration_reliability.svg` is an editable-by-code plot from saved grouped evaluation bins, not a screenshot.
