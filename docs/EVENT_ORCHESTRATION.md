# Event orchestration

The local SQLite outbox is the source of truth for backend agent triggers. Its envelope contains event ID/type, scenario ID, epoch, simulation tick, state version, optional infrastructure revision, UTC creation time, source module, affected IDs, structured payload and correlation/causation IDs. Simulation time and real processing timestamps are distinct.

## Transaction boundaries

- Scenario create, parameter change, advance and reset insert their outbox envelope before the same SQLite transaction commits scenario state and simulation history.
- Manual road close/reopen increments `scenario_infrastructure.revision`, supersedes proposed plans and inserts an `infrastructure_changed` event in one `BEGIN IMMEDIATE` transaction.
- Approval/rejection updates plan status and inserts its rescue decision event in the same plan-store transaction.
- Agent execution claims the event by changing `pending` to `processing` in a transaction. Each agent result and the final decision trace are persisted separately; plan saving rechecks all assumptions in a fresh locked transaction. The queue is at-least-once, not a cross-stage all-or-nothing transaction.

`AgentOrchestrator` checks event ID status, event attempt count and `(event_id, agent_name)` uniqueness. Duplicate processors cannot claim an already-processing event. At service startup, interrupted `processing`/retryable `failed` events return to pending and are retried, up to three attempts. Failed final events remain visible and may be manually retried within that bound. Unrecognized event types remain auditable as superseded/non-trigger records.

After a stage, the worker checks current epoch, simulation version and infrastructure revision. If they changed, the result is superseded and cannot save or approve a plan. PlanStore rechecks under lock at save and decision, which closes the race between calculation and persistence. Equivalent proposal signatures and unique trigger IDs suppress duplicate plans.

The frontend polls typed REST endpoints every 2.5–3 seconds; abort/sequence guards prevent stale response replacement. Polling is for display only. Replay reads checkpoints and deterministic history but does not write an outbox event or apply an operational mutation. Historical traces survive reset and are labeled by epoch.
