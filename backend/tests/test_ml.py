import csv
import hashlib
import json
import shutil

from fastapi.testclient import TestClient

from app import main as main_module, ml_service
from app.main import app
from app.ml.dataset import DatasetConfig, generate_dataset
from app.ml.features import FEATURE_NAMES, TARGET_NAME
from app.ml.reliability import check_distribution_support
from app.ml.sensitivity import run_sensitivity
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
    assert first["csv_sha256"] == hashlib.sha256((tmp_path / "one.csv").read_bytes()).hexdigest()
    assert first["csv_sha256"] == second["csv_sha256"]
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
    reliability=client.get("/api/v1/ml/reliability").json()
    sensitivity=client.get("/api/v1/ml/sensitivity").json()
    assert dataset["scenario_count"] == 72
    assert evaluation["test_scenario_count"] == 15
    assert evaluation["test_metrics"]["f1"] > 0
    assert reliability["status"]=="available"
    assert reliability["report"]["calibration"]["test_groups_used_for_fit_or_choice"] is False
    assert sensitivity["status"]=="available"
    assert len(sensitivity["report"]["comparisons"])==63

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
    assert payload["scenario_epoch"] == state.epoch
    assert payload["probabilities_calibrated"] is True
    assert payload["reliability_status"] == "available"
    assert payload["calibration_status"] == "adopted"
    assert all(item["calibrated_synthetic_probability"] is not None for item in payload["predictions"])
    assert all(item["distribution_support_status"] in {"within_observed_support", "edge_of_observed_support", "outside_observed_support"} for item in payload["predictions"])
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
    evaluation=json.loads((ml_service.ARTIFACT_DIR/"evaluation.json").read_text(encoding="utf-8"))
    assert set(evaluation["test_scenario_ids"])==groups[2]
    assert evaluation["test_metrics"]["confusion_matrix"]=={"true_negative":2264,"false_positive":65,"false_negative":141,"true_positive":2930}


def test_calibration_is_grouped_and_preserves_untouched_test_metrics():
    reliability=json.loads((ml_service.ARTIFACT_DIR/"reliability_evaluation.json").read_text(encoding="utf-8"))
    split=reliability["split_scenario_ids"]
    parts=[set(split[key]) for key in ("train","validation","test")]
    assert not (parts[0]&parts[1] or parts[0]&parts[2] or parts[1]&parts[2])
    assert reliability["calibration"]["test_groups_used_for_fit_or_choice"] is False
    assert reliability["calibration"]["status"]=="adopted"
    raw=reliability["calibration"]["final_held_out_raw"]
    calibrated=reliability["calibration"]["final_held_out_platt"]
    assert abs(raw["brier_score"]-0.030526440868303074)<1e-12
    assert calibrated["brier_score"]<raw["brier_score"]
    assert len(raw["reliability_diagram"])==10
    assert sum(row["count"] for row in raw["reliability_diagram"])==5400
    assert reliability["dataset_sha256"]==json.loads((ml_service.ARTIFACT_DIR/"model_metadata.json").read_text())["dataset_sha256"]


def test_distribution_support_distinguishes_in_range_edge_missing_invalid_and_outside():
    support={"feature_schema":FEATURE_NAMES,"per_feature":{name:{"min":0,"max":1,"q005":.1,"q995":.9} for name in FEATURE_NAMES}}
    row={name:.5 for name in FEATURE_NAMES}
    assert check_distribution_support(row,support)["status"]=="within_observed_support"
    assert check_distribution_support({**row,FEATURE_NAMES[0]:.05},support)["status"]=="edge_of_observed_support"
    assert check_distribution_support({**row,FEATURE_NAMES[0]:1.1},support)["status"]=="outside_observed_support"
    assert check_distribution_support({k:v for k,v in row.items() if k!=FEATURE_NAMES[0]},support)["status"]=="missing_features"
    assert check_distribution_support({**row,FEATURE_NAMES[0]:float("nan")},support)["status"]=="invalid_features"


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
    assert metadata["dataset_sha256"]==hashlib.sha256(data.read_bytes()).hexdigest()
    assert (output / "flood_exposure_v1.joblib").is_file()
    assert (output / "evaluation.json").is_file()
    assert metadata["split_integrity"]["test_used_for_fit_or_model_selection"] is False
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
        ml_service._load_reliability_bundle.cache_clear()


def test_missing_calibrator_falls_back_to_explicit_raw_score(tmp_path, monkeypatch):
    monkeypatch.setattr(ml_service,"CALIBRATOR_PATH",tmp_path/"missing-calibrator.joblib")
    ml_service._load_reliability_bundle.cache_clear()
    try:
        info=ml_service.model_info()
        assert info.status=="ready"
        assert info.reliability_status=="degraded"
        assert info.probabilities_calibrated is False
        assert "missing" in info.calibration_status
        scenario_store=ScenarioStore(tmp_path/"fallback.sqlite3")
        monkeypatch.setattr(ml_service,"store",scenario_store)
        state=scenario_store.create(ScenarioCreate(name="Missing calibration",seed=2,preset="heavy"),"missing-calibration").state
        result=ml_service.predictions(state.id)
        assert result.reliability_status=="degraded"
        assert all(item.calibrated_synthetic_probability is None for item in result.predictions)
        assert all(item.distribution_support_status!="unavailable" for item in result.predictions)
    finally:
        ml_service._load_reliability_bundle.cache_clear()


def test_sensitivity_repeats_actual_validation_simulation_deterministically(tmp_path):
    source=ml_service.ARTIFACT_DIR
    target=tmp_path/"artifacts"; target.mkdir()
    for name in ("model_metadata.json","dataset_metadata.json","flood_exposure_v1.joblib",
                 "flood_exposure_platt_v1.joblib","distribution_support_v1.json"):
        shutil.copy2(source/name,target/name)
    metadata=json.loads((target/"model_metadata.json").read_text(encoding="utf-8"))
    validation=metadata["split_scenario_ids"]["validation"][0]
    first=run_sensitivity(target/"dataset_metadata.json",target,scenario_ids=[validation],ticks=(0,))
    second=run_sensitivity(target/"dataset_metadata.json",target,scenario_ids=[validation],ticks=(0,))
    assert first["comparisons"]==second["comparisons"]
    assert first["test_scenarios_used"]==[]
    assert len(first["comparisons"])==7
    assert all(item["scenario_id"]==validation for item in first["comparisons"])
