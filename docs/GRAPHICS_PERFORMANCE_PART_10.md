# Graphics Performance — Part 10

## Source and build evidence

Fresh Part 10 production build (Vite 8.3.4): initial JavaScript bundle **708.16 kB minified / 210.06 kB gzip**; lazy CityScene chunk **978.25 kB / 261.82 kB gzip**; CSS **61.45 kB / 14.16 kB gzip**. The build retains Vite's warning for a chunk above 500 kB. No warning threshold change or bundle reshuffle was made. The Part 9 CityScene bundle measurement is unchanged.

## Browser measurements

Browser-based initial readiness, lazy scene load duration, draw calls, triangle count, idle/flood/vehicle FPS, low-graphics FPS, memory pressure and WebGL context-loss recovery require a real browser inspection session. The earlier computer-use helper was unable to verify the active URL. Unless a fresh session succeeds and its browser/viewport are recorded, all those measurements remain **PENDING**. Unit tests and builds do not establish visual fidelity or FPS.

## Manual walkthrough checklist

Record browser name/version, viewport dimensions, OS/GPU when available and whether reduced-motion/low-graphics is enabled. Then verify:

- [ ] Command Center renders; buildings, roads and six bridges are visible.
- [ ] Seeded flood progression visibly changes water and affected assets.
- [ ] Camera presets and daylight, overcast and low-light views are readable.
- [ ] Current physical exposure is distinct from future ML exposure.
- [ ] Decision Explorer shows persisted traces; Guided Demo performs backend actions.
- [ ] Rescue proposal requires human approval before a unit is reserved.
- [ ] Dispatch follows the approved road polyline through at least two turns and a bridge where route geometry permits.
- [ ] Closing a route-relevant road visibly blocks the mission; revised routes require commander approval.
- [ ] Arrival, explicit completion and return-to-service update the mission and resource panels.
- [ ] A/B switching keeps camera continuity; reduced motion and low graphics work.
- [ ] Narrow layout is usable; a rendering failure exposes a useful fallback.
- [ ] Refresh and backend restart preserve scenario and mission state.

Capture screenshots only when a real browser session is available. No screenshots or GPU timings are claimed by this report unless attached with actual browser and viewport details.
