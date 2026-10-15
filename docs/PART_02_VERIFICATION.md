# Part 2 verification record

Verified on Windows on 15 October 2026 using Python 3.12.5, Node.js 24.12.0, and npm 11.6.2. This record describes checks actually run on the Part 2 feature branch, not future acceptance claims.

## Automated checks

| Check | Result |
|---|---|
| Backend dependency installation | completed in `backend/.venv` from pinned versions |
| Python imports and `pip check` | successful; no broken requirements |
| `python -m pytest -q` | **10 passed**: deterministic seeds, inventory/bounds, relationships, invalid dimensions, IDs, unknown fields, non-finite values, API/detail consistency, 404 and local CORS |
| Frontend dependency installation | completed; exact versions in package.json and package-lock.json |
| `npm run typecheck` | passed with strict TypeScript |
| `npm run lint` | passed |
| `npm test` | **6 passed**: runtime contract rejection, coordinate transform, API-backed inspection, layers/navigation/future states, failed connection/retry, malformed payload |
| `npm run build` | passed; emitted local production assets |
| `npm audit` | **0 vulnerabilities reported** at the time of the check |
| `git diff --check` | passed |

Frontend component tests mock the WebGL component because jsdom does not render WebGL. Actual rendering and canvas interaction were checked separately in the browser. One test was updated to wait for the lazy-loaded scene rather than assume synchronous mounting; the final suite passed.

## Browser and integration checks

- Opened the local development app and the production build with the real FastAPI service running.
- Confirmed the city rendered from the local service: 72 buildings, four districts, ten roads, six bridges, one hospital, one shelter, two parks, and five response units.
- Selected a mesh in the 3D canvas; the inspector loaded the matching building ID, dimensions, district, and occupants from the building endpoint.
- Exercised camera focus, reset, orbit, zoom, and keyboard pan. Zoom changed the rendered scene; camera controls remained usable with the seed city.
- Switched to the explicit building inventory, selected a record, and verified the matching API-backed inspector; returned to 3D.
- Toggled the lower-graphics mode and returned to standard mode.
- Verified Command Center, Digital Twin Studio, and the three future routes through browser interaction and component tests.
- Checked the 1366-pixel laptop layout and 390-pixel mobile layout. Mobile navigation worked; the mobile document had no horizontal overflow. Closed mobile navigation is removed from keyboard/accessibility navigation.
- Stopped the actual backend process, refreshed, and observed the offline status plus stale-snapshot warning. Restarted the backend and reconnected successfully.
- Exported a JSON snapshot through the UI download control.
- Captured command-center, mobile, and offline-state screenshots during the checks.
- Inspected production console logs: no application errors were observed. Three.js/R3F emits an upstream `THREE.Clock` deprecation warning. The explicit PCF shadow configuration avoids the removed soft-shadow fallback warning in the final build.

## Offline resource review

The frontend API client fetches only relative `/api/v1/` URLs. Fonts are bundled from local font packages. The renderer uses generated geometry, materials, and lights without remote model, tile, texture, or font loaders. Production page asset references are local `/assets/` files. The backend makes no outbound requests; its optional CDN-based API documentation UIs are disabled. No external AI API, key, analytics, or hosted inference dependency was introduced.

This was a source/asset review and local runtime check. A full browser network trace and operating-system network-disconnection test were not performed. Dependency installation still requires internet access unless packages have been cached in advance.

## Known limitations

- The default city is flat and fictional; it is not a calibrated real-world disaster model.
- Road corridors have endpoint records but are not yet split into a routable intersection graph.
- No scenario mutation, SQLite persistence, flood progression, model, rescue optimizer, or agents are implemented in this part.
- Vite reports large chunks: approximately 564 kB of application code and 960 kB of separately loaded scene code before gzip (about 176 kB and 256 kB gzip). Further tuning can follow profiling on the final demo laptop.
- The backend test client produces an upstream Starlette/httpx deprecation warning; tests pass.
- The automatic WebGL-error fallback was not tested by forcing GPU failure. The explicit inventory mode was exercised successfully.
- No quantitative FPS or memory benchmark is claimed. These checks establish functional interaction on this environment, not performance on every GPU.
