"""CLI for comparing a current dataset against the Phase 1 drift baseline."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.training.drift import build_drift_profile, compare_categorical_profiles
from src.training.train import load_rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference", type=Path, default=Path("outputs/model/drift_baseline.json"))
    parser.add_argument("--data", type=Path, default=Path("data/synthetic_incidents.csv"))
    parser.add_argument("--threshold", type=float, default=0.25)
    args = parser.parse_args()

    reference = json.loads(args.reference.read_text(encoding="utf-8"))
    current = build_drift_profile(load_rows(args.data))
    comparison = compare_categorical_profiles(reference["categorical"], current["categorical"])
    print(json.dumps(comparison, indent=2))
    if any(float(item["psi"]) >= args.threshold for item in comparison.values()):
        raise SystemExit(2)


if __name__ == "__main__":
    main()
