"""Reproducible local mission-clock and position benchmark (temporary SQLite only).

Run from backend/: python benchmark_missions.py
"""
from __future__ import annotations

import statistics
import tempfile
import time
from pathlib import Path

from app.missions import MissionStore, _position_at
from app.rescue import PlanStore, RescuePlan
from app.scenarios import ScenarioStore
from app.schemas import ScenarioCreate


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="resq-part8-benchmark-", ignore_cleanup_errors=True) as folder:
        path = Path(folder) / "benchmark.sqlite3"
        scenarios = ScenarioStore(path)
        state = scenarios.create(ScenarioCreate(name="Part 8 benchmark", seed=2026, preset="mild"), "part8-benchmark").state
        plans = PlanStore(path)
        revision, _ = plans.infrastructure(state.id, state.epoch)
        route = {"reachable": True, "distance_m": 2000, "polyline": [[0, 0], [1000, 0], [1000, 1000]],
                 "polyline_xyz": [[0, 0, 0], [1000, 0, 0], [1000, 1000, 0]],
                 "segment_lengths_m": [1000, 1000], "segment_speeds_mps": [6, 6],
                 "edge_ids": ["road-a:segment:0-1", "road-b:segment:0-1"], "road_ids": ["road-a", "road-b"]}
        plan = RescuePlan(plan_id="benchmark-plan", scenario_id=state.id, scenario_version=state.state_version,
                          scenario_epoch=state.epoch, infrastructure_revision=revision, simulation_tick=state.tick,
                          generated_at="2026-10-01T00:00:00+00:00", priorities=[],
                          missions=[{"unit_id": "unit-test", "unit_type": "rescue_team", "destination_id": "building-hospital",
                                     "unit_capacity": 4, "occupants_targeted": 2, "route": route}],
                          available_assignments=[], unreachable=[], comparison={}, solver_status="benchmark",
                          objective="benchmark", explanation="synthetic benchmark")
        plans.save(plan)
        plans.decision(plan.plan_id, "approved", expected_version=state.state_version)
        missions = MissionStore(str(path))
        mission = missions.list(state.id, state.epoch)[0]
        mission = missions.command(mission.mission_id, "dispatch", mission.mission_version, idempotency_key="dispatch")

        samples = []
        for index in range(100):
            clock = missions.clock(state.id, state.epoch)
            started = time.perf_counter()
            missions.advance(state.id, state.epoch, clock.version, state.state_version, 1, idempotency_key=f"advance-{index}")
            samples.append((time.perf_counter() - started) * 1000)
        route_sample = {"polyline": route["polyline_xyz"], "segment_lengths_m": route["segment_lengths_m"]}
        started = time.perf_counter()
        for step in range(10000):
            _position_at(route_sample, (step % 1999) + 0.25)
        position_ms = (time.perf_counter() - started) * 1000 / 10000
        started = time.perf_counter()
        for _ in range(100):
            missions.clock(state.id, state.epoch)
        read_ms = (time.perf_counter() - started) * 10
        print({"scenario": "one moving unit, 2 km route, 100 one-second persisted advances",
               "advance_mean_ms": round(statistics.mean(samples), 3),
               "advance_p95_ms": round(sorted(samples)[94], 3),
               "advance_max_ms": round(max(samples), 3),
               "position_interpolation_mean_ms": round(position_ms, 6),
               "clock_read_mean_ms": round(read_ms, 3),
               "elapsed_mission_seconds": missions.clock(state.id, state.epoch).seconds})


if __name__ == "__main__":
    main()
