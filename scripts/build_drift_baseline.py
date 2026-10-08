"""Build a committed drift reference profile from a known-good dataset."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.training.drift import build_drift_profile, load_incident_rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the incident drift baseline profile.")
    parser.add_argument("--data", type=Path, default=Path("data/synthetic_incidents.csv"))
    parser.add_argument(
        "--output", type=Path, default=Path("data/reference/drift_baseline.json")
    )
    parser.add_argument("--bins", type=int, default=10)
    args = parser.parse_args()

    profile = build_drift_profile(load_incident_rows(args.data), numeric_bins=args.bins)
    profile["source_data"] = str(args.data)
    profile["numeric_bin_count"] = args.bins
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(__import__("json").dumps(profile, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Wrote drift reference profile: {args.output}")


if __name__ == "__main__":
    main()
