"""Reproducible scenario-grouped synthetic training data generation."""

from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np

from ..city_service import generate_city
from ..flood import SimulationParameters, initial_depth, step
from .features import ENGINE_VERSION, FEATURE_NAMES, HORIZON_TICKS, TARGET_NAME, build_feature_rows, target_exposed

OBSERVATION_TICKS = (0, 3, 6, 9, 12)


@dataclass(frozen=True)
class DatasetConfig:
    scenario_count: int = 72
    first_scenario_seed: int = 73000
    sampling_seed: int = 44117
    horizon_ticks: int = HORIZON_TICKS
    observation_ticks: tuple[int, ...] = OBSERVATION_TICKS


def _sample_parameters(rng: np.random.Generator) -> SimulationParameters:
    # Wide but bounded synthetic range; each run gets its own constant forcing.
    rainfall = float(rng.uniform(0.0, 260.0))
    river_level = float(rng.uniform(-0.7, 1.8))
    drainage = float(rng.uniform(0.05, 1.0))
    return SimulationParameters(rainfall_mm_h=rainfall, river_level_m=river_level,
                                drainage_effectiveness=drainage, speed=1.0)


def generate_dataset(config: DatasetConfig, csv_path: str | Path, metadata_path: str | Path) -> dict:
    if config.scenario_count < 20:
        raise ValueError("At least 20 independent scenarios are required for grouped evaluation.")
    if not config.observation_ticks or tuple(sorted(set(config.observation_ticks))) != config.observation_ticks:
        raise ValueError("Observation ticks must be unique and strictly increasing.")
    if config.observation_ticks[-1] + config.horizon_ticks > 24:
        raise ValueError("The last observation plus target horizon must be no later than tick 24.")

    csv_path, metadata_path = Path(csv_path), Path(metadata_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(config.sampling_seed)
    scenario_seeds = [config.first_scenario_seed + i for i in range(config.scenario_count)]
    fields = ["scenario_id", "scenario_seed", "observation_tick", "building_id", *FEATURE_NAMES, TARGET_NAME]
    positive = 0
    rows_written = 0
    duplicate_feature_rows = 0
    seen: set[tuple[float, ...]] = set()
    seed_records = []

    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for scenario_index, scenario_seed in enumerate(scenario_seeds, start=1):
            scenario_id = f"synthetic-{scenario_seed}"
            params = _sample_parameters(rng)
            city = generate_city(scenario_seed)
            depth = initial_depth(scenario_seed, params.river_level_m)
            current_tick = 0
            for observation_tick in config.observation_ticks:
                advance_ticks = observation_tick - current_tick
                if advance_ticks:
                    depth, _ = step(depth, scenario_seed, params, steps=advance_ticks)
                feature_rows = build_feature_rows(city, depth, scenario_seed, params, observation_tick)
                future_depth, _ = step(depth, scenario_seed, params, steps=config.horizon_ticks)
                labels = target_exposed(city, future_depth, scenario_seed, params.river_level_m)
                for building, features in zip(city.buildings, feature_rows, strict=True):
                    label = labels[building.id]
                    positive += label
                    identity = tuple(round(float(features[key]), 8) for key in FEATURE_NAMES) + (float(label),)
                    if identity in seen:
                        duplicate_feature_rows += 1
                    seen.add(identity)
                    writer.writerow({"scenario_id": scenario_id, "scenario_seed": scenario_seed,
                                     "observation_tick": observation_tick, "building_id": building.id,
                                     **features, TARGET_NAME: label})
                    rows_written += 1
                current_tick = observation_tick
            seed_records.append({"scenario_id": scenario_id, "seed": scenario_seed,
                                 "parameters": asdict(params)})
            if scenario_index == 1 or scenario_index % 10 == 0 or scenario_index == config.scenario_count:
                print(f"Generated scenario {scenario_index}/{config.scenario_count} - {rows_written} observations", flush=True)

    negatives = rows_written - positive
    metadata = {
        "dataset_version": "flood-exposure-synthetic-v1",
        "engine_version": ENGINE_VERSION,
        "generator": "app.ml.dataset.generate_dataset",
        "label_definition": "1 when the building footprint maximum water depth is at least 0.05 m after six fixed five-minute flood ticks (30 simulated minutes); otherwise 0.",
        "feature_names": FEATURE_NAMES,
        "target_name": TARGET_NAME,
        "feature_units": {name: ("m" if name.endswith("_m") else "mm/h" if name == "rainfall_mm_h" else "ticks" if name == "simulation_tick" else "count" if name.endswith("_floors") else "ratio" if "fraction" in name or name.startswith("use_") or name == "drainage_effectiveness" else "dimensionless") for name in FEATURE_NAMES},
        "scenario_count": config.scenario_count,
        "observation_count": rows_written,
        "positive_count": positive,
        "negative_count": negatives,
        "positive_fraction": positive / rows_written if rows_written else 0.0,
        "duplicate_feature_target_rows": duplicate_feature_rows,
        "random_sampling_seed": config.sampling_seed,
        "configuration": asdict(config),
        "simulation_seeds": seed_records,
        "provenance": "Generated locally from the RESQ-AI synthetic city generator and deterministic Part 3 flood engine; not collected from real incidents or observations.",
        "csv_file": csv_path.name,
    }
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return metadata
