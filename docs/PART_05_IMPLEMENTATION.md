# Part 5 implementation

Part 5 adds a local NetworkX routable road graph, explicit bridge and access edges, flood-aware Dijkstra routing, transparent destination rankings, exact constrained assignment plus a like-for-like nearest-unit baseline, SQLite proposal/decision persistence, road-closure overlays, and a commander review panel. Proposed routes are drawn over the 3D city in cyan, with alternatives in violet. No external AI or routing API is used, and proposal approval never simulates mission completion.

The graph splits the ten deterministic city corridors at geometric crossings and connects them with stable junction IDs. Bridge decks occupy distinct 46 m segments. Vehicle policy, access-spur limit, synthetic speeds, priority weights, objective, constraints, and known geometry limitations are recorded in [ROUTING_MODEL.md](ROUTING_MODEL.md) and [RESOURCE_OPTIMIZATION.md](RESOURCE_OPTIMIZATION.md). Contract and approval rules are in [RESCUE_PLAN_CONTRACT.md](RESCUE_PLAN_CONTRACT.md).

Part 5 verification and remaining limits are recorded in [PART_05_VERIFICATION.md](PART_05_VERIFICATION.md). This increment does not add full autonomous agents, boat navigation, completed-rescue state, or automatic execution.
