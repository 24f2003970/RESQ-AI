# Part 8.2 Manual Browser Walkthrough Checklist

Status: pending manual execution. This checklist is a test procedure, not evidence that visual verification has occurred.

Use a disposable local database and the normal local backend/frontend. Create a reproducible seeded scenario, generate and approve a rescue plan, and keep the scenario epoch and simulation version visible for comparison.

## Dispatch and route following

- [ ] Open the approved mission in the 3D city and confirm its unit starts at the persisted unit position.
- [ ] Dispatch the unit and advance the operational clock in small increments.
- [ ] Confirm the vehicle follows the approved route polyline through two road turns. At each turn it reaches the corner before taking the next segment; it does not cut diagonally through buildings or canals.
- [ ] Where the approved route crosses a bridge, confirm vehicle elevation follows the route's bridge elevation.
- [ ] Compare the visible vehicle location with the authoritative mission position and `traversed_distance_m`; the displayed interpolation must never exceed the latest authoritative progress.

## Blockage and route revision

- [ ] While the vehicle is between intersections, manually close a road segment ahead on its route.
- [ ] Confirm the mission becomes blocked at its current persisted position without snapping to another node.
- [ ] Request a replacement route and inspect its route geometry and edge IDs. Confirm it starts at the blocked position, contains no closed/flooded/inaccessible road segment, and stays connected to the traversable road geometry.
- [ ] Approve the current proposal. Confirm the mission resumes from the same position and follows the revised polyline.

## Arrival, completion and resource restoration

- [ ] Advance the clock until the unit reaches the destination. Confirm arrival does not itself mark the mission completed or release the unit.
- [ ] Confirm simulated completion explicitly as commander.
- [ ] Use the explicit return-to-service/restore action. Confirm the unit becomes available at its persisted current location, with no automatic return-to-base movement.
- [ ] Refresh the page and confirm the mission event history and restored resource state persist.

Record the browser, scenario seed/epoch, mission ID, and any mismatch between route geometry, mission progress and displayed movement. Never use this simulation for operational emergency decisions.
