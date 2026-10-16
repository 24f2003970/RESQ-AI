# UI / UX Specification

## Visual direction

**70% realistic disaster visualization and 30% futuristic command-center UI.** The city should read as a plausible, stylized emergency map with legible infrastructure. The surrounding application uses deep navy, charcoal, graphite, muted slate, restrained cyan, clean typography, and limited motion. Avoid cartoon proportions, excessive glow, dense glass panels, and metrics without backend evidence.

Use a default isometric camera, with orbit, zoom, pan, and object inspection. Buildings vary by district and height; hospitals, shelters, roads, bridges, river, terrain, and response vehicles have distinct shapes. The city is an evolving Digital Twin only when its geometry reflects the same backend IDs and states as the simulation.

The Digital Twin includes camera presets for city overview, flood hotspot, bridge crossing and selected rescue operation; a lighting selector offers daylight, overcast and low-light rendering. These presets are presentation controls and do not change scenario inputs. Low-graphics mode is available alongside the viewport and reduces detail and shadows for lower-power laptops.

### Color and layer rules

- Flood depth: shallow light cyan; moderate blue; deep dark blue; severe indigo.
- Building risk: safe green; warning yellow; high orange; critical red.
- Rescue route cyan; alternative route violet; blocked infrastructure red; safe shelters teal.
- Flood-depth and building-risk overlays have separate toggles. Add legends, units, timestamps, and a non-color cue (pattern/icon/label) for critical distinctions.
- Respect reduced-motion preference; animation never hides current state.

## Shared shell

Persistent top bar: scenario name, simulation clock/state, connection indicator, reset/undo where valid, and global layer or presentation controls. Left navigation exposes the five screens. Keep a scenario context drawer for seed, model version, and assumptions. All views show whether data is synthetic, imported, or derived.

## 1. Command Center

**Purpose:** make the signature loop understandable at presentation distance.

- Large interactive city viewport with flood, risk, route, and unit layers.
- Severity strip with simulated flood extent, highest depth, at-risk population, open/blocked routes, and available units. Each metric names units and updates from the backend.
- Critical zone queue with priority, access status, and reason summary.
- Proposed response card showing assignments, routes, shelters, constraints, and warnings.
- Active operations list distinguished from unapproved proposals.
- Event feed with simulated time and agent/source labels.
- Human controls: Review plan, Approve, Reject, Pause, Advance step. Approval is explicit and logged.

## 2. Digital Twin Studio

- Expandable canvas with selectable building, road, bridge, hospital, shelter, river segment, terrain cell, zone, or unit.
- Inspector displays stable ID, coordinates/elevation, state, provenance, and last update.
- Independent layer switches: depth, building risk, closures/damage, facilities, population/vulnerability, routes, units.
- Legend and depth scale remain visible while the layer is on.
- Show simulation time, state version, and selected object. Avoid editing geometry as though it were a live city.

## 3. Scenario Lab

- Rainfall intensity and duration, river stage, seed, and resource availability controls with units and validated bounds.
- Toggle road/bridge closures by selecting a city asset; show the affected connection.
- Presets are versioned input bundles, not named outcome promises.
- Run one step, run to configured horizon, pause, and reset.
- What-if comparison runs identical seed/model/solver versions with labeled parameter differences.
- Show loading/error state and explain invalid or disconnected scenarios.

## 4. AI Decision Explorer

- Event timeline grouped by state version: trigger, agents invoked, outputs, plan revision, reviewer action.
- Decision cards show inputs, algorithm/model version, score components, constraints, feasible alternatives, and warnings.
- Route display explains distance and hazard cost; assignment shows unit capacity and trade-off.
- Replanning links the triggering road/flood change to changed routes or assignments.
- Human review records approver action, simulated timestamp, and plan version.

## 5. Model Intelligence Lab

- Dataset description, provenance, license/attribution note, synthetic-vs-observed designation, sample counts, and grouping key.
- Model type, target definition, feature definitions/units, preprocessing, configuration, random seed, artifact hash, and training/test scenario split.
- Evaluation: class counts, confusion matrix, balanced accuracy, macro-F1, per-class recall, and critical-class precision-recall where defined; include rule baseline.
- Feature importance with method and caveat; selected examples reveal features, target source, prediction, and model version.
- State limitations clearly: synthetic labels do not validate real floods; spatially adjacent cells are not independent; the model is for demonstration and must not be used operationally.

## Interaction and accessibility

- Keyboard focus is visible; critical controls have text labels and confirmation state.
- Use readable contrast and scalable typography. Do not encode status with hue alone.
- Tooltips explain units and formulas briefly.
- Provide a 2D fallback table or map summary when WebGL fails or reduced graphics are needed.
- Avoid flashing, unnecessary camera movement, and animation that changes meaning.

## Part 11 presentation mode

Judge Mode uses the same application scenario and backend records as Command Center. It expands the Digital Twin, keeps four current-state indicators and the current event visible, and surfaces agent traces, proposal freshness, assignment evidence and mission lifecycle counts. It has explicit entry/exit controls, low-graphics and predicted-risk switches, supporting-workspace links, and a next-review cue derived from the current API snapshot. A proposal remains pending human approval and links to the existing commander review. Out-of-date prediction/plan values are withheld or labeled historical. The route includes a table fallback for backend-derived exposed-building depths if the 3D scene fails.

The shared interface uses a restrained graphite/navy surface system, mint action and focus color, readable status badges, consistent panel headings and minimum-height controls. At 1366 × 768, prioritize the city and core evidence; detail pages retain their existing navigation and controls. Do not describe synthetic model scores as real-world accuracy or simulated missions as completed rescue outcomes.

## Performance budget (initial targets)

Keep the fictional demo city within a few hundred visible buildings and a modest flood grid (for example 64×64); measure on the actual demo laptop before expanding. Avoid real-time fluid rendering and expensive postprocessing. The frontend should request compact state deltas, batch geometry where feasible, and decouple visual animation from simulation step frequency. Targets are engineering goals to profile, not claims until measured.
