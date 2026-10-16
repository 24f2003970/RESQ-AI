# Part 8 Mission Demo Guide

1. Start the local backend and frontend using the existing development instructions. Open Guided Demo and complete the existing Part 7 flood, local ML, agent, closure, replanning, and proposal review chapters.
2. Approve a valid proposal. The approval creates `ready` missions and reserves their units; it does not dispatch them.
3. Open Mission Operations, select a ready mission, and choose **Dispatch mission**. Select/focus the mission in the Digital Twin.
4. Advance the operational clock in small increments. The displayed vehicle follows backend route geometry and stops when the backend clock stops.
5. To demonstrate a disruption, close a road that is still ahead on the selected mission's route. A relevant mission becomes blocked. Request a replacement route and inspect the proposal.
6. Approve the proposed route explicitly; then advance the clock until the unit arrives. Confirm simulated completion explicitly.
7. Inspect persisted events and the latest advisory agent trace. Restore a completed/cancelled unit only when intentionally demonstrating its return-to-service at its recorded position.

The exact route depends on the saved scenario, closures, and approved proposal. Do not claim the route is blocked unless the closure intersects a remaining graph segment. A route that does not encounter the chosen closure is a valid demo outcome; choose a different still-open route segment. This is a fictional simulator and makes no claim about real dispatch, evacuation, or lives saved.
