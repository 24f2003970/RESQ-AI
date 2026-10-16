# Mission Lifecycle

## State machine

```text
approved plan → ready → en_route → arrived → completed → (unit return-to-service)
                       ↘ blocked → en_route (approved route revision)
           ready / en_route / blocked / arrived → cancelled
```

Only `ready` can dispatch. Only `en_route` can become `arrived` through clock progression. A road disruption can move `en_route` to `blocked`; route calculation alone does not resume it. Route approval requires current mission version, simulation state, epoch, infrastructure revision, and an open proposed route. `arrived` requires explicit commander completion. Invalid state jumps are rejected.

## Route and time

Progress is measured along the route's backend polyline using per-segment lengths and speeds; positions interpolate in 3D, including bridge elevation. Operational time is synthetic and independent of flood ticks. Clock advances are bounded to 1–30 seconds. A stopped, blocked, paused, or not-yet-dispatched unit does not move.

## Scenario epochs and replay

Every mission is bound to the scenario ID and epoch in which its plan was approved. Reset changes the active epoch. Historical records and their reservations remain auditable in that epoch, while commands against them fail. Replay is read-only and returns durable timeline entries; it does not rerun allocation, change unit status, or release resources.

## Approval and identity

Approval creates missions idempotently from the saved approved plan. Mission identity is stable per plan assignment. Unit identity is unique within scenario epoch in the authoritative `unit_resources` table. Simulation version and infrastructure revision are captured at creation and checked at dispatch/replanning boundaries.
