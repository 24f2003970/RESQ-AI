from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator


class Entity(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    id: str = Field(min_length=1)
    name: str


class Position(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    x_m: float
    y_m: float
    elevation_m: float = 0


class District(Entity):
    land_use: Literal["residential", "commercial", "mixed"]
    center: Position
    width_m: float = Field(gt=0)
    depth_m: float = Field(gt=0)


class Building(Entity):
    district_id: str
    position: Position
    width_m: float = Field(gt=0)
    depth_m: float = Field(gt=0)
    height_m: float = Field(gt=0)
    floors: int = Field(ge=1)
    use: Literal["residential", "commercial", "hospital", "shelter"]
    occupants: int = Field(ge=0)
    material_color: str
    condition: Literal["baseline"] = "baseline"


class Road(Entity):
    from_node: str
    to_node: str
    start: Position
    end: Position
    width_m: float = Field(gt=0)
    length_m: float = Field(gt=0)
    status: Literal["open"] = "open"


class Bridge(Entity):
    road_id: str
    position: Position
    width_m: float = Field(gt=0)
    length_m: float = Field(gt=0)
    status: Literal["open"] = "open"


class Facility(Entity):
    building_id: str
    capacity: int = Field(ge=0)
    status: Literal["available"] = "available"


class Hospital(Facility):
    capabilities: list[str]


class Shelter(Facility):
    occupancy: int = Field(ge=0)


class River(Entity):
    start: Position
    end: Position
    width_m: float = Field(gt=0)
    surface_elevation_m: float


class RescueUnit(Entity):
    type: Literal["ambulance", "boat", "rescue_team"]
    position: Position
    capacity: int = Field(gt=0)
    status: Literal["standby"] = "standby"


class GreenArea(Entity):
    position: Position
    width_m: float = Field(gt=0)
    depth_m: float = Field(gt=0)
    trees: list[Position]


class City(Entity):
    seed: int
    generator_version: str
    width_m: float = Field(gt=0)
    depth_m: float = Field(gt=0)
    provenance: Literal["fictional_seed_city"] = "fictional_seed_city"


class ScenarioMetadata(Entity):
    city_id: str
    simulation_status: Literal["baseline"] = "baseline"
    state_version: int = Field(ge=1)
    simulated_seconds: int = Field(ge=0)
    description: str


class CityState(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    city: City
    scenario: ScenarioMetadata
    districts: list[District]
    buildings: list[Building]
    roads: list[Road]
    bridges: list[Bridge]
    hospitals: list[Hospital]
    shelters: list[Shelter]
    rivers: list[River]
    rescue_units: list[RescueUnit]
    green_areas: list[GreenArea]

    @model_validator(mode="after")
    def validate_relationships(self):
        groups = [self.districts, self.buildings, self.roads, self.bridges,
                  self.hospitals, self.shelters, self.rivers, self.rescue_units, self.green_areas]
        ids = [e.id for group in groups for e in group]
        if len(ids) != len(set(ids)):
            raise ValueError("Entity IDs must be globally unique")
        districts = {d.id for d in self.districts}
        buildings = {b.id for b in self.buildings}
        roads = {r.id for r in self.roads}
        if any(b.district_id not in districts for b in self.buildings):
            raise ValueError("Building references unknown district")
        if any(f.building_id not in buildings for f in [*self.hospitals, *self.shelters]):
            raise ValueError("Facility references unknown building")
        if any(b.road_id not in roads for b in self.bridges):
            raise ValueError("Bridge references unknown road")
        if self.scenario.city_id != self.city.id:
            raise ValueError("Scenario references unknown city")
        return self


class Health(BaseModel):
    status: Literal["ok"]
    service: str
    version: str
    mode: Literal["local"]
