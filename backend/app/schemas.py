from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator


class Entity(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)
    id: str = Field(min_length=1)
    name: str


class Position(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)
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


class RoadNode(Entity):
    position: Position


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


class TerrainGrid(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)
    cell_size_m: float = Field(gt=0)
    x_centers_m: list[float]
    y_centers_m: list[float]
    elevation_m: list[list[float]]


class CityState(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    city: City
    scenario: ScenarioMetadata
    terrain: TerrainGrid
    districts: list[District]
    buildings: list[Building]
    roads: list[Road]
    road_nodes: list[RoadNode]
    bridges: list[Bridge]
    hospitals: list[Hospital]
    shelters: list[Shelter]
    rivers: list[River]
    rescue_units: list[RescueUnit]
    green_areas: list[GreenArea]

    @model_validator(mode="after")
    def validate_relationships(self):
        groups = [self.districts, self.buildings, self.roads, self.road_nodes, self.bridges,
                  self.hospitals, self.shelters, self.rivers, self.rescue_units, self.green_areas]
        ids = [e.id for group in groups for e in group]
        if len(ids) != len(set(ids)):
            raise ValueError("Entity IDs must be globally unique")
        districts = {d.id for d in self.districts}
        buildings = {b.id for b in self.buildings}
        roads = {r.id for r in self.roads}
        nodes = {n.id for n in self.road_nodes}
        if any(r.from_node not in nodes or r.to_node not in nodes for r in self.roads):
            raise ValueError("Road references unknown endpoint")
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


class SimulationParameters(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)
    rainfall_mm_h: float = Field(ge=0, le=300)
    river_level_m: float = Field(ge=-2, le=5)
    drainage_effectiveness: float = Field(ge=0, le=1)
    speed: float = Field(ge=0.25, le=8)


class ScenarioCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    name: str = Field(min_length=1, max_length=80)
    seed: int = Field(ge=0, le=2_147_483_647, default=2026)
    preset: Literal["mild", "heavy", "extreme"] = "mild"


class ParameterUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    rainfall_mm_h: float | None = Field(default=None, ge=0, le=300)
    river_level_m: float | None = Field(default=None, ge=-2, le=5)
    drainage_effectiveness: float | None = Field(default=None, ge=0, le=1)
    speed: float | None = Field(default=None, ge=0.25, le=8)
    expected_version: int = Field(ge=1)


class AdvanceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    steps: int = Field(ge=1, le=120)
    expected_version: int = Field(ge=1)
    single_step: bool = False


class VersionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1)


class RescuePlanDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["approved", "rejected"]
    expected_version: int = Field(ge=1)
    reason: str = Field(default="", max_length=500)

    @model_validator(mode="after")
    def require_rejection_reason(self):
        if self.action == "rejected" and not self.reason.strip():
            raise ValueError("A rejection reason is required.")
        return self


class RoadClosureRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    road_id: str = Field(min_length=1)
    reason: str = Field(default="Commander closure", min_length=1, max_length=300)


class RescueAssignmentEdit(BaseModel):
    model_config = ConfigDict(extra="forbid")
    unit_id: str = Field(min_length=1)
    destination_id: str = Field(min_length=1)


class RescuePlanModification(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1)
    assignments: list[RescueAssignmentEdit] = Field(max_length=20)


class ImpactItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    entity_id: str
    max_depth_m: float
    mean_depth_m: float | None = None
    exposed_fraction: float | None = None
    category: Literal["none", "watch", "moderate", "severe"] | None = None
    water_reaches_building: bool | None = None
    status: Literal["open", "caution", "flooded", "closed"] | None = None
    deck_elevation_m: float | None = None
    water_surface_m: float | None = None


class ImpactAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    buildings: list[ImpactItem]
    roads: list[ImpactItem]
    bridges: list[ImpactItem]


class MassBalance(BaseModel):
    model_config = ConfigDict(extra="forbid")
    initial_m3: float
    rainfall_m3: float
    river_in_m3: float
    river_out_m3: float
    drainage_m3: float
    stored_m3: float
    balance_error_m3: float


class SimulationEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event_id: str
    scenario_id: str
    tick: int = Field(ge=0)
    simulated_seconds: int = Field(ge=0)
    state_version: int = Field(ge=1)
    event_type: str
    entity_ids: list[str]
    payload: dict[str, Any]


class ScenarioState(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    name: str
    seed: int
    city_id: str
    preset: Literal["mild", "heavy", "extreme"]
    status: Literal["paused", "running"]
    tick: int
    epoch: int
    state_version: int
    simulated_seconds: int
    grid_width: int
    grid_height: int
    cell_size_m: float
    x_centers_m: list[float]
    y_centers_m: list[float]
    terrain_m: list[list[float]]
    depth_m: list[list[float]]
    parameters: SimulationParameters
    impacts: ImpactAssessment
    mass_balance: MassBalance
    maximum_depth_m: float
    affected_buildings: int
    exposed_roads: int
    closed_bridges: int


class ScenarioEnvelope(BaseModel):
    state: ScenarioState
    events: list[SimulationEvent]


class MLFeatureInfo(BaseModel):
    name: str
    description: str
    units: str
    role: Literal["numeric", "indicator"]


class MLModelInfo(BaseModel):
    status: Literal["ready", "unavailable"]
    model_name: str
    model_version: str | None = None
    algorithm: str | None = None
    trained_at_utc: str | None = None
    training_scenarios: int | None = None
    observation_count: int | None = None
    horizon_ticks: int | None = None
    horizon_minutes: int | None = None
    target: str
    artifact_sha256: str | None = None
    sklearn_version: str | None = None
    probabilities_calibrated: bool = False
    reliability_status: Literal["available", "degraded", "unavailable"] = "degraded"
    calibration_status: str = "not_evaluated"
    reliability_warnings: list[str] = []
    unavailable_reason: str | None = None


class MLDatasetInfo(BaseModel):
    dataset_version: str
    engine_version: str
    label_definition: str
    feature_names: list[str]
    target_name: str
    scenario_count: int
    observation_count: int
    positive_count: int
    negative_count: int
    positive_fraction: float
    duplicate_feature_target_rows: int
    random_sampling_seed: int
    configuration: dict[str, Any]
    provenance: str
    csv_sha256: str | None = None


class MLFeatureContribution(BaseModel):
    name: str
    value: float
    global_permutation_importance: float


class BuildingRiskPrediction(BaseModel):
    building_id: str
    current_exposed: bool
    current_exposure_category: Literal["none", "watch", "moderate", "severe"]
    current_max_depth_m: float
    predicted_future_exposed: bool
    predicted_category: Literal["predicted_exposed", "predicted_not_exposed"]
    uncalibrated_model_score: float
    calibrated_synthetic_probability: float | None = None
    distribution_support_status: Literal["within_observed_support", "edge_of_observed_support", "outside_observed_support", "missing_features", "invalid_features", "incompatible_schema", "unavailable"] = "unavailable"
    reliability_warnings: list[str] = []
    influential_features: list[MLFeatureContribution]


class ScenarioPredictionSet(BaseModel):
    model_version: str
    scenario_id: str
    scenario_state_version: int
    scenario_tick: int
    scenario_epoch: int = 0
    horizon_ticks: int
    horizon_minutes: int
    target_definition: str
    probabilities_calibrated: bool = False
    reliability_status: Literal["available", "degraded", "unavailable"] = "degraded"
    calibration_status: str = "not_evaluated"
    reliability_warnings: list[str] = []
    predictions: list[BuildingRiskPrediction]


class MLEvaluationReport(BaseModel):
    evaluation_version: str
    created_at_utc: str
    selected_model: str
    selection_metric: str
    validation_candidates: dict[str, Any]
    test_set_label: str
    test_scenario_count: int
    test_observation_count: int
    test_positive_count: int
    test_negative_count: int
    test_metrics: dict[str, Any]
    test_baselines: dict[str, Any]
    false_positive_examples: list[dict[str, Any]]
    false_negative_examples: list[dict[str, Any]]
    permutation_importance: list[dict[str, Any]]
    probabilities_calibrated: bool
    model_score_note: str
    inference_latency_ms_per_observation: float
    latency_batch_size: int
    latency_repetitions: int
    test_scenario_ids: list[str]
