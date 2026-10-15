"""Create a reproducible flood demo using the authoritative local scenario store."""

import json
import uuid

from ..scenarios import store
from ..schemas import AdvanceRequest, ParameterUpdate, ScenarioCreate


def main() -> None:
    envelope = store.create(ScenarioCreate(name="Part 4 Flood Demonstration", seed=2026, preset="mild"),
                            f"part-04-flood-demo-{uuid.uuid4()}")
    state = envelope.state
    envelope = store.update_parameters(state.id, ParameterUpdate(rainfall_mm_h=100, river_level_m=0.8,
        drainage_effectiveness=0.4, expected_version=state.state_version))
    envelope = store.advance(state.id, AdvanceRequest(steps=6, single_step=True,
        expected_version=envelope.state.state_version))
    state = envelope.state
    print(json.dumps({
        "scenario_id": state.id,
        "seed": state.seed,
        "tick": state.tick,
        "simulated_minutes": state.simulated_seconds // 60,
        "rainfall_mm_h": state.parameters.rainfall_mm_h,
        "river_level_m": state.parameters.river_level_m,
        "drainage_effectiveness": state.parameters.drainage_effectiveness,
        "maximum_land_depth_m": state.maximum_depth_m,
        "affected_buildings": state.affected_buildings,
        "exposed_roads": state.exposed_roads,
        "closed_bridges": state.closed_bridges,
    }, indent=2))


if __name__ == "__main__":
    main()
