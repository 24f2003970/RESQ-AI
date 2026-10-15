"""CLI: python -m app.ml.generate_dataset [--scenarios 72] [--seed 73000]."""

import argparse
from pathlib import Path

from .dataset import DatasetConfig, generate_dataset


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate reproducible RESQ-AI synthetic flood-exposure data.")
    parser.add_argument("--scenarios", type=int, default=72)
    parser.add_argument("--seed", type=int, default=73000, help="First independent city/scenario seed")
    parser.add_argument("--sampling-seed", type=int, default=44117)
    parser.add_argument("--csv", type=Path, default=Path("data/ml/flood_exposure.csv"))
    parser.add_argument("--metadata", type=Path, default=Path("ml_artifacts/dataset_metadata.json"))
    args = parser.parse_args()
    result = generate_dataset(DatasetConfig(scenario_count=args.scenarios,
        first_scenario_seed=args.seed, sampling_seed=args.sampling_seed), args.csv, args.metadata)
    print(f"Saved {result['observation_count']} observations: {result['positive_count']} positive, {result['negative_count']} negative")


if __name__ == "__main__":
    main()
