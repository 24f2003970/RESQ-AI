# Part 9 visual demo checklist

Use a disposable local database and a deterministic scenario seed. Record browser, GPU, viewport, seed, scenario epoch, mission ID and whether standard or low graphics is active. This list is a manual test procedure; it is not a claim that the browser review has been completed.

## City and scene controls

- [ ] Open Command Center at 1366×768; confirm the viewport and surrounding panels remain readable. Repeat at 1440×900 and 1920×1080.
- [ ] Select City overview, Flood hotspot, Bridge crossing and Rescue operation presets. Confirm easing is bounded and normal orbit/zoom remains under user control.
- [ ] Switch Daylight, Overcast and Low-light. Confirm these controls change scene presentation only and do not change rainfall, water depth or state version.
- [ ] Inspect residential, commercial, hospital and shelter buildings. Confirm bodies remain aligned with backend locations, footprints and heights.
- [ ] Inspect all roads and six bridges. Confirm road surfaces, markings and bridge decks align with the network corridors; closures are visibly marked.
- [ ] Enable flood and future-exposure layers separately. Compare the legend to backend depth values and confirm predicted exposure is visually distinct from current water.
- [ ] Enable/disable terrain, infrastructure, facilities, units, greenery and districts. Confirm status and selection remain legible without relying on color alone.
- [ ] Select a building and a mission; confirm the inspector or operations panel shows its backend identity and the camera targets the selected object.
- [ ] Enable Low graphics. Confirm shadows, terrain detail, windows, trees, street lights and water material change while scenario values remain identical.
- [ ] Test the WebGL fallback/inventory and keyboard focus states if the renderer fails or is unavailable.

## Mission presentation

- [ ] Create and approve a rescue plan using the existing commander workflow.
- [ ] Dispatch a mission and select its unit in Mission Operations.
- [ ] Advance the operational clock so the vehicle traverses at least two road turns. Confirm it follows each route segment without cutting diagonally across a building or canal.
- [ ] If the route crosses a bridge, confirm the vehicle follows approved bridge elevation.
- [ ] Close a road ahead of a moving unit. Confirm the unit stops at its persisted position and the route/blocked status is clear.
- [ ] Propose and approve a safe route revision. Confirm movement starts from the persisted stopped position and follows the revised approved polyline.
- [ ] Advance to arrival; confirm arrival does not mark completion or release the resource.
- [ ] Complete the mission explicitly and return the unit to service explicitly. Refresh and confirm state/history persists.
- [ ] Switch Scenario A/B views and Guided Demo stages. Confirm the selected state, explanation, actions and camera target stay coherent and no timed fake movement occurs.

## Record results

Record pass/fail, screenshots, browser/GPU, route/mission IDs, viewport, depth/version and any mismatch. Capture renderer draw calls and FPS from the browser's supported diagnostics if available; these are not currently automated metrics.
