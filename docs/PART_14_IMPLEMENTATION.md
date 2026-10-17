# Part 14 — RC1 implementation

Part 14 is a release-readiness slice, not a new intelligence feature. It records repeatable synthetic Demo A and Demo B cases, adds a disposable end-to-end acceptance runner, improves no-route explanations, corrects mission resource-release wording, and defers secondary workspaces into route-level chunks.

## Demo and acceptance

`backend/demo_acceptance_rc1.py` runs the real FastAPI services with a temporary SQLite database. Demo A covers the local model, event trace, versioned rescue plan, explicit approval and dispatch, authoritative movement, an infrastructure closure, a feasible alternate route, version-checked route approval, arrival, explicit completion and explicit return-to-service. Demo B uses the same seed and forcing in a separate scenario, closes every generated road, and verifies zero assignments and zero mission rows. The runner writes JSON and Markdown reports to its ignored `backend/artifacts/part14-rc1-acceptance/` output folder by default. It creates/removes only a separate temporary operational SQLite database.

The UI groups unreachable destinations under a concise explanation and gives a small number of concrete route reasons on demand. Existing records remain historical; approved routes and missions are never edited by a screenshot or by this acceptance script. Resource text now explains that a commander can return a completed unit to service explicitly and that arrival/completion alone do not release it.

## Measured optimization

The baseline build before Part 14 route deferral had a 761.99 kB minified primary application chunk (223.60 kB gzip). Lazy loading Scenario Lab, Guided Demo, Model Intelligence, Judge Mode and Decision Robustness reduced the primary chunk to 636.49 kB (190.23 kB gzip), a reduction of 125.50 kB minified / 33.36 kB gzip. The Command Center remains eager; its 3D scene was already lazy. The 3D scene chunk remains approximately 980.87 kB minified and still triggers Vite's existing chunk warning. The build threshold was not changed.

The browser-only `?perf=1` instrumentation exposes a five-second rolling sample through `window.__RESQ_SCENE_METRICS__` in development. It reports frame intervals, renderer draw calls/triangles, geometry/texture counts, canvas size, WebGL strings and graphics mode. The build-time `import.meta.env.DEV` guard prevents activation in production. The probe source remains in the lazy scene chunk, so the code is not described as absent from the bundle. It is opt-in and writes no network telemetry. The measured results and environment are in `GPU_PERFORMANCE_RC1.md`; browser-visible GPU counters can be unavailable when a driver masks WebGL renderer information.

## Unchanged safeguards

- Human approval is required before a proposal creates ready missions; dispatch is a separate explicit action.
- Mission positions advance only from the backend's persisted route and operational clock.
- Infrastructure closures are not relaxed for acceptance. Demo A uses a genuinely supported replacement route; Demo B asserts the correct refusal.
- Arrival is not represented as evacuation, lives saved or real rescue completion.
- No external model/API, dispatch integration, live data or real-city routing is introduced.

See `PART_14_VERIFICATION.md` for the run record and `RC1_KNOWN_LIMITATIONS.md` for remaining gaps.
