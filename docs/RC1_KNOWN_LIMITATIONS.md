# RC1 known limitations

- All city geometry, flood forcings, training labels, occupants, priorities, routes and mission outcomes are synthetic. This prototype is not certified for emergency operations.
- The local model predicts synthetic future exposure; its score is not a real-world flood probability. Physical current exposure remains simulator output.
- The graph has 10 generated corridors and 6 generated bridges. Boat routing, surveyed access, traffic, external data and field safety are unsupported.
- A route revision can be longer than the original; Demo A's measured alternative is 1053.6 m versus an original 606.0 m route. If no safe supported path exists, the system leaves the mission blocked.
- Mission arrival and explicit completion do not prove occupant evacuation or lives saved. Units are restored only by an explicit return-to-service action at their saved position.
- CityScene's production chunk is approximately 981 kB minified and triggers Vite's existing chunk warning. Route-level lazy loading reduced the initial app chunk; no optimized geometry/material overhaul was justified by the collected short samples.
- Browser inspection covered Command Center, Scenario Lab, Model Intelligence Lab, AI Decision Explorer, Decision Robustness Lab and Judge Mode. Mission movement across corners, browser-side closure/reroute/arrival/restore, Demo B UI, context-loss recovery, browser build string, page-load timing and browser memory remain unverified.
- The inspected browser session emitted repeated React “Maximum update depth exceeded” console errors while Command Center was active. The walkthrough did not isolate their source; review before a polished RC1 demo.
- GPU samples used WebGL 2 on Intel UHD Graphics even though an RTX 4050 was present. The `?perf=1` development sampler forces continuous frames and reports a derived median frame rate; it is not a guaranteed FPS. Matched, repeatable movement/camera/idle benchmarks remain outstanding.
- The app binds to loopback by default and has no external inference integration. This is not a formal network-isolation or penetration test.
