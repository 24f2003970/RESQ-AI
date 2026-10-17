import csv
import json
import subprocess
import sys
from pathlib import Path

from app.evaluation import classify_objective_delta


def test_objective_delta_buckets_are_exclusive_at_decimal_boundaries():
    cases = [
        ("0", "tied"),
        ("0.01", "tied"),
        ("-0.01", "tied"),
        ("0.010001", "improved"),
        ("-0.010001", "lower"),
        ("0.001", "tied"),
        ("-0.001", "tied"),
    ]
    categories = {"improved", "tied", "lower"}
    for value, expected in cases:
        result = classify_objective_delta(value)
        assert result == expected
        assert result in categories
        assert sum(classify_objective_delta(value) == name for name in categories) == 1


def test_part15_evaluation_is_reproducible_bounded_and_reports_failure_cases(tmp_path):
    backend = Path(__file__).resolve().parents[1]
    output = tmp_path / "evidence"
    result = subprocess.run(
        [sys.executable, "run_part15_evaluation.py", "--output", str(output)],
        cwd=backend,
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )

    report = json.loads((output / "scientific_evaluation.json").read_text(encoding="utf-8"))
    rows = report["scenario_groups"]
    assert len(rows) == report["summary"]["independent_scenario_groups"] == 10
    assert len({row["scenario_group"] for row in rows}) == 10
    assert all(row["tick_observations_counted_as_independent"] == 1 for row in rows)
    assert all(row["planner"]["solver_status"] == "optimal_linear_sum_assignment" for row in rows)
    assert all(row["planner"]["objective_outcome"] in {"improved", "tied", "lower"} for row in rows)
    assert sum(report["summary"]["assignment_objective_outcomes"].values()) == len(rows)
    assert report["summary"]["assignment_objective_outcomes"] == {
        name: sum(row["planner"]["objective_outcome"] == name for row in rows)
        for name in ("improved", "tied", "lower")
    }
    assert report["summary"]["all_roads_closed_assignments"] == 0
    assert report["summary"]["groups_with_zero_ground_assignments"] >= 1
    fallback = next(row for row in rows if row["case"] == "model_unavailable_fallback")
    assert fallback["ml"]["status"] == "unavailable_simulated_fallback"
    assert fallback["planner"]["optimized"]["destinations_covered"] >= 0
    assert report["model_artifact_sha256"]
    assert report["calibrator_artifact_sha256"]
    assert "disposable temporary SQLite" in report["method"]["evaluation_database"]
    with (output / "scientific_evaluation.csv").open(newline="", encoding="utf-8") as handle:
        assert len(list(csv.DictReader(handle))) == 10
    assert "10" in result.stdout
