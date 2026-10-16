"""Local ML artifact checks and inference over the authoritative scenario state."""

from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path

import joblib
import numpy as np
import sklearn

from .city_service import generate_city
from .flood import SimulationParameters
from .ml.features import ENGINE_VERSION, FEATURE_NAMES, HORIZON_TICKS, TARGET_NAME, build_feature_rows, feature_matrix
from .ml.reliability import check_distribution_support
from .schemas import (BuildingRiskPrediction, MLDatasetInfo, MLEvaluationReport, MLFeatureContribution,
                      MLFeatureInfo, MLModelInfo, ScenarioPredictionSet, ScenarioState)
from .scenarios import ScenarioError, store

ARTIFACT_DIR = Path(__file__).resolve().parents[1] / "ml_artifacts"
MODEL_PATH = ARTIFACT_DIR / "flood_exposure_v1.joblib"
MODEL_METADATA_PATH = ARTIFACT_DIR / "model_metadata.json"
DATASET_METADATA_PATH = ARTIFACT_DIR / "dataset_metadata.json"
EVALUATION_PATH = ARTIFACT_DIR / "evaluation.json"
RELIABILITY_PATH = ARTIFACT_DIR / "reliability_evaluation.json"
SUPPORT_PATH = ARTIFACT_DIR / "distribution_support_v1.json"
CALIBRATOR_PATH = ARTIFACT_DIR / "flood_exposure_platt_v1.joblib"
SENSITIVITY_PATH = ARTIFACT_DIR / "sensitivity_evaluation.json"

FEATURE_INFO = [
    MLFeatureInfo(name="current_depth_max_m", description="Maximum current water depth over the building footprint.", units="m", role="numeric"),
    MLFeatureInfo(name="current_depth_mean_m", description="Mean current water depth over the building footprint.", units="m", role="numeric"),
    MLFeatureInfo(name="current_exposed_fraction", description="Fraction of footprint samples currently at least 0.05 m deep.", units="ratio", role="numeric"),
    MLFeatureInfo(name="neighborhood_depth_max_m", description="Maximum current depth in the surrounding 3 × 3 terrain-cell neighborhood.", units="m", role="numeric"),
    MLFeatureInfo(name="neighborhood_depth_mean_m", description="Mean current depth in the surrounding 3 × 3 neighborhood.", units="m", role="numeric"),
    MLFeatureInfo(name="neighborhood_wet_fraction_005m", description="Share of neighboring cells currently at least 0.05 m deep.", units="ratio", role="numeric"),
    MLFeatureInfo(name="neighborhood_wet_fraction_030m", description="Share of neighboring cells currently at least 0.30 m deep.", units="ratio", role="numeric"),
    MLFeatureInfo(name="terrain_elevation_m", description="Synthetic elevation at the building's terrain cell.", units="m", role="numeric"),
    MLFeatureInfo(name="terrain_neighborhood_mean_m", description="Mean synthetic elevation in the surrounding 3 × 3 neighborhood.", units="m", role="numeric"),
    MLFeatureInfo(name="distance_to_canal_m", description="Horizontal distance from building northing to the 52 m canal edge.", units="m", role="numeric"),
    MLFeatureInfo(name="river_level_m", description="Current stage-controlled canal surface elevation.", units="m", role="numeric"),
    MLFeatureInfo(name="terrain_minus_river_m", description="Building cell elevation relative to current river level.", units="m", role="numeric"),
    MLFeatureInfo(name="rainfall_mm_h", description="Current scenario rainfall intensity.", units="mm/h", role="numeric"),
    MLFeatureInfo(name="drainage_effectiveness", description="Current synthetic drainage multiplier.", units="ratio", role="numeric"),
    MLFeatureInfo(name="simulation_tick", description="Current elapsed fixed five-minute simulation tick.", units="ticks", role="numeric"),
    MLFeatureInfo(name="building_height_m", description="Static generated building height.", units="m", role="numeric"),
    MLFeatureInfo(name="building_floors", description="Static generated floor count.", units="floors", role="numeric"),
    MLFeatureInfo(name="building_width_m", description="Static generated building width.", units="m", role="numeric"),
    MLFeatureInfo(name="building_depth_m", description="Static generated building footprint depth.", units="m", role="numeric"),
    MLFeatureInfo(name="x_m", description="Building east coordinate in the fictional city grid.", units="m", role="numeric"),
    MLFeatureInfo(name="y_m", description="Building north coordinate in the fictional city grid.", units="m", role="numeric"),
    *[MLFeatureInfo(name=f"use_{use}", description=f"One-hot indicator that the generated building use is {use}.", units="binary", role="indicator")
      for use in ("residential", "commercial", "hospital", "shelter")],
]


class ModelUnavailable(RuntimeError):
    pass


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ModelUnavailable(f"Required local ML metadata is unavailable: {path.name}.") from exc


@lru_cache(maxsize=1)
def _load_model_bundle() -> tuple[dict, dict, dict, dict]:
    metadata = _read_json(MODEL_METADATA_PATH)
    dataset = _read_json(DATASET_METADATA_PATH)
    evaluation = _read_json(EVALUATION_PATH)
    try:
        artifact_bytes = MODEL_PATH.read_bytes()
    except OSError as exc:
        raise ModelUnavailable("No locally trained model artifact is installed.") from exc
    digest = hashlib.sha256(artifact_bytes).hexdigest()
    if digest != metadata.get("artifact_sha256"):
        raise ModelUnavailable("The local model artifact does not match its training metadata checksum.")
    if metadata.get("features") != FEATURE_NAMES or dataset.get("feature_names") != FEATURE_NAMES:
        raise ModelUnavailable("The saved model feature schema does not match the running service.")
    if metadata.get("engine_version") != ENGINE_VERSION:
        raise ModelUnavailable("The saved model was trained against an incompatible flood-engine version.")
    if metadata.get("scikit_learn_version") != sklearn.__version__:
        raise ModelUnavailable("The installed scikit-learn version does not match the saved artifact.")
    try:
        bundle = joblib.load(MODEL_PATH)
    except Exception as exc:
        raise ModelUnavailable("The local model artifact could not be loaded.") from exc
    if bundle.get("feature_names") != FEATURE_NAMES or bundle.get("engine_version") != ENGINE_VERSION or "estimator" not in bundle:
        raise ModelUnavailable("The artifact's embedded feature contract is incompatible.")
    return bundle, metadata, dataset, evaluation


@lru_cache(maxsize=1)
def _load_reliability_bundle() -> dict:
    """Reliability artifacts degrade explicitly without disabling the physics model."""
    warnings: list[str] = []
    try:
        _, metadata, _, _ = _load_model_bundle()
        report = _read_json(RELIABILITY_PATH)
        support = _read_json(SUPPORT_PATH)
        if report.get("model_artifact_sha256") != metadata.get("artifact_sha256"):
            raise ModelUnavailable("Reliability evidence was produced for a different model artifact.")
        if report.get("feature_schema") != FEATURE_NAMES or support.get("feature_schema") != FEATURE_NAMES:
            raise ModelUnavailable("Reliability evidence has an incompatible feature schema.")
        calibrator = None
        calibration = report.get("calibration", {})
        calibration_status = calibration.get("status", "unavailable")
        if calibration_status == "adopted":
            if not CALIBRATOR_PATH.is_file():
                warnings.append("Validated calibration metadata is present but its local artifact is missing.")
                calibration_status = "unavailable_missing_artifact"
            else:
                digest = hashlib.sha256(CALIBRATOR_PATH.read_bytes()).hexdigest()
                if digest != calibration.get("calibrator_sha256"):
                    warnings.append("The calibration artifact checksum does not match its evidence.")
                    calibration_status = "unavailable_checksum_mismatch"
                else:
                    calibrator = joblib.load(CALIBRATOR_PATH)
        elif calibration_status != "not_adopted_development_gate_failed":
            warnings.append("Calibration evidence is unavailable; raw model scores are not probabilities.")
        if calibrator is None and calibration_status == "adopted":
            calibration_status = "unavailable"
        return {"status": "available" if not warnings else "degraded", "report": report,
                "support": support, "calibrator": calibrator, "calibration_status": calibration_status,
                "warnings": warnings}
    except Exception as exc:
        return {"status": "degraded", "report": None, "support": None, "calibrator": None,
                "calibration_status": "unavailable", "warnings": [str(exc)]}


def model_info() -> MLModelInfo:
    try:
        _, metadata, _, _ = _load_model_bundle()
        reliability = _load_reliability_bundle()
        return MLModelInfo(status="ready", model_name=metadata["model_name"],
            model_version=metadata["model_version"], algorithm=metadata["algorithm"],
            trained_at_utc=metadata["created_at_utc"], training_scenarios=metadata["training_scenarios"],
            observation_count=metadata["sample_count"], horizon_ticks=metadata["prediction_horizon_ticks"],
            horizon_minutes=metadata["prediction_horizon_minutes"], target=metadata["target"],
            artifact_sha256=metadata["artifact_sha256"], sklearn_version=metadata["scikit_learn_version"],
            probabilities_calibrated=reliability["calibrator"] is not None,
            reliability_status=reliability["status"],
            calibration_status=reliability["calibration_status"],
            reliability_warnings=reliability["warnings"])
    except ModelUnavailable as exc:
        try:
            metadata = _read_json(MODEL_METADATA_PATH)
            name = metadata.get("model_name", "RESQ-AI Future Building Exposure Classifier")
            target = metadata.get("target", TARGET_NAME)
        except ModelUnavailable:
            name, target = "RESQ-AI Future Building Exposure Classifier", TARGET_NAME
        return MLModelInfo(status="unavailable", model_name=name, target=target, unavailable_reason=str(exc))


def dataset_info() -> MLDatasetInfo:
    return MLDatasetInfo.model_validate(_read_json(DATASET_METADATA_PATH))


def evaluation_info() -> MLEvaluationReport:
    return MLEvaluationReport.model_validate(_read_json(EVALUATION_PATH))


def reliability_info() -> dict:
    reliability = _load_reliability_bundle()
    if reliability["report"] is None:
        return {"status": "unavailable", "warnings": reliability["warnings"], "report": None}
    return {"status": reliability["status"], "warnings": reliability["warnings"], "report": reliability["report"]}


def sensitivity_info() -> dict:
    try:
        data = _read_json(SENSITIVITY_PATH)
        _, metadata, _, _ = _load_model_bundle()
        if data.get("model_version") != metadata.get("model_version"):
            raise ModelUnavailable("Sensitivity evidence belongs to a different model version.")
        return {"status": "available", "report": data}
    except (ModelUnavailable, OSError, json.JSONDecodeError) as exc:
        return {"status": "unavailable", "reason": str(exc), "report": None}


def feature_info() -> list[MLFeatureInfo]:
    return FEATURE_INFO


def predictions(scenario_id: str, building_id: str | None = None) -> ScenarioPredictionSet:
    scenario = store.get(scenario_id).state
    return predict_state(scenario, building_id)


def predict_state(scenario: ScenarioState, building_id: str | None = None) -> ScenarioPredictionSet:
    """Run the installed local model against an explicit immutable snapshot.

    Scenario experiments use this path so predictions never read or overwrite
    the live ScenarioStore while evaluating an isolated variant.
    """
    bundle, metadata, _, evaluation = _load_model_bundle()
    city = generate_city(scenario.seed)
    params = SimulationParameters(**scenario.parameters.model_dump())
    rows = build_feature_rows(city, np.asarray(scenario.depth_m, dtype=np.float64), scenario.seed, params, scenario.tick)
    estimator = bundle["estimator"]
    reliability = _load_reliability_bundle()
    calibrator = reliability["calibrator"]
    support = reliability["support"]
    matrix = feature_matrix(rows)
    labels = estimator.predict(matrix).astype(int)
    scores = estimator.predict_proba(matrix)[:, 1] if hasattr(estimator, "predict_proba") else estimator.decision_function(matrix)
    calibrated_scores = calibrator.predict_proba(
        (np.log(np.clip(scores, 1e-6, 1 - 1e-6) / np.clip(1 - scores, 1e-6, 1))).reshape(-1, 1)
    )[:, 1] if calibrator is not None else None
    current_by_id = {item.entity_id: item for item in scenario.impacts.buildings}
    importance = {item["feature"]: max(0.0, float(item["importance_mean"]))
                  for item in evaluation.get("permutation_importance", [])}
    top_features = sorted(importance, key=importance.get, reverse=True)[:5]
    selected_buildings = {building.id for building in city.buildings}
    if building_id is not None:
        if building_id not in selected_buildings:
            raise ScenarioError(404, "Building does not exist in the scenario city.")
        indices = [index for index, building in enumerate(city.buildings) if building.id == building_id]
    else:
        indices = list(range(len(city.buildings)))
    output = []
    for index in indices:
        building = city.buildings[index]
        current = current_by_id[building.id]
        features = [MLFeatureContribution(name=name, value=float(rows[index][name]),
            global_permutation_importance=importance.get(name, 0.0)) for name in top_features]
        support_result = check_distribution_support(rows[index], support) if support is not None else {
            "status": "unavailable", "warnings": ["Training-support metadata is unavailable; no support claim is made."],
        }
        output.append(BuildingRiskPrediction(building_id=building.id,
            current_exposed=current.water_reaches_building, current_exposure_category=current.category,
            current_max_depth_m=current.max_depth_m, predicted_future_exposed=bool(labels[index]),
            predicted_category="predicted_exposed" if labels[index] else "predicted_not_exposed",
            uncalibrated_model_score=float(scores[index]),
            calibrated_synthetic_probability=float(calibrated_scores[index]) if calibrated_scores is not None else None,
            distribution_support_status=support_result["status"],
            reliability_warnings=list(reliability["warnings"])+list(support_result.get("warnings", [])),
            influential_features=features))
    return ScenarioPredictionSet(model_version=metadata["model_version"], scenario_id=scenario.id,
        scenario_state_version=scenario.state_version, scenario_tick=scenario.tick, scenario_epoch=scenario.epoch, horizon_ticks=HORIZON_TICKS,
        horizon_minutes=HORIZON_TICKS * 5, target_definition=dataset_label(),
        probabilities_calibrated=calibrator is not None, reliability_status=reliability["status"],
        calibration_status=reliability["calibration_status"], reliability_warnings=reliability["warnings"], predictions=output)


def dataset_label() -> str:
    _, _, dataset, _ = _load_model_bundle()
    return dataset["label_definition"]
