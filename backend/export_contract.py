"""Export schema artifacts without starting a server. Run from backend/."""
import json
import tempfile
from pathlib import Path
from app.main import app
from app.schemas import (BuildingRiskPrediction, CityState, MLDatasetInfo, MLEvaluationReport,
                         MLFeatureInfo, MLModelInfo, ScenarioEnvelope, ScenarioPredictionSet,
                         RescuePlanDecision, RoadClosureRequest, RescuePlanModification)
from app.rescue import RescuePlan
from app.city_service import generate_city
from app.scenarios import ScenarioStore

target = Path(__file__).resolve().parents[1] / "frontend" / "src" / "api"
target.mkdir(parents=True, exist_ok=True)
(target / "openapi.json").write_text(json.dumps(app.openapi(), indent=2) + "\n", encoding="utf-8")
(target / "city.schema.json").write_text(json.dumps(CityState.model_json_schema(), indent=2) + "\n", encoding="utf-8")
(target / "scenario.schema.json").write_text(json.dumps(ScenarioEnvelope.model_json_schema(), indent=2) + "\n", encoding="utf-8")
for name, model in {
    "ml-model.schema.json": MLModelInfo,
    "ml-dataset.schema.json": MLDatasetInfo,
    "ml-evaluation.schema.json": MLEvaluationReport,
    "ml-feature.schema.json": MLFeatureInfo,
    "ml-predictions.schema.json": ScenarioPredictionSet,
    "ml-building-prediction.schema.json": BuildingRiskPrediction,
    "rescue-plan.schema.json": RescuePlan,
    "rescue-plan-decision.schema.json": RescuePlanDecision,
    "road-closure.schema.json": RoadClosureRequest,
    "rescue-plan-modification.schema.json": RescuePlanModification,
}.items():
    (target / name).write_text(json.dumps(model.model_json_schema(), indent=2) + "\n", encoding="utf-8")
fixtures = target.parent / "test" / "fixtures"
fixtures.mkdir(parents=True, exist_ok=True)
(fixtures / "city.json").write_text(json.dumps(generate_city().model_dump(), indent=2) + "\n", encoding="utf-8")
with tempfile.TemporaryDirectory() as temp:
    scenario_store = ScenarioStore(Path(temp) / "fixture.sqlite3")
    scenario = scenario_store.get(scenario_store.active_id()).model_dump()
(fixtures / "scenario.json").write_text(json.dumps(scenario, indent=2) + "\n", encoding="utf-8")
