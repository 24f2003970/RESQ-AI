# Mission Event Contract

Mission state changes append ordered `mission_events` with event ID, mission ID, event type, mission version, operational-clock seconds, payload, and timestamp. Clock changes append `mission_clock_events`. The timeline includes creation, dispatch, progress, block, approved route revision, arrival, completion, cancellation, and return-to-service. Events are immutable audit entries; API replay is a read-only view.

Relevant existing six-agent pipeline triggers are `mission_dispatched`, `mission_blocked`, `mission_arrived`, `mission_completed`, `mission_cancelled`, `mission_cancelled_unit_unavailable`, `unit_returned_to_service`, and `mission_route_revision_approved`. They are written to the existing durable outbox in the same SQLite transaction as the operation. Agents produce advisory traces and proposals; only explicit commander commands change mission state. Trigger policy limits new commander proposals to meaningful resource/access events to avoid loops from every movement tick.

Command endpoints accept expected versions and optional `Idempotency-Key`. Repeated identical keys return the saved result; reuse for a different operation is rejected. The replay endpoint never enqueues agent work or changes reservations.
