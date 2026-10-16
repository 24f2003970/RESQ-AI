# Resource Reservation and Release Policy

`unit_resources` is the authoritative record for per-epoch unit availability, mission ownership, and simulated current position. `missions` is authoritative for mission lifecycle state; the approved plan is retained as the historical decision record. Refreshing the browser, restarting the service, or changing scenario epoch never releases a reservation.

- Approval reserves assigned units immediately (`reserved`).
- Dispatch changes the owned unit to `en_route`; a road interruption changes it to `blocked`; arrival changes it to `at_destination`.
- Cancelling a `ready` mission releases its reservation because no movement occurred.
- Cancelling after dispatch, or confirming simulated completion, leaves the unit `unavailable`.
- A commander must explicitly invoke return-to-service/restore. The unit becomes `available` at its persisted current location. The simulator does not invent a return trip to base.
- Historical epoch records are retained. Availability and conflicts are scoped to the active epoch; old epoch records remain auditable and cannot be commanded.

Completion only means the fictional simulated mission was confirmed complete. Synthetic occupant targets are not verified rescue outcomes.
