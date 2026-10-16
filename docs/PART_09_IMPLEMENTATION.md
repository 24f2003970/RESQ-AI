# Part 9 implementation

Part 9 improves the existing backend-driven Digital Twin presentation. It does not change flood calculations, mission commands, or the city dataset.

## Visual changes

- Buildings keep their backend footprint, location, floors and height. Rendering profiles vary wall, roof, trim, windows and entrances; low-rise homes receive a gable roof. Hospitals and shelters have distinct rooftop marks. Commercial/institutional rooftops include restrained equipment and parapets.
- Terrain is rendered with twice the grid subdivision in standard mode and bilinear samples from the existing elevation matrix. Height-based vertex tints add ground variation without changing scenario elevations.
- Flood rendering uses depth bands and opacity from the current positive depth cells. River banks follow the river segment coordinates. Road surface status colors, sidewalk/curb batches, occasional street lights, closure barriers, bridge decks, guardrails and supports use the existing road/bridge geometry.
- Trees and repeated architectural parts use instanced meshes with shared geometry/materials.
- Daylight, overcast and low-light presets change only render lighting. Camera presets focus the city, deepest currently wet cell, first modeled bridge, or selected mission. Camera transitions use easing while the user retains orbit/zoom control.
- Existing mission vehicles continue to sample the approved 3D route using authoritative traversed distance. The display does not advance a mission or move beyond the backend progress snapshot. Low-graphics mode remains available.

## Source-level geometry baseline

The fixture city has 72 buildings (350 total floors), 10 roads, 6 bridges, 2 green areas and 32 trees. The old terrain grid rendered 825 vertices and 1,536 triangles. Standard Part 9 terrain samples at twice the per-axis subdivision: 3,185 vertices and 6,144 triangles for the same grid. Low graphics retains the original 825-vertex grid. These are deterministic geometry counts, not GPU frame measurements.

The renderer batches repeating road pieces and street furniture, trees, facade details and bridge supports by geometry/material. Browser GPU draw calls, frame rate and scene load time could not be measured in this run; see [PART_09_VERIFICATION.md](PART_09_VERIFICATION.md).

## Scope limits

The synthetic city remains stylized and orthogonal. River stage and cell depth remain synthetic model outputs. Water shading does not simulate currents, waves or fluid interaction. The first bridge is used for the bridge camera preset because the UI currently has no bridge selection inspector. No external models or binary art assets were added.
