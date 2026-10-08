"""CLI for comparing a current dataset against the Phase 1 drift baseline."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.training.drift import build_drift_profile, compare_categorical_profiles
from src.training.train import load_rows


def run_drift_check(reference_path: Path, data_path: Path, threshold: float) -> dict:
    reference = json.loads(reference_path.read_text(encoding="utf-8"))
    current = build_drift_profile(load_rows(data_path))
    comparison = compare_categorical_profiles(
        reference["categorical"], current["categorical"]
    )
    drift_detected = any(
        float(item["psi"]) >= threshold for item in comparison.values()
    )
    return {
        "drift_detected": drift_detected,
        "threshold": threshold,
        "comparison": comparison,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--reference", type=Path, default=Path("data/reference/drift_baseline.json")
    )
    parser.add_argument(
        "--data", type=Path, default=Path("data/synthetic_incidents.csv")
    )
    parser.add_argument("--threshold", type=float, default=0.25)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    result = run_drift_check(args.reference, args.data, args.threshold)
    payload = json.dumps(result, indent=2, sort_keys=True)
    print(payload)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
