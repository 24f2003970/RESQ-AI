"""Train and evaluate local classifiers with whole-scenario holdouts."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import sklearn
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (average_precision_score, balanced_accuracy_score, brier_score_loss,
                             confusion_matrix, f1_score, precision_score, recall_score, roc_auc_score)
from sklearn.model_selection import GroupShuffleSplit
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.tree import DecisionTreeClassifier

from .features import ENGINE_VERSION, FEATURE_NAMES, HORIZON_TICKS, TARGET_NAME, feature_matrix, heuristic_prediction, heuristic_score

ARTIFACT_DIR = Path("ml_artifacts")
MODEL_PATH = ARTIFACT_DIR / "flood_exposure_v1.joblib"


def load_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    required = {"scenario_id", "scenario_seed", "observation_tick", "building_id", TARGET_NAME, *FEATURE_NAMES}
    if not rows or not required.issubset(rows[0]):
        raise ValueError("Dataset is empty or missing the expected feature/label schema.")
    return rows


def metrics(y_true: np.ndarray, y_pred: np.ndarray, scores: np.ndarray | None = None) -> dict:
    cm = confusion_matrix(y_true, y_pred, labels=[0, 1])
    output = {
        "precision": float(precision_score(y_true, y_pred, zero_division=0)),
        "recall": float(recall_score(y_true, y_pred, zero_division=0)),
        "f1": float(f1_score(y_true, y_pred, zero_division=0)),
        "balanced_accuracy": float(balanced_accuracy_score(y_true, y_pred)),
        "support": {"negative": int(np.sum(y_true == 0)), "positive": int(np.sum(y_true == 1))},
        "confusion_matrix": {"true_negative": int(cm[0, 0]), "false_positive": int(cm[0, 1]),
                             "false_negative": int(cm[1, 0]), "true_positive": int(cm[1, 1])},
        "roc_auc": float(roc_auc_score(y_true, scores)) if scores is not None and len(np.unique(y_true)) == 2 else None,
        "pr_auc_average_precision": float(average_precision_score(y_true, scores)) if scores is not None and len(np.unique(y_true)) == 2 else None,
        "brier_score_uncalibrated": float(brier_score_loss(y_true, scores))
        if scores is not None and np.all((scores >= 0) & (scores <= 1)) else None,
    }
    return output


def _score(model, x: np.ndarray) -> np.ndarray:
    return model.predict_proba(x)[:, 1] if hasattr(model, "predict_proba") else model.decision_function(x)


def _candidate_models(seed: int) -> dict[str, object]:
    return {
        "logistic_regression": make_pipeline(StandardScaler(), LogisticRegression(max_iter=1200, class_weight="balanced", random_state=seed)),
        "decision_tree_depth_5": DecisionTreeClassifier(max_depth=5, min_samples_leaf=8, class_weight="balanced", random_state=seed),
        "decision_tree_depth_9": DecisionTreeClassifier(max_depth=9, min_samples_leaf=5, class_weight="balanced", random_state=seed),
        "random_forest": RandomForestClassifier(n_estimators=64, max_depth=12, min_samples_leaf=4,
            class_weight="balanced_subsample", n_jobs=1, random_state=seed),
    }


def _write_svg(path: Path, test_metrics: dict, importances: list[dict]) -> None:
    width, height = 980, 620
    colors = {"ink": "#dce8e7", "muted": "#91a7a8", "accent": "#7de2bd", "panel": "#182527", "blue": "#4ca7dd"}
    matrix = test_metrics["confusion_matrix"]
    max_count = max(1, *matrix.values())
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}">',
             f'<rect width="{width}" height="{height}" rx="20" fill="#0d1719"/>',
             f'<text x="40" y="48" fill="{colors["ink"]}" font-family="Arial" font-size="24">Held-out test · future building exposure</text>',
             f'<text x="40" y="80" fill="{colors["muted"]}" font-family="Arial" font-size="14">Confusion matrix · actual rows / predicted columns</text>']
    labels = [("true_negative", 0, 0), ("false_positive", 0, 1), ("false_negative", 1, 0), ("true_positive", 1, 1)]
    for key, row, col in labels:
        x, y = 54 + col * 140, 118 + row * 110
        value = matrix[key]
        opacity = 0.12 + 0.75 * value / max_count
        fill = colors["accent"] if row == col else "#ef8f79"
        parts.extend([f'<rect x="{x}" y="{y}" width="126" height="96" rx="12" fill="{fill}" opacity="{opacity:.3f}"/>',
                      f'<text x="{x+16}" y="{y+40}" fill="{colors["ink"]}" font-family="Arial" font-size="26">{value}</text>',
                      f'<text x="{x+16}" y="{y+68}" fill="{colors["muted"]}" font-family="Arial" font-size="12">{key.replace("_", " ")}</text>'])
    parts.append(f'<text x="390" y="104" fill="{colors["muted"]}" font-family="Arial" font-size="14">Permutation importance · test set</text>')
    for index, item in enumerate(importances[:12]):
        y = 133 + index * 35
        label = item["feature"]
        value = max(0.0, item["importance_mean"])
        bar_width = min(350, value * 1300)
        parts.extend([f'<text x="390" y="{y+13}" fill="{colors["ink"]}" font-family="Arial" font-size="12">{label}</text>',
                      f'<rect x="595" y="{y}" width="{bar_width:.1f}" height="17" rx="7" fill="{colors["blue"]}"/>',
                      f'<text x="{605+bar_width:.1f}" y="{y+13}" fill="{colors["muted"]}" font-family="Arial" font-size="11">{value:.3f}</text>'])
    parts.extend([f'<text x="40" y="390" fill="{colors["ink"]}" font-family="Arial" font-size="16">F1 {test_metrics["f1"]:.3f} · balanced accuracy {test_metrics["balanced_accuracy"]:.3f}</text>',
                  f'<text x="40" y="420" fill="{colors["muted"]}" font-family="Arial" font-size="13">Synthetic simulator labels · grouped held-out scenarios · scores are not calibrated probabilities</text>',
                  "</svg>"])
    path.write_text("\n".join(parts), encoding="utf-8")


def train(dataset_path: Path, metadata_path: Path, artifact_dir: Path = ARTIFACT_DIR, seed: int = 92021) -> dict:
    rows = load_rows(dataset_path)
    dataset_sha256 = hashlib.sha256(dataset_path.read_bytes()).hexdigest()
    dataset_metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    if dataset_metadata.get("csv_sha256") and dataset_metadata["csv_sha256"] != dataset_sha256:
        raise ValueError("Dataset CSV checksum does not match its generation metadata.")
    if dataset_metadata.get("feature_names") != FEATURE_NAMES or dataset_metadata.get("target_name") != TARGET_NAME:
        raise ValueError("Dataset provenance metadata is incompatible with the training schema.")
    groups = np.asarray([row["scenario_id"] for row in rows])
    unique_groups = np.unique(groups)
    if len(unique_groups) < 20:
        raise ValueError("At least 20 unique scenario groups are required.")
    y = np.asarray([int(row[TARGET_NAME]) for row in rows], dtype=np.int64)
    x = feature_matrix(rows)
    if not np.isfinite(x).all() or set(np.unique(y)) != {0, 1}:
        raise ValueError("Features must be finite and dataset must contain both label classes.")

    outer = GroupShuffleSplit(n_splits=1, test_size=0.20, random_state=seed)
    trainval_indices, test_indices = next(outer.split(x, y, groups))
    inner = GroupShuffleSplit(n_splits=1, test_size=0.25, random_state=seed + 1)
    train_relative, val_relative = next(inner.split(x[trainval_indices], y[trainval_indices], groups[trainval_indices]))
    train_indices = trainval_indices[train_relative]
    val_indices = trainval_indices[val_relative]
    split_groups = {
        "train": sorted(set(groups[train_indices])),
        "validation": sorted(set(groups[val_indices])),
        "test": sorted(set(groups[test_indices])),
    }
    sets = [set(value) for value in split_groups.values()]
    if any(sets[i] & sets[j] for i in range(3) for j in range(i + 1, 3)):
        raise AssertionError("Scenario groups leaked across train/validation/test splits.")

    candidate_results = {}
    best_name = None
    best_key = (-1.0, -1.0, -1.0)
    for name, model in _candidate_models(seed).items():
        model.fit(x[train_indices], y[train_indices])
        val_scores = _score(model, x[val_indices])
        val_pred = (val_scores >= 0.5).astype(int) if name == "logistic_regression" or hasattr(model, "predict_proba") else model.predict(x[val_indices])
        result = metrics(y[val_indices], val_pred, val_scores)
        candidate_results[name] = result
        rank = (result["f1"], result["pr_auc_average_precision"] or 0.0, result["balanced_accuracy"])
        if rank > best_key:
            best_name, best_key = name, rank

    dummy = DummyClassifier(strategy="prior")
    dummy.fit(x[train_indices], y[train_indices])
    heuristic_scores = np.asarray([heuristic_score(row) for row in rows], dtype=float)
    heuristic_pred = np.asarray([heuristic_prediction(row) for row in rows], dtype=int)
    dummy_scores = dummy.predict_proba(x[test_indices])[:, 1]
    dummy_test = metrics(y[test_indices], dummy.predict(x[test_indices]), dummy_scores)
    heuristic_test = metrics(y[test_indices], heuristic_pred[test_indices], heuristic_scores[test_indices])

    best = _candidate_models(seed)[best_name]
    fit_indices = np.concatenate((train_indices, val_indices))
    best.fit(x[fit_indices], y[fit_indices])
    test_scores = _score(best, x[test_indices])
    test_pred = best.predict(x[test_indices]).astype(int)
    test_metrics = metrics(y[test_indices], test_pred, test_scores)
    latency_inputs = x[test_indices]
    best.predict(latency_inputs[:1])
    repetitions = 25
    started = time.perf_counter_ns()
    for _ in range(repetitions):
        best.predict(latency_inputs)
    inference_ms_per_observation = (time.perf_counter_ns() - started) / 1e6 / repetitions / len(latency_inputs)

    importance_result = permutation_importance(best, x[test_indices], y[test_indices], n_repeats=3,
        random_state=seed, scoring="average_precision" if len(np.unique(y[test_indices])) > 1 else "balanced_accuracy", n_jobs=1)
    importances = sorted([{"feature": name, "importance_mean": float(mean), "importance_std": float(std)}
                          for name, mean, std in zip(FEATURE_NAMES, importance_result.importances_mean,
                                                     importance_result.importances_std, strict=True)],
                         key=lambda item: item["importance_mean"], reverse=True)

    failures = {"false_positives": [], "false_negatives": []}
    for row_index, pred, score in zip(test_indices, test_pred, test_scores, strict=True):
        actual = int(y[row_index])
        key = "false_positives" if pred == 1 and actual == 0 else "false_negatives" if pred == 0 and actual == 1 else None
        if key and len(failures[key]) < 8:
            row = rows[row_index]
            failures[key].append({"scenario_id": row["scenario_id"], "scenario_seed": int(row["scenario_seed"]),
                "tick": int(row["observation_tick"]), "building_id": row["building_id"],
                "actual": actual, "predicted": int(pred), "model_score_uncalibrated": float(score)})

    artifact_dir.mkdir(parents=True, exist_ok=True)
    model_path = artifact_dir / "flood_exposure_v1.joblib"
    joblib.dump({"estimator": best, "feature_names": FEATURE_NAMES, "engine_version": ENGINE_VERSION}, model_path, compress=3)
    artifact_hash = hashlib.sha256(model_path.read_bytes()).hexdigest()
    training = {
        "model_name": "RESQ-AI Future Building Exposure Classifier",
        "model_version": "1.0.0",
        "algorithm": best_name,
        "artifact_file": model_path.name,
        "artifact_sha256": artifact_hash,
        "artifact_size_bytes": model_path.stat().st_size,
        "dataset_sha256": dataset_sha256,
        "dataset_configuration": dataset_metadata.get("configuration", {}),
        "dataset_version": dataset_metadata.get("dataset_version"),
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "scikit_learn_version": sklearn.__version__,
        "engine_version": ENGINE_VERSION,
        "features": FEATURE_NAMES,
        "target": TARGET_NAME,
        "prediction_horizon_ticks": HORIZON_TICKS,
        "prediction_horizon_minutes": HORIZON_TICKS * 5,
        "random_state": seed,
        "training_configuration": {"selection_metric": "validation F1, then validation PR-AUC, then balanced accuracy",
            "candidates": list(candidate_results), "test_size_by_scenarios": 0.20,
            "validation_fraction_of_trainval_scenarios": 0.25, "probabilities_calibrated": False},
        "sample_count": len(rows),
        "scenario_count": len(unique_groups),
        "training_scenarios": len(split_groups["train"]) + len(split_groups["validation"]),
        "split_scenario_ids": split_groups,
        "split_integrity": {"group_key": "scenario_id", "train_groups": len(split_groups["train"]),
            "validation_groups": len(split_groups["validation"]), "test_groups": len(split_groups["test"]),
            "overlap_count": 0, "test_used_for_fit_or_model_selection": False},
    }
    evaluation = {
        "evaluation_version": "future-exposure-eval-v1",
        "created_at_utc": training["created_at_utc"],
        "selected_model": best_name,
        "selection_metric": "validation F1, then PR-AUC, then balanced accuracy",
        "validation_candidates": candidate_results,
        "test_set_label": "Unseen scenario IDs and simulation seeds; held out until final evaluation.",
        "test_scenario_count": len(split_groups["test"]),
        "test_observation_count": int(len(test_indices)),
        "test_positive_count": int(np.sum(y[test_indices] == 1)),
        "test_negative_count": int(np.sum(y[test_indices] == 0)),
        "test_metrics": test_metrics,
        "test_baselines": {"dummy_prior": dummy_test, "transparent_local_forecast_heuristic": heuristic_test},
        "false_positive_examples": failures["false_positives"],
        "false_negative_examples": failures["false_negatives"],
        "permutation_importance": importances,
        "probabilities_calibrated": False,
        "model_score_note": "Classifier scores are uncalibrated; the product does not present them as probabilities or operational certainty.",
        "inference_latency_ms_per_observation": inference_ms_per_observation,
        "latency_batch_size": int(len(latency_inputs)),
        "latency_repetitions": repetitions,
        "test_scenario_ids": split_groups["test"],
    }
    (artifact_dir / "model_metadata.json").write_text(json.dumps(training, indent=2), encoding="utf-8")
    (artifact_dir / "evaluation.json").write_text(json.dumps(evaluation, indent=2), encoding="utf-8")
    _write_svg(artifact_dir / "evaluation.svg", test_metrics, importances)
    return {"training": training, "evaluation": evaluation}


def main() -> None:
    parser = argparse.ArgumentParser(description="Train a local future flood-exposure classifier.")
    parser.add_argument("--dataset", type=Path, default=Path("data/ml/flood_exposure.csv"))
    parser.add_argument("--dataset-metadata", type=Path, default=ARTIFACT_DIR / "dataset_metadata.json")
    parser.add_argument("--artifacts", type=Path, default=ARTIFACT_DIR)
    parser.add_argument("--seed", type=int, default=92021)
    args = parser.parse_args()
    result = train(args.dataset, args.dataset_metadata, args.artifacts, args.seed)
    print(json.dumps({"selected_model": result["training"]["algorithm"],
                      "test_metrics": result["evaluation"]["test_metrics"],
                      "test_baselines": result["evaluation"]["test_baselines"],
                      "latency_ms": result["evaluation"]["inference_latency_ms_per_observation"]}, indent=2))


if __name__ == "__main__":
    main()
