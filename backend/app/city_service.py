import random
from functools import lru_cache
from .terrain import terrain_at
from .terrain import CELL_SIZE_M, grid_coordinates, terrain_grid
from .schemas import (
    Bridge, Building, City, CityState, District, GreenArea, Hospital, Position,
    RescueUnit, River, Road, RoadNode, ScenarioMetadata, Shelter,
)


def point(x: float, y: float, z: float | None = None, seed: int = 2026) -> Position:
    return Position(x_m=x, y_m=y, elevation_m=terrain_at(x, y, seed) if z is None else z)


@lru_cache(maxsize=8)
def generate_city(seed: int = 2026) -> CityState:
    """Build the deterministic fictional city and its seed-matched terrain."""
    def at(x: float, y: float, z: float | None = None) -> Position:
        return point(x, y, z, seed)

    rng = random.Random(f"resq-v1:{seed}:buildings")
    trees_rng = random.Random(f"resq-v1:{seed}:greenery")
    city = City(id=f"city-v1-{seed}", name="Riverside", seed=seed,
                generator_version="1.0.0", width_m=660, depth_m=500)
    districts = [District(id=f"district-{i}", name=name, land_use=land,
                          center=at(x, y), width_m=320, depth_m=220)
                 for i, (name, land, x, y) in enumerate([
                     ("Northbank", "residential", -165, 125),
                     ("Civic Quarter", "mixed", 165, 125),
                     ("West End", "mixed", -165, -125),
                     ("Commerce Park", "commercial", 165, -125)], 1)]
    roads: list[Road] = []
    bridges: list[Bridge] = []
    for i, x in enumerate([-260, -156, -52, 52, 156, 260]):
        road = Road(id=f"road-ns-{i}", name=f"{i + 1} Avenue", from_node=f"node-{i}-south",
                    to_node=f"node-{i}-north", start=at(x, -240), end=at(x, 240),
                    width_m=14, length_m=480)
        roads.append(road)
        bridges.append(Bridge(id=f"bridge-{i}", name=f"{i + 1} Avenue crossing",
                              road_id=road.id, position=at(x, 0, terrain_at(x, 30, seed) + .4), width_m=14, length_m=46))
    for i, y in enumerate([-200, -100, 100, 200]):
        roads.append(Road(id=f"road-ew-{i}", name=["Foundry Road", "Civic Road", "Garden Road", "Northbank Road"][i],
                          from_node=f"node-west-{i}", to_node=f"node-east-{i}",
                          start=at(-320, y), end=at(320, y), width_m=14, length_m=640))
    buildings = []
    green_areas = []
    for ix, x in enumerate([-208, -104, 0, 104, 208]):
        for iy, y in enumerate([-150, -60, 60, 150]):
            if (ix, iy) in [(0, 2), (3, 0)]:
                green_areas.append(GreenArea(id=f"park-{ix}-{iy}", name="Canal Gardens" if iy == 2 else "Commerce Green",
                    position=at(x, y), width_m=84, depth_m=62,
                    trees=[at(x + trees_rng.uniform(-33, 33), y + trees_rng.uniform(-23, 23)) for _ in range(16)]))
                continue
            for lot in range(4):
                bx = x + (-23 if lot % 2 == 0 else 23)
                by = y + (-17 if lot < 2 else 17)
                district = (0 if x < 0 else 1) if y > 0 else (2 if x < 0 else 3)
                commercial = district == 3
                floors = rng.randint(4, 12) if commercial else rng.randint(2, 5)
                use = "commercial" if commercial else "residential"
                bid = f"building-{ix}-{iy}-{lot}"
                name = f"{districts[district].name} {ix * 16 + iy * 4 + lot + 1:02d}"
                if (ix, iy, lot) == (1, 1, 0):
                    use, floors, bid, name = "hospital", 4, "building-hospital", "Riverside General"
                if (ix, iy, lot) == (4, 3, 2):
                    use, floors, bid, name = "shelter", 2, "building-shelter", "Northbank Community Shelter"
                buildings.append(Building(id=bid, name=name, district_id=districts[district].id,
                    position=at(bx, by), width_m=rng.uniform(22, 32), depth_m=rng.uniform(19, 26),
                    height_m=floors * 3.6, floors=floors, use=use, occupants=rng.randint(10, 24) * floors,
                    material_color=rng.choice(["#c7c6bc", "#929da1", "#c4b39c", "#879393", "#b7c0bd"])))
    units = [RescueUnit(id=f"unit-{i}", name=name, type=kind, position=at(x, y), capacity=cap)
             for i, (name, kind, x, y, cap) in enumerate([
                 ("Medic 01", "ambulance", -156, -82, 2), ("Medic 02", "ambulance", -156, -70, 2),
                 ("Marine 01", "boat", 280, 23, 8), ("Alpha team", "rescue_team", 260, 166, 6),
                 ("Bravo team", "rescue_team", 260, 178, 6)], 1)]
    coordinates = grid_coordinates()
    return CityState(city=city, terrain={"cell_size_m": CELL_SIZE_M, "x_centers_m": coordinates[0],
        "y_centers_m": coordinates[1], "elevation_m": terrain_grid(seed).round(4).tolist()}, scenario=ScenarioMetadata(id="default", name="Riverside / Baseline",
        city_id=city.id, state_version=1, simulated_seconds=0,
        description="Seeded fictional city baseline. Dynamic flood conditions belong to saved scenarios."),
        districts=districts, buildings=buildings, roads=roads, bridges=bridges,
        road_nodes=[RoadNode(id=node_id, name=f"{r.name} endpoint", position=position)
                    for r in roads for node_id, position in [(r.from_node, r.start), (r.to_node, r.end)]],
        hospitals=[Hospital(id="hospital-1", name="Riverside General", building_id="building-hospital",
                            capacity=120, capabilities=["Emergency", "Inpatient"])],
        shelters=[Shelter(id="shelter-1", name="Northbank Community Shelter", building_id="building-shelter",
                          capacity=240, occupancy=0)],
        rivers=[River(id="river-1", name="Riverside Canal", start=at(-330, 0), end=at(330, 0),
                      width_m=34, surface_elevation_m=-.8)], rescue_units=units, green_areas=green_areas)
