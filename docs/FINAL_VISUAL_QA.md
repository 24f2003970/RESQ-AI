# Final visual QA checklist

**Part 16 status: BLOCKED.** The computer-use helper stopped because it could not verify the current Edge URL. Browser tools were not retried or bypassed. This is a tool safety restriction, not an application defect. All browser-measured items below remain **BLOCKED** until a separately authorized, URL-verifiable session is available.

## Previous genuine Part 15 capture

The gallery contains ten unaltered screenshots from the URL-verified local app. The recorded dimensions (807×729 and 1536×912) are outer-window images, not measured CSS viewport sizes. See `VISUAL_EVIDENCE_GALLERY.md` for scenario/epoch and capture limitations.

## Part 16 target matrix

| CSS viewport | Actual `innerWidth × innerHeight` | Command Center | Mission controls | Judge / analytical labs | Tables / overflow | Status |
|---|---|---|---|---|---|---|
| 1366×768 | Not measured | Not checked | Not checked | Not checked | Not checked | BLOCKED |
| 1440×900 | Not measured | Not checked | Not checked | Not checked | Not checked | BLOCKED |
| 1920×1080 | Not measured | Not checked | Not checked | Not checked | Not checked | BLOCKED |
| Narrow responsive size | Not measured | Not checked | Not checked | Not checked | Not checked | BLOCKED |

If no permitted helper can set and independently measure CSS size, retain these pending statuses and include observed outer-window dimensions separately.

## Accessibility and graphics

- **BLOCKED:** Keyboard-only path, focus visibility, labels/roles/announcements, and contrast need browser verification.
- **BLOCKED:** Reduced-motion behavior and low-graphics mode need a real browser session.
- **BLOCKED:** WebGL fallback and context-loss behavior need a real browser session.
- **BLOCKED:** Part 16 React render stability walkthrough was not performed; prior bounded walkthroughs did not reproduce the historical error.
- **PENDING:** Record whether the known upstream `THREE.Clock` deprecation warning remains in the next URL-verified browser session.

Record actual outcomes in `PART_16_VERIFICATION.md`. Do not infer browser accessibility from a unit test.
