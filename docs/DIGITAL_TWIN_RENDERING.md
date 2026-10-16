# Digital Twin rendering contract

## Coordinates and authority

The scene maps backend coordinates in metres to Three.js `(x, y, z) = (east, elevation, -north)`. The 20 m terrain/depth grid shares the backend city's grid origin. Building locations, footprints and heights, road corridors, bridge positions/elevations, river endpoints/stage, flood depth and mission route geometry come from the backend response.

Styling is derived from building use/floors and current impact records. It must not move or resize the backend-defined building body. Terrain subdivision only inserts display vertices interpolated from the same elevation grid. A visual preset must not mutate scenario state or force parameters.

## Layers

- **Buildings:** shared instanced walls, plinths, roofs, windows, entrances and selected facade accents; hospitals and shelters use distinct rooftop marks.
- **Terrain / greenery:** elevation-tinted terrain, park meshes and instanced trees.
- **Infrastructure:** road surface and markings, sidewalks/curbs, status colors, closure barricades, bridge deck, guardrails and supports.
- **Flood:** positive backend cell depths only, using shallow/moderate/deep/very-deep color and alpha bands.
- **Predicted exposure:** separate frontend layer sourced from the existing future-exposure prediction response; it does not recolor the physical flood surface.
- **Units/routes:** existing resource and mission data; ready routes are dimmer than active mission routes, blocked missions are red, selected missions receive stronger emphasis.

## Water and bridges

Each displayed flood cell uses its backend depth and terrain sample to set its water surface. Depth color and opacity are render cues, not additional hydrology. There is no animated current or flow field. The display threshold only omits near-zero cells; it does not change the backend flood extent. Bridge geometry retains the backend bridge elevation and remains separately visible above the water where the modeled deck is higher.

## Missions and vehicles

Vehicles sample the approved `polyline_xyz` route at the reported mission distance. When a newer authoritative snapshot arrives, the visual can ease between the previous and new distance but cannot exceed the new value. Route revisions snap to the revised route's persisted mission position. Blocked, arrived and completed missions stop movement. Selecting an en-route mission lets the camera follow its latest authoritative position without changing its progress. Arrival is not completion and does not restore a resource.

## Reduced graphics and camera

Low graphics disables shadow maps, fixes device pixel ratio to 1, uses base terrain grid spacing, reduces facade windows and tree density, removes streetlights and lowers water material complexity. Camera controls include overview, flood hotspot, bridge crossing, rescue operation, selected building, zoom, and accessible inventory fallback. Lighting options affect only background/light values.

Reduced-motion preference makes camera presets immediate and disables in-between vehicle motion. The canvas listens for WebGL context loss/restoration, allows the browser restoration event, and displays a status message while graphics are paused. The current render-error fallback is a selectable building inventory wrapped in a React render error boundary. Actual GPU recovery still requires manual validation on the presentation laptop.
