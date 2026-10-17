# Final visual QA checklist

## Observed in Part 15

- [x] Verified local app URL in Edge: `http://127.0.0.1:5173/`.
- [x] Captured the Command Center, flood scenario, proposal/routes, model reliability, agent trace, approved mission, and early en-route movement. See `VISUAL_EVIDENCE_GALLERY.md`.
- [x] The window was observed at 807×729 and maximized to 1536×912 screenshot dimensions. These are window-image dimensions; exact CSS viewport values were not available from the supported capture tool.
- [x] App data came from scenario `scenario-riverside-2026`, epoch 0, using the displayed 2026 flood-demo scenario. The screenshot values matched real local backend responses.

## Not verified in Part 15

- [ ] Exact desktop CSS viewport sizes 1366×768, 1440×900, and 1920×1080. The supported computer-use helper did not provide a safe, independently verified viewport setter; no claim is made for these dimensions.
- [ ] Robustness Lab, Judge Mode, and Demo B all-roads-closed screenshots saved to this gallery.
- [ ] Fresh screenshots of blocked mission, approved route revision, arrival, explicit completion, and resource restoration.
- [ ] Reduced-motion preference behavior.
- [ ] WebGL context-loss and recovery behavior.
- [ ] Full accessibility audit, including keyboard-only operation and assistive-technology labels.

## Manual follow-up

1. Start with the disposable local demo instructions in `LOCAL_DEMO_QUICKSTART.md`; record the app version/commit and browser version.
2. Set each target viewport in a supported browser-resize tool and record the CSS viewport separately from the outer window size.
3. At each size, inspect 3D prominence, navigation, proposal approval controls, mission operations, chart/table legibility, loading overlays, and Judge Mode. Capture actual screenshots without altering application state to create a desired outcome.
4. Follow `PART_08_2_BROWSER_WALKTHROUGH.md` and `PART_14_VERIFICATION.md` for dispatch, turns, closure, route revision, arrival, completion, and return-to-service. Record scenario ID, epoch, route, mission state, and backend response for each capture.
5. Use the UI's reduced-motion and low-graphics controls where available. Restore original preference settings at the end.
6. Test context loss only when the supported browser/helper offers a safe recovery test; otherwise leave it pending. Do not use undocumented browser scripting or report a simulated screenshot as proof.
