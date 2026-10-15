import csv
import json

from fastapi.testclient import TestClient

from app import main as main_module, ml_service
from app.main import app
from app.ml.dataset import DatasetConfig, generate_dataset
from app.ml.features import FEATURE_NAMES, TARGET_NAME
from app.ml.train import train
from app.ml_service import predictions
from app.scenarios import ScenarioStore
from app.schemas import AdvanceRequest, ScenarioCreate


def test_dataset_generation_is_repeatable_grouped_and_has_no_future_features(tmp_path):
    config = DatasetConfig(scenario_count=20, observation_ticks=(0,))
    first = generate_dataset(config, tmp_path / "one.csv", tmp_path / "one.json")
    second = generate_dataset(config, tmp_path / "two.csv", tmp_path / "two.json")
    assert first["observation_count"] == second["observation_count"] == 20 * 72
    assert first["positive_count"] + first["negative_count"] == first["observation_count"]
    assert first["duplicate_feature_target_rows"] == 0
    assert first["feature_names"] == second["feature_names"] == FEATURE_NAMES
    assert first["target_name"] == TARGET_NAME
    assert (tmp_path / "one.csv").read_bytes() == (tmp_path / "two.csv").read_bytes()
    with (tmp_path / "one.csv").open(newline="", encoding="utf-8") as stream:
        headers = next(csv.reader(stream))
    assert "scenario_id" not in FEATURE_NAMES
    assert "future_depth_m" not in headers and "future_exposed" not in FEATURE_NAMES
    assert set(FEATURE_NAMES).issubset(headers)


def test_ml_api_contracts_and_live_predictions(tmp_path, monkeypatch):
    scenario_store = ScenarioStore(tmp_path / "ml-api.sqlite3")
    monkeypatch.setattr(main_module, "store", scenario_store)
    monkeypatch.setattr(ml_service, "store", scenario_store)
    client = TestClient(app)
    assert client.get("/api/v1/ml/model").json()["status"] == "ready"
    dataset = client.get("/api/v1/ml/dataset").json()
    evaluation = client.get("/api/v1/ml/evaluation").json()
    assert dataset["scenario_count"] == 72
    assert evaluation["test_scenario_count"] == 15
    assert evaluation["test_metrics"]["f1"] > 0

    created = scenario_store.create(ScenarioCreate(name="ML API test", seed=2026, preset="heavy"), "ml-api-test-key")
    scenario_id = created.state.id
    result = client.get(f"/api/v1/scenarios/{scenario_id}/predictions")
    assert result.status_code == 200
    payload = result.json()
    state = scenario_store.get(scenario_id).state
    assert payload["scenario_id"] == scenario_id
    assert payload["scenario_state_version"] == state.state_version
    assert payload["scenario_tick"] == state.tick
    assert len(payload["predictions"]) == 72
    assert payload["probabilities_calibrated"] is False
    first = predictions(scenario_id)
    second = predictions(scenario_id)
    assert [p.model_dump() for p in first.predictions] == [p.model_dump() for p in second.predictions]
    building_id = first.predictions[0].building_id
    selected = client.get(f"/api/v1/scenarios/{scenario_id}/predictions/{building_id}")
    assert selected.status_code == 200 and len(selected.json()["predictions"]) == 1
    missing = client.get(f"/api/v1/scenarios/{scenario_id}/predictions/not-a-building")
    assert missing.status_code == 404
    advanced = scenario_store.advance(scenario_id, AdvanceRequest(steps=1, single_step=True,
        expected_version=state.state_version)).state
    refreshed = client.get(f"/api/v1/scenarios/{scenario_id}/predictions").json()
    assert refreshed["scenario_state_version"] == advanced.state_version
    assert refreshed["scenario_tick"] == advanced.tick == state.tick + 1


def test_saved_evaluation_split_groups_are_disjoint():
    metadata_path = ml_service.ARTIFACT_DIR / "model_metadata.json"
    split = json.loads(metadata_path.read_text(encoding="utf-8"))["split_scenario_ids"]
    groups = [set(split[name]) for name in ("train", "validation", "test")]
    assert [len(group) for group in groups] == [42, 15, 15]
    assert not (groups[0] & groups[1] or groups[0] & groups[2] or groups[1] & groups[2])


def test_training_compares_models_and_saves_a_verified_bundle(tmp_path):
    data = tmp_path / "training.csv"
    source = tmp_path / "dataset.json"
    output = tmp_path / "artifacts"
    generate_dataset(DatasetConfig(scenario_count=40, observation_ticks=(0, 3)), data, source)
    report = train(data, source, output, seed=92021)
    metadata = json.loads((output / "model_metadata.json").read_text(encoding="utf-8"))
    assert report["training"]["algorithm"] in {"logistic_regression", "decision_tree_depth_5", "decision_tree_depth_9", "random_forest"}
    assert set(report["evaluation"]["validation_candidates"]) == {"logistic_regression", "decision_tree_depth_5", "decision_tree_depth_9", "random_forest"}
    assert metadata["artifact_sha256"]
    assert (output / "flood_exposure_v1.joblib").is_file()
    assert (output / "evaluation.json").is_file()
    split = metadata["split_scenario_ids"]
    parts = [set(split[name]) for name in ("train", "validation", "test")]
    assert not (parts[0] & parts[1] or parts[0] & parts[2] or parts[1] & parts[2])


def test_missing_model_artifact_degrades_cleanly(tmp_path, monkeypatch):
    monkeypatch.setattr(ml_service, "MODEL_PATH", tmp_path / "missing.joblib")
    ml_service._load_model_bundle.cache_clear()
    try:
        client = TestClient(app)
        assert client.get("/api/v1/ml/model").json()["status"] == "unavailable"
        assert client.get("/api/v1/scenarios/unknown/predictions").status_code == 503
    finally:
        ml_service._load_model_bundle.cache_clear()
