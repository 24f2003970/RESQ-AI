"""Deterministic forcing sensitivity from actual flood-simulation variants."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

import joblib
import numpy as np
from scipy.stats import spearmanr

from ..city_service import generate_city
from ..flood import SimulationParameters, initial_depth, step
from .features import (ENGINE_VERSION, FEATURE_NAMES, HORIZON_TICKS,
                       build_feature_rows, feature_matrix, target_exposed)
from .reliability import (ARTIFACT_DIR, CALIBRATOR_PATH, SUPPORT_PATH,
                          RELIABILITY_PATH, _apply_platt,
                          check_distribution_support)

SENSITIVITY_PATH = Path("sensitivity_evaluation.json")


def _snapshot(seed: int, params: SimulationParameters, tick: int) -> tuple[Any, np.ndarray]:
    city = generate_city(seed)
    depth = initial_depth(seed, params.river_level_m)
    if tick:
        depth, _ = step(depth, seed, params, steps=tick)
    return city, depth


def _evaluate(seed: int, params: SimulationParameters, tick: int, model: Any, calibrator: Any,
              support: dict[str, Any]) -> dict[str, Any]:
    city, depth = _snapshot(seed, params, tick)
    rows = build_feature_rows(city, depth, seed, params, tick)
    matrix = feature_matrix(rows)
    score = model.predict_proba(matrix)[:, 1]
    pred = model.predict(matrix).astype(int)
    future, _ = step(depth, seed, params, steps=HORIZON_TICKS)
    truth_map = target_exposed(city, future, seed, params.river_level_m)
    truth = np.asarray([truth_map[item.id] for item in city.buildings], dtype=int)
    calibrated = _apply_platt(calibrator, score) if calibrator is not None else None
    statuses = [check_distribution_support(row, support)["status"] for row in rows]
    return {"rows": rows, "score": score, "prediction": pred, "truth": truth, "calibrated": calibrated,
            "support_status_counts": {status: statuses.count(status) for status in sorted(set(statuses))}}


def _variants(params: SimulationParameters) -> list[dict[str, Any]]:
    # Deltas are applied to the scenario forcing before the deterministic flood
    # engine is rerun from its initial state. They never edit correlated feature
    # columns independently.
    definitions = [
        ("rainfall_small_plus_5_mm_h", "rainfall_mm_h", 5.0),
        ("rainfall_large_plus_30_mm_h", "rainfall_mm_h", 30.0),
        ("river_small_plus_0.03_m", "river_level_m", 0.03),
        ("river_large_plus_0.15_m", "river_level_m", 0.15),
        ("drainage_small_minus_0.05", "drainage_effectiveness", -0.05),
        ("drainage_large_minus_0.20", "drainage_effectiveness", -0.20),
    ]
    output = []
    for name, feature, delta in definitions:
        changed = asdict(params)
        changed[feature] = float(changed[feature] + delta)
        if feature == "drainage_effectiveness":
            changed[feature] = float(np.clip(changed[feature], 0.05, 1.0))
            delta = changed[feature] - params.drainage_effectiveness
        output.append({"name": name, "feature": feature, "requested_delta": delta,
                       "parameters": SimulationParameters(**changed)})
    return output


def run_sensitivity(dataset_metadata_path: Path, artifact_dir: Path = ARTIFACT_DIR,
                    scenario_ids: list[str] | None = None, ticks: tuple[int, ...] = (0, 6, 12)) -> dict[str, Any]:
    metadata = json.loads(dataset_metadata_path.read_text(encoding="utf-8"))
    model_metadata = json.loads((artifact_dir / "model_metadata.json").read_text(encoding="utf-8"))
    if model_metadata.get("engine_version") != ENGINE_VERSION or model_metadata.get("features") != FEATURE_NAMES:
        raise ValueError("Sensitivity model feature or engine contract mismatch.")
    model = joblib.load(artifact_dir / model_metadata["artifact_file"])["estimator"]
    calibrator_path = artifact_dir / CALIBRATOR_PATH.name
    calibrator = joblib.load(calibrator_path) if calibrator_path.exists() else None
    support = json.loads((artifact_dir / SUPPORT_PATH.name).read_text(encoding="utf-8"))
    seeds = metadata["simulation_seeds"]
    split = model_metadata["split_scenario_ids"]
    chosen_ids = scenario_ids or split["validation"][:3]
    if not set(chosen_ids).issubset(set(split["validation"])):
        raise ValueError("Sensitivity probes must use validation scenarios, never final test scenarios.")
    by_id = {item["scenario_id"]: item for item in seeds}
    comparisons = []
    for scenario_id in chosen_ids:
        item = by_id[scenario_id]
        seed = int(item["seed"])
        base_params = SimulationParameters(**item["parameters"])
        for tick in ticks:
            base = _evaluate(seed, base_params, tick, model, calibrator, support)
            comparisons.append({"scenario_id": scenario_id, "seed": seed, "tick": tick, "variant": "baseline",
                "intervention": None, "prediction_flip_fraction_vs_baseline": 0.0,
                "rank_spearman_vs_baseline": 1.0, "predicted_positive_count": int(base["prediction"].sum()),
                "delta_predicted_positive_count": 0, "truth_positive_count": int(base["truth"].sum()),
                "f1": float(__import__("sklearn.metrics", fromlist=["f1_score"]).f1_score(base["truth"], base["prediction"], zero_division=0)),
                "calibrated_probability_mean": float(base["calibrated"].mean()) if base["calibrated"] is not None else None,
                "support_status_counts": base["support_status_counts"]})
            for variant in _variants(base_params):
                altered = _evaluate(seed, variant["parameters"], tick, model, calibrator, support)
                correlation = (spearmanr(base["score"], altered["score"]).statistic
                               if np.ptp(base["score"]) > 1e-12 and np.ptp(altered["score"]) > 1e-12 else None)
                comparisons.append({"scenario_id": scenario_id, "seed": seed, "tick": tick,
                    "variant": variant["name"], "intervention": {"parameter": variant["feature"],
                        "delta": float(variant["requested_delta"]), "before": float(getattr(base_params, variant["feature"])),
                        "after": float(getattr(variant["parameters"], variant["feature"]))},
                    "prediction_flip_fraction_vs_baseline": float(np.mean(base["prediction"] != altered["prediction"])),
                    "rank_spearman_vs_baseline": float(correlation) if correlation is not None and np.isfinite(correlation) else None,
                    "predicted_positive_count": int(altered["prediction"].sum()),
                    "delta_predicted_positive_count": int(altered["prediction"].sum() - base["prediction"].sum()),
                    "truth_positive_count": int(altered["truth"].sum()),
                    "f1": float(__import__("sklearn.metrics", fromlist=["f1_score"]).f1_score(altered["truth"], altered["prediction"], zero_division=0)),
                    "calibrated_probability_mean": float(altered["calibrated"].mean()) if altered["calibrated"] is not None else None,
                    "support_status_counts": altered["support_status_counts"]})
    report = {"version": "simulation-sensitivity-v1", "model_version": model_metadata["model_version"],
        "dataset_engine_version": metadata["engine_version"], "test_scenarios_used": [],
        "validation_scenarios": [{"scenario_id": by_id[item]["scenario_id"], "seed": by_id[item]["seed"],
            "parameters": by_id[item]["parameters"]} for item in chosen_ids],
        "ticks": list(ticks), "intervention_method": "Change one scenario forcing parameter at a time, rerun the deterministic flood engine from initial depth to the target tick, then recompute model features and 30-minute simulator labels.",
        "base_parameters_sampled_within_training_synthetic_ranges": True,
        "interpretation": "Prediction changes measure sensitivity, not error. Stable outputs do not establish accuracy. Results describe a small deterministic synthetic validation probe, not real flood behavior.",
        "comparisons": comparisons,
        "summary": {"comparison_count": len(comparisons),
            "mean_nonbaseline_flip_fraction": float(np.mean([x["prediction_flip_fraction_vs_baseline"] for x in comparisons if x["variant"] != "baseline"])),
            "mean_nonbaseline_spearman": (float(np.mean([x["rank_spearman_vs_baseline"] for x in comparisons if x["variant"] != "baseline" and x["rank_spearman_vs_baseline"] is not None]))
                if any(x["variant"] != "baseline" and x["rank_spearman_vs_baseline"] is not None for x in comparisons) else None),
            "undefined_rank_pairs": sum(x["variant"] != "baseline" and x["rank_spearman_vs_baseline"] is None for x in comparisons)}}
    output = artifact_dir / SENSITIVITY_PATH
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate deterministic flood-model sensitivity on validation scenarios.")
    parser.add_argument("--dataset-metadata", type=Path, default=Path("ml_artifacts/dataset_metadata.json"))
    parser.add_argument("--artifacts", type=Path, default=ARTIFACT_DIR)
    args = parser.parse_args()
    report = run_sensitivity(args.dataset_metadata, args.artifacts)
    print(json.dumps(report["summary"], indent=2))


if __name__ == "__main__":
    main()
