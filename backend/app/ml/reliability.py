"""Grouped calibration and reliability evidence for the synthetic flood model.

All fitted reliability artifacts use development scenario groups only. The
saved final test groups are read only for the last report and are never used to
choose calibration or support thresholds.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from datetime import date
from pathlib import Path
from typing import Any

import joblib
import numpy as np
from sklearn.calibration import calibration_curve
from sklearn.model_selection import GroupKFold
from sklearn.metrics import (average_precision_score, brier_score_loss,
                             f1_score, log_loss, precision_score, recall_score,
                             roc_auc_score)
from sklearn.linear_model import LogisticRegression

from .features import FEATURE_NAMES, HORIZON_TICKS, TARGET_NAME, feature_matrix
from .train import ARTIFACT_DIR, _candidate_models, _score, load_rows, metrics

CALIBRATOR_PATH = ARTIFACT_DIR / "flood_exposure_platt_v1.joblib"
SUPPORT_PATH = ARTIFACT_DIR / "distribution_support_v1.json"
RELIABILITY_PATH = ARTIFACT_DIR / "reliability_evaluation.json"


def _ece(y: np.ndarray, score: np.ndarray, bins: int = 10) -> tuple[float, list[dict[str, float | int]]]:
    """Equal-width expected calibration error; bins and empty-bin policy are explicit."""
    edges = np.linspace(0.0, 1.0, bins + 1)
    bucket = np.minimum(np.digitize(score, edges[1:-1], right=False), bins - 1)
    rows: list[dict[str, float | int]] = []
    error = 0.0
    for index in range(bins):
        mask = bucket == index
        count = int(mask.sum())
        if not count:
            rows.append({"bin": index, "lower": float(edges[index]), "upper": float(edges[index + 1]), "count": 0,
                         "mean_score": 0.0, "observed_frequency": 0.0})
            continue
        mean_score = float(score[mask].mean())
        observed = float(y[mask].mean())
        error += count / len(y) * abs(mean_score - observed)
        rows.append({"bin": index, "lower": float(edges[index]), "upper": float(edges[index + 1]), "count": count,
                     "mean_score": mean_score, "observed_frequency": observed})
    return float(error), rows


def calibration_metrics(y: np.ndarray, score: np.ndarray) -> dict[str, Any]:
    clipped = np.clip(score, 1e-8, 1 - 1e-8)
    ece, diagram = _ece(y, clipped, bins=10)
    curve_observed, curve_mean = calibration_curve(y, clipped, n_bins=10, strategy="uniform")
    return {
        "brier_score": float(brier_score_loss(y, clipped)),
        "log_loss": float(log_loss(y, clipped, labels=[0, 1])),
        "expected_calibration_error": ece,
        "ece_method": "10 fixed-width [0,1] bins; empty bins omitted from weighted sum; bin counts retained",
        "reliability_diagram": diagram,
        "sklearn_reliability_curve": [{"mean_predicted": float(x), "observed_fraction": float(v)}
                                       for x, v in zip(curve_mean, curve_observed, strict=True)],
    }


def _group_balanced_weights(groups: np.ndarray) -> np.ndarray:
    unique, counts = np.unique(groups, return_counts=True)
    count_map = dict(zip(unique.tolist(), counts.tolist(), strict=True))
    return np.asarray([1.0 / count_map[group] for group in groups], dtype=float)


def _fit_platt(raw_score: np.ndarray, y: np.ndarray, groups: np.ndarray) -> LogisticRegression:
    # Work on the RF's log-odds score. Equal total weight per scenario avoids
    # treating five repeated ticks from one run as five independent scenarios.
    logit = np.log(np.clip(raw_score, 1e-6, 1 - 1e-6) / np.clip(1 - raw_score, 1e-6, 1))
    model = LogisticRegression(C=1e6, solver="lbfgs", max_iter=1000)
    model.fit(logit.reshape(-1, 1), y, sample_weight=_group_balanced_weights(groups))
    return model


def _apply_platt(model: LogisticRegression, raw_score: np.ndarray) -> np.ndarray:
    logit = np.log(np.clip(raw_score, 1e-6, 1 - 1e-6) / np.clip(1 - raw_score, 1e-6, 1))
    return model.predict_proba(logit.reshape(-1, 1))[:, 1]


def _calibration_gate(raw_metrics: dict[str, Any], calibrated_metrics: dict[str, Any]) -> bool:
    """Apply the predeclared adoption rule without consulting test metrics."""
    brier_improvement = raw_metrics["brier_score"] - calibrated_metrics["brier_score"]
    log_loss_delta = calibrated_metrics["log_loss"] - raw_metrics["log_loss"]
    return brier_improvement >= 0.001 and log_loss_delta <= 0.01


def _persist_calibrator(path: Path, calibrator: LogisticRegression | None, adopted: bool) -> str | None:
    """Persist only an adopted production calibrator; clear stale rejected artifacts."""
    if not adopted:
        path.unlink(missing_ok=True)
        return None
    if calibrator is None:
        raise ValueError("An adopted calibration gate requires a fitted production calibrator.")
    joblib.dump(calibrator, path, compress=3)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sha256_file(path: Path, *, normalize_text_newlines: bool = False) -> str:
    content = path.read_bytes()
    if normalize_text_newlines:
        content = content.replace(b"\r\n", b"\n")
    return hashlib.sha256(content).hexdigest()


def _support(rows: list[dict[str, str]], fit_groups: set[str]) -> dict[str, Any]:
    selected = [row for row in rows if row["scenario_id"] in fit_groups]
    matrix = feature_matrix(selected)
    return {
        "version": "feature-support-v1", "feature_schema": FEATURE_NAMES,
        "source": "Final estimator development scenarios only (train plus validation); final test groups excluded.",
        "per_feature": {
            name: {"min": float(np.min(matrix[:, index])), "max": float(np.max(matrix[:, index])),
                  "q005": float(np.quantile(matrix[:, index], 0.005)),
                  "q995": float(np.quantile(matrix[:, index], 0.995))}
            for index, name in enumerate(FEATURE_NAMES)
        },
    }


def _grouped_oof_scores(x: np.ndarray, y: np.ndarray, groups: np.ndarray,
                        algorithm: str, seed: int, n_splits: int = 5) -> np.ndarray:
    """Produce deterministic group-held-out scores for calibrator fitting."""
    predictions = np.full(len(groups), np.nan)
    for fit_idx, held_idx in GroupKFold(n_splits=n_splits).split(x, y, groups):
        estimator = _candidate_models(seed)[algorithm]
        estimator.fit(x[fit_idx], y[fit_idx])
        predictions[held_idx] = _score(estimator, x[held_idx])
    if not np.isfinite(predictions).all():
        raise AssertionError("Every development observation must have one group-held-out score.")
    return predictions


def _nested_grouped_calibration(x: np.ndarray, y: np.ndarray, groups: np.ndarray,
                                algorithm: str, seed: int, n_splits: int = 5
                                ) -> tuple[np.ndarray, np.ndarray, list[dict[str, Any]]]:
    """Evaluate calibration with an independent, fully nested grouped design.

    Each outer held-out group is excluded from both the outer estimator fit and
    every inner OOF/calibrator fit. The audit is persisted to make that
    separation inspectable rather than relying only on a prose assertion.
    """
    raw = np.full(len(groups), np.nan)
    calibrated = np.full(len(groups), np.nan)
    audit: list[dict[str, Any]] = []
    for outer_fit, outer_held in GroupKFold(n_splits=n_splits).split(x, y, groups):
        outer_train_groups = sorted(set(groups[outer_fit].tolist()))
        outer_validation_groups = sorted(set(groups[outer_held].tolist()))
        if set(outer_train_groups) & set(outer_validation_groups):
            raise AssertionError("Outer grouped split contains overlapping scenario IDs.")

        inner_oof = _grouped_oof_scores(x[outer_fit], y[outer_fit], groups[outer_fit],
                                        algorithm, seed, n_splits)
        calibrator = _fit_platt(inner_oof, y[outer_fit], groups[outer_fit])
        outer_estimator = _candidate_models(seed)[algorithm]
        outer_estimator.fit(x[outer_fit], y[outer_fit])
        outer_scores = _score(outer_estimator, x[outer_held])
        raw[outer_held] = outer_scores
        calibrated[outer_held] = _apply_platt(calibrator, outer_scores)
        audit.append({
            "outer_validation_groups": outer_validation_groups,
            "outer_estimator_fit_groups": outer_train_groups,
            "inner_oof_estimator_fit_groups": outer_train_groups,
            "calibrator_fit_groups": outer_train_groups,
            "inner_grouped_oof_folds": n_splits,
        })

    if not np.isfinite(raw).all() or not np.isfinite(calibrated).all():
        raise AssertionError("Every development observation must have one nested outer prediction.")
    return raw, calibrated, audit


def check_distribution_support(row: dict[str, Any], support: dict[str, Any]) -> dict[str, Any]:
    if tuple(support.get("feature_schema", ())) != tuple(FEATURE_NAMES):
        return {"status": "incompatible_schema", "warnings": ["Saved feature support does not match the running feature schema."], "out_of_support_features": []}
    missing = [name for name in FEATURE_NAMES if name not in row]
    if missing:
        return {"status": "missing_features", "warnings": [f"Missing required features: {', '.join(missing)}."], "out_of_support_features": missing}
    try:
        values = {name: float(row[name]) for name in FEATURE_NAMES}
    except (TypeError, ValueError):
        values = {}
    invalid = [name for name in FEATURE_NAMES if name not in values or not np.isfinite(values[name])]
    if invalid:
        return {"status": "invalid_features", "warnings": [f"Invalid or non-finite features: {', '.join(invalid)}."], "out_of_support_features": invalid}
    bounds = support.get("per_feature", {})
    if set(bounds) != set(FEATURE_NAMES) or any(not {"min", "max", "q005", "q995"}.issubset(bounds.get(name, {})) for name in FEATURE_NAMES):
        return {"status": "incompatible_schema", "warnings": ["Saved feature support bounds are incomplete or incompatible."], "out_of_support_features": []}
    outside = [name for name in FEATURE_NAMES if values[name] < bounds[name]["min"] or values[name] > bounds[name]["max"]]
    edge = [name for name in FEATURE_NAMES if values[name] < bounds[name]["q005"] or values[name] > bounds[name]["q995"]]
    if outside:
        status = "outside_observed_support"
        warnings = [f"Outside observed training feature support: {', '.join(outside)}."]
    elif edge:
        status = "edge_of_observed_support"
        warnings = [f"Near the tails of observed training feature support: {', '.join(edge)}."]
    else:
        status, warnings = "within_observed_support", []
    warnings.append("In-range support does not guarantee prediction accuracy; this detector is not a real-world hazard score.")
    return {"status": status, "warnings": warnings, "out_of_support_features": outside, "tail_features": edge}


def _metric_subset(rows: list[dict[str, str]], y: np.ndarray, pred: np.ndarray, score: np.ndarray,
                   mask: np.ndarray, minimum: int = 30, minimum_scenarios: int = 3) -> dict[str, Any]:
    count = int(mask.sum())
    scenario_count = len({rows[i]["scenario_id"] for i in np.flatnonzero(mask)})
    positives = int(y[mask].sum()) if count else 0
    result: dict[str, Any] = {"observation_count": count, "scenario_count": scenario_count,
                              "positive_count": positives, "negative_count": count - positives}
    if scenario_count < minimum_scenarios:
        result["status"] = "insufficient_scenario_support"
        return result
    if count < minimum or positives == 0 or positives == count:
        result["status"] = "insufficient_class_support"
        return result
    result.update(metrics(y[mask], pred[mask], score[mask]))
    result["status"] = "descriptive_synthetic_subgroup"
    return result


def _subgroups(rows: list[dict[str, str]], y: np.ndarray, pred: np.ndarray, score: np.ndarray) -> dict[str, Any]:
    values = {key: np.asarray([float(row[key]) for row in rows]) for key in
              ("rainfall_mm_h", "river_level_m", "drainage_effectiveness", "terrain_elevation_m", "distance_to_canal_m", "simulation_tick", "current_depth_max_m")}
    masks: dict[str, np.ndarray] = {"all_test": np.ones(len(rows), dtype=bool)}
    rainfall_bins = [(0, 65, "0-65"), (65, 130, "65-130"), (130, 195, "130-195"), (195, float("inf"), "195+")]
    for low, high, label in rainfall_bins:
        masks[f"rainfall_mm_h:{label}"] = (values["rainfall_mm_h"] >= low) & (values["rainfall_mm_h"] < high)
    masks.update({
        "river_stage:below_0m": values["river_level_m"] < 0,
        "river_stage:0_to_0.8m": (values["river_level_m"] >= 0) & (values["river_level_m"] < 0.8),
        "river_stage:0.8m_plus": values["river_level_m"] >= 0.8,
        "drainage:low_below_0.33": values["drainage_effectiveness"] < 0.33,
        "drainage:mid_0.33_to_0.66": (values["drainage_effectiveness"] >= 0.33) & (values["drainage_effectiveness"] < 0.66),
        "drainage:high_0.66_plus": values["drainage_effectiveness"] >= 0.66,
        "currently_dry": values["current_depth_max_m"] < 0.05,
        "newly_exposed": (values["current_depth_max_m"] < 0.05) & (y == 1),
        "near_exposure_threshold_0.03_to_0.07m": (values["current_depth_max_m"] >= 0.03) & (values["current_depth_max_m"] <= 0.07),
    })
    for tick in sorted(set(values["simulation_tick"].tolist())):
        masks[f"simulation_tick:{int(tick)}"] = values["simulation_tick"] == tick
    for feature in ("terrain_elevation_m", "distance_to_canal_m"):
        quantiles = np.quantile(values[feature], [0.25, 0.5, 0.75])
        for i, (low, high) in enumerate(zip([-np.inf, *quantiles], [*quantiles, np.inf], strict=True), 1):
            masks[f"{feature}:q{i}"] = (values[feature] >= low) & (values[feature] <= high if i == 4 else values[feature] < high)
    return {name: _metric_subset(rows, y, pred, score, mask) for name, mask in masks.items()}


def run_reliability(dataset_path: Path, artifact_dir: Path = ARTIFACT_DIR, seed: int = 92021) -> dict[str, Any]:
    rows = load_rows(dataset_path)
    metadata = json.loads((artifact_dir / "model_metadata.json").read_text(encoding="utf-8"))
    dataset_metadata = json.loads((artifact_dir / "dataset_metadata.json").read_text(encoding="utf-8"))
    dataset_sha = hashlib.sha256(dataset_path.read_bytes()).hexdigest()
    if metadata.get("dataset_sha256") != dataset_sha or dataset_metadata.get("csv_sha256") != dataset_sha:
        raise ValueError("Training, generation, and CSV checksums do not agree.")
    groups = np.asarray([row["scenario_id"] for row in rows])
    y = np.asarray([int(row[TARGET_NAME]) for row in rows], dtype=int)
    x = feature_matrix(rows)
    split = metadata["split_scenario_ids"]
    dev_groups, test_groups = set(split["train"] + split["validation"]), set(split["test"])
    if dev_groups & test_groups or set(groups) != dev_groups | test_groups:
        raise ValueError("Dataset groups do not exactly match the saved leak-free split.")
    dev_idx = np.flatnonzero(np.isin(groups, list(dev_groups)))
    test_idx = np.flatnonzero(np.isin(groups, list(test_groups)))
    dev_x, dev_y, dev_groups_array = x[dev_idx], y[dev_idx], groups[dev_idx]
    outer_raw, outer_calibrated, fold_audit = _nested_grouped_calibration(
        dev_x, dev_y, dev_groups_array, metadata["algorithm"], seed, n_splits=5)
    raw_oof_metrics = calibration_metrics(dev_y, outer_raw)
    nested_oof_metrics = calibration_metrics(dev_y, outer_calibrated)
    brier_improvement = raw_oof_metrics["brier_score"] - nested_oof_metrics["brier_score"]
    log_loss_delta = nested_oof_metrics["log_loss"] - raw_oof_metrics["log_loss"]
    adopt = _calibration_gate(raw_oof_metrics, nested_oof_metrics)

    artifact_dir.mkdir(parents=True, exist_ok=True)
    calibrator_path = artifact_dir / CALIBRATOR_PATH.name
    if adopt:
        # Production calibrator fit: full development-only grouped OOF scores.
        # This artifact is separate from the nested adoption evaluation above.
        production_oof = _grouped_oof_scores(dev_x, dev_y, dev_groups_array,
                                             metadata["algorithm"], seed, n_splits=5)
        final_calibrator = _fit_platt(production_oof, dev_y, dev_groups_array)
        calibration_artifact_sha = _persist_calibrator(calibrator_path, final_calibrator, adopted=True)
    else:
        calibration_artifact_sha = _persist_calibrator(calibrator_path, None, adopted=False)

    final_estimator = joblib.load(artifact_dir / metadata["artifact_file"])["estimator"]
    test_scores = _score(final_estimator, x[test_idx])
    test_pred = final_estimator.predict(x[test_idx]).astype(int)
    test_rows = [rows[index] for index in test_idx]
    test_y = y[test_idx]
    test_groups_array = groups[test_idx]
    raw_test_cal = calibration_metrics(test_y, test_scores)
    all_calibrated_scores = _apply_platt(final_calibrator, test_scores) if adopt else None
    calibrated_test_cal = calibration_metrics(test_y, all_calibrated_scores) if adopt else None
    support = _support(rows, dev_groups)
    support_path = artifact_dir / SUPPORT_PATH.name
    support_path.write_bytes((json.dumps(support, indent=2) + "\n").encode("utf-8"))

    # Latency is measured on a representative 360-building scenario, warmed
    # first; timings are environment dependent and include local NumPy/sklearn.
    batch = x[test_idx[: min(360, len(test_idx))]]
    probe_rows = [rows[i] for i in dev_idx[: len(batch)]]
    for _ in range(3):
        raw = _score(final_estimator, batch)
        if adopt:
            _apply_platt(final_calibrator, raw)
        for row in probe_rows:
            check_distribution_support(row, support)
    repeats = 30
    started = time.perf_counter_ns()
    for _ in range(repeats):
        raw = _score(final_estimator, batch)
    model_ms = (time.perf_counter_ns() - started) / 1e6 / repeats
    started = time.perf_counter_ns()
    for _ in range(repeats):
        if adopt:
            _apply_platt(final_calibrator, raw)
    calibration_ms = ((time.perf_counter_ns() - started) / 1e6 / repeats) if adopt else None
    started = time.perf_counter_ns()
    for _ in range(repeats):
        [check_distribution_support(row, support) for row in probe_rows]
    support_ms = (time.perf_counter_ns() - started) / 1e6 / repeats

    raw_test_order = np.argsort(np.argsort(test_scores))
    calibrated_test_order = np.argsort(np.argsort(all_calibrated_scores)) if adopt else None
    ranking_flip_fraction = float(np.mean(raw_test_order != calibrated_test_order)) if adopt else None
    failures: dict[str, list[dict[str, Any]]] = {"false_positives": [], "false_negatives": []}
    for local, index in enumerate(test_idx):
        kind = "false_positives" if test_pred[local] == 1 and test_y[local] == 0 else "false_negatives" if test_pred[local] == 0 and test_y[local] == 1 else None
        if kind and len(failures[kind]) < 12:
            row = rows[index]
            failures[kind].append({"scenario_id": row["scenario_id"], "scenario_seed": int(row["scenario_seed"]),
                "tick": int(row["observation_tick"]), "building_id": row["building_id"], "actual": int(test_y[local]),
                "predicted": int(test_pred[local]), "raw_score_uncalibrated": float(test_scores[local]),
                "calibrated_synthetic_probability": float(all_calibrated_scores[local]) if adopt else None,
                "relevant_features": {name: float(row[name]) for name in ("current_depth_max_m", "neighborhood_depth_max_m",
                    "rainfall_mm_h", "river_level_m", "drainage_effectiveness", "terrain_elevation_m", "distance_to_canal_m", "simulation_tick")}})
    newly_dry = np.asarray([float(row["current_depth_max_m"]) < 0.05 for row in test_rows])
    newly_y = test_y[newly_dry]
    newly_pred = test_pred[newly_dry]
    newly = {"definition": "current footprint max depth <0.05 m and future target is exposure within 30 simulated minutes",
             "observation_count_currently_dry": int(newly_dry.sum()),
             "positive_newly_exposed_count": int(newly_y.sum()), "scenario_count": len(set(test_groups_array[newly_dry]))}
    if len(np.unique(newly_y)) == 2:
        newly.update({"precision": float(precision_score(newly_y, newly_pred, zero_division=0)),
                      "recall": float(recall_score(newly_y, newly_pred, zero_division=0)),
                      "f1": float(f1_score(newly_y, newly_pred, zero_division=0)),
                      "false_negative_count": int(np.sum((newly_y == 1) & (newly_pred == 0)))})
    else:
        newly["status"] = "insufficient_class_support"

    # Held-out observed support rate is a false-alert characterization only;
    # intentional sensitivity variants are generated by the separate CLI.
    statuses = [check_distribution_support(row, support)["status"] for row in test_rows]
    report = {
        "version": "ml-reliability-v2", "model_version": metadata["model_version"],
        "model_artifact_sha256": metadata["artifact_sha256"], "feature_schema": FEATURE_NAMES,
        "dataset_sha256": dataset_sha, "dataset_configuration": dataset_metadata["configuration"],
        "split_scenario_ids": split, "calibration": {
            "method": "Platt sigmoid on raw random-forest probability log-odds; production fit uses 5-fold GroupKFold OOF scores over development groups; equal total sample weight per scenario",
            "test_groups_used_for_fit_or_choice": False,
            "adoption_rule": "Adopt only if fully nested outer development scenario-group Brier improves by at least 0.001 and log loss is no more than 0.01 worse. This rule was fixed before final test evaluation.",
            "status": "adopted" if adopt else "not_adopted_development_gate_failed",
            "calibrator_artifact": calibrator_path.name if adopt else None,
            "calibrator_sha256": calibration_artifact_sha,
            "development_nested_outer_raw": raw_oof_metrics,
            "development_nested_outer_calibrated": nested_oof_metrics,
            "development_brier_improvement": brier_improvement,
            "development_log_loss_delta": log_loss_delta,
            "nested_group_fold_audit": fold_audit,
            "production_calibrator_fit_groups": sorted(dev_groups) if adopt else [],
            "production_calibrator_oof_folds": 5 if adopt else None,
            "final_held_out_raw": raw_test_cal, "final_held_out_platt": calibrated_test_cal,
            "held_out_classification_at_threshold_0_5": {
                "uncalibrated": metrics(test_y, test_pred, test_scores),
                "platt_calibrated": metrics(test_y, (all_calibrated_scores >= 0.5).astype(int), all_calibrated_scores) if adopt else None,
            },
            "ranking_auc_unchanged_by_monotonic_sigmoid": float(roc_auc_score(test_y, all_calibrated_scores)) if adopt else None,
            "ranking_order_change_fraction_test": ranking_flip_fraction,
            "probability_scope": "Synthetic simulator label only; not real-world flood probability.",
        },
        "held_out_failure_analysis": {"test_observation_count": int(len(test_idx)),
            "test_scenario_count": len(test_groups), "subgroups": _subgroups(test_rows, test_y, test_pred, test_scores),
            "newly_exposed": newly, **failures,
            "dependence_note": "Building-tick rows within a scenario are repeated and spatially related; subgroup counts are descriptive and do not imply independent observations."},
        "distribution_support": {"method": "Per-feature training/development min-max plus 0.5th/99.5th percentile tail flags; missing, invalid, and schema mismatch have separate states.",
            "test_support_counts": {status: statuses.count(status) for status in sorted(set(statuses))},
            "limitations": "Marginal support only; correlations can be implausible while every feature remains individually in range. In-support does not guarantee accuracy; this is not an independently validated hazard score."},
        "artifact_integrity": {
            "dataset_sha256": dataset_sha,
            "model_artifact_sha256": hashlib.sha256((artifact_dir / metadata["artifact_file"]).read_bytes()).hexdigest(),
            "model_metadata_sha256": _sha256_file(artifact_dir / "model_metadata.json", normalize_text_newlines=True),
            "calibrator_sha256": calibration_artifact_sha,
            "support_sha256": hashlib.sha256(support_path.read_bytes()).hexdigest(),
        },
        "runtime_metadata": {"python_version": __import__("platform").python_version(),
            "numpy_version": np.__version__, "scikit_learn_version": __import__("sklearn").__version__,
            "seed": seed, "outer_group_folds": 5, "inner_group_folds": 5},
        "performance": {"batch_size": int(len(batch)), "repetitions": repeats,
            "original_model_batch_ms": model_ms, "calibrator_batch_ms": calibration_ms,
            "support_check_batch_ms": support_ms,
            "measurement_note": "Warmed local process timing; environment-specific; batch covers one generated city."},
        "evaluation_date": date.today().isoformat(), "scikit_learn_version": __import__("sklearn").__version__,
    }
    (artifact_dir / RELIABILITY_PATH.name).write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Build grouped, synthetic-only reliability evidence for the saved flood classifier.")
    parser.add_argument("--dataset", type=Path, default=Path("data/ml/flood_exposure.csv"))
    parser.add_argument("--artifacts", type=Path, default=ARTIFACT_DIR)
    parser.add_argument("--seed", type=int, default=92021)
    args = parser.parse_args()
    report = run_reliability(args.dataset, args.artifacts, args.seed)
    print(json.dumps({"calibration_status": report["calibration"]["status"],
        "nested_development_brier_raw": report["calibration"]["development_nested_outer_raw"]["brier_score"],
        "nested_development_brier_platt": report["calibration"]["development_nested_outer_calibrated"]["brier_score"],
        "test_raw": report["calibration"]["final_held_out_raw"],
        "test_platt": report["calibration"]["final_held_out_platt"],
        "newly_exposed": report["held_out_failure_analysis"]["newly_exposed"],
        "performance": report["performance"]}, indent=2))


if __name__ == "__main__":
    main()
