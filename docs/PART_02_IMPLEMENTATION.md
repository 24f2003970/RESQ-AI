# Part 2 — Full-stack foundation

## Implemented boundary

The service generates one immutable baseline snapshot for the configured fictional city seed. The React application loads it through the local API and renders it in React Three Fiber. Inventory, counts, selection IDs, and inspector data originate in Python. There are no hardcoded runtime city fixtures in the frontend. Simulation, SQLite persistence, WebSocket events, model training, risk colors, road closures, rescue routes, and moving missions remain future implementation work.

The Part 1 architecture remains the overall design. Part 2 exposes read-only `city/state` and `scenarios/default` routes rather than implementing the planned scenario mutation API prematurely. The default seed is 2026; set the `RESQ_CITY_SEED` environment variable before starting the backend to use another integer. Restarting with the same seed and generator version yields the same city.

## Local API

| Method and path | Response |
|---|---|
| `GET /api/v1/health` | service name, version, local mode, `ok` status |
| `GET /api/v1/scenarios/default` | scenario ID/name, city ID, baseline status, state version, simulated time |
| `GET /api/v1/city/state` | complete city snapshot and all typed entity arrays |
| `GET /api/v1/city/buildings/{id}` | one authoritative building record; useful JSON error on 404 |
| `GET /openapi.json` | local OpenAPI contract |

Requests receive an `X-Request-ID`; request logs include method, path, status, duration, and request ID as JSON. Unexpected failures produce a generic JSON error without disclosing the exception in the response. CORS permits the documented localhost/127.0.0.1 development and preview origins, not wildcard origins. Swagger/Redoc UIs are disabled because their default assets require a CDN; the schema remains local.

The current state is an in-memory cached baseline. It is not persistent operational state. SQLite and transactional updates will be introduced when scenarios become mutable.

## Contracts and coordinates

Pydantic models are the contract source. `backend/export_contract.py` exports OpenAPI, the CityState JSON Schema, and a test-only seed fixture. `npm run generate-api` derives TypeScript declarations using openapi-typescript. The frontend uses the generated component types and AJV 2020 to validate the complete city payload at runtime. Missing required fields, incorrect types, invalid dimensions, empty city data, network timeouts, and bad HTTP responses are visible errors.

- Backend position: `x_m` east, `y_m` north, `elevation_m` up, all meters.
- Scene position: `[x_m, elevation_m, -y_m]`; `scene/coordinates.ts` centralizes this transform.
- Height/width/depth and road length are meters; building occupants, beds, shelter places, and unit capacity are counts.
- IDs are stable for the seed and generator version. Facilities reference buildings; bridges reference road corridors; roads reference catalogued endpoint nodes; buildings reference districts; the scenario references its city.
- Pydantic rejects unknown properties, non-finite positions, negative dimensions, duplicate IDs, and broken entity references. JSON uses snake_case and numbers, with no date or coordinate conversion in serialization.
- The road corridors cross visually. Their endpoints are catalogued, but a routable graph split at every intersection is intentionally deferred to the routing phase.

The city is a 660 m × 500 m flat fictional block plan with a canal at northing zero. Seeded variation affects building dimensions, heights, occupancy, and park trees. Buildings are not observed real structures. River surface elevation is an aesthetic baseline datum, not simulated flood depth. District extents and the seed inventory have no real geographic meaning.

## Rendering and controls

Walls, roofs, rooftop equipment, facade windows, road surfaces, and lane markings reuse instanced geometry/materials. The city is rendered on demand, with a device pixel ratio capped at 1.5. Low graphics caps it at 1 and disables shadows. Tree geometry is small and procedural; no external 3D assets, map tiles, textures, or fonts are fetched at runtime. Manrope and IBM Plex Mono are bundled locally with their font packages.

The isometric camera fits the viewport. Left-drag orbits; the wheel or +/- buttons zoom; right-drag and arrow keys (while the canvas has focus) pan. Reset restores the fitted view; focus centers the selected building. Selecting an instanced mesh uses its stable ID, fetches the building endpoint, and shows matching data in the inspector. Facility rows and the building inventory provide alternative selection paths.

The layer panel toggles buildings, park greenery, facility rooftop marks, district boundaries, and unit markers. Future flood/risk/closure/route/unit-motion layers can consume extended scenario state through the same ID contract; no fake future state is rendered now.

## Screens and connection behavior

- **Command Center:** backend inventory, city viewport, inspector, facilities, static baseline infrastructure/resource status, scenario metadata preview, honest AI placeholder.
- **Digital Twin Studio:** expanded viewport with the same city, selection, layers, and controls.
- **Scenario Lab:** honest development state, proposed Part 3.
- **Model Intelligence Lab:** honest development state, proposed Part 4.
- **AI Decision Explorer:** honest development state, proposed Parts 5–7.

Future part numbers are provisional and do not authorize implementation. Part 2 uses the user's exact `feature/part-02-fullstack-foundation` branch name as an exception to the shorter `feat/` convention in the team workflow.

Initial load waits for both city and health responses. Failed loads show a retry action. Health is checked every 15 seconds. A lost connection marks the UI offline and labels any retained city as a stale snapshot; reconnection requires an explicit refresh so the old snapshot is never relabeled as current without reloading. The snapshot export contains exactly the loaded backend data.

## Limitations

This is a baseline Digital Twin foundation, not an evolving disaster engine yet. The backend has no scenario mutation, storage, forecasting, risk outputs, optimizer, or agents. Vehicles are standby base markers. Facility capacity and occupancy are seeded fictional values. A powerful GPU is not required, but WebGL support is; an explicit inventory mode and an error-boundary fallback support inspection if the renderer fails. The Three.js scene chunk is larger than ordinary UI code and is loaded separately. Frame rate and GPU compatibility must still be assessed on the team's final demo laptop.

No internet-disconnection toggle is required: application resources are served from loopback. Installation and dependency fetching need internet; running the installed app needs both local processes but no external service. Do not treat a page already cached in the browser as proof of an independently installed offline environment.
