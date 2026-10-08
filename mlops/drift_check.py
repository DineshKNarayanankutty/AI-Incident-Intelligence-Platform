"""CLI for comparing current incident data against a committed reference profile."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.training.drift import build_drift_profile, compare_profiles, load_incident_rows


def _load_predictions(path: Path | None) -> list[str] | None:
    if path is None:
        return None
    payload = path.read_text(encoding="utf-8")
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return [line.strip() for line in payload.splitlines() if line.strip()]
    if isinstance(data, list):
        return [str(value) for value in data]
    raise ValueError("Predictions file must contain a JSON list or one label per line.")


def run_drift_check(
    reference_path: Path,
    data_path: Path,
    threshold: float,
    warning_threshold: float = 0.10,
    predictions_path: Path | None = None,
) -> dict:
    reference = json.loads(reference_path.read_text(encoding="utf-8"))
    rows = load_incident_rows(data_path)
    predictions = _load_predictions(predictions_path)

    current = build_drift_profile(
        rows,
        predictions=predictions,
        reference_numeric=reference.get("numeric", {}),
    )
    comparison = compare_profiles(
        reference,
        current,
        threshold=threshold,
        warning_threshold=warning_threshold,
    )

    return {
        **comparison,
        "reference_path": str(reference_path),
        "data_path": str(data_path),
        "reference_sample_size": reference.get("sample_size"),
        "current_sample_size": current.get("sample_size"),
        "profile_version": current.get("profile_version"),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Check incident data drift using PSI.")
    parser.add_argument(
        "--reference", type=Path, default=Path("data/reference/drift_baseline.json")
    )
    parser.add_argument(
        "--data", type=Path, default=Path("data/synthetic_incidents.csv")
    )
    parser.add_argument("--threshold", type=float, default=0.25)
    parser.add_argument("--warning-threshold", type=float, default=0.10)
    parser.add_argument("--predictions", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    if not 0 < args.warning_threshold < args.threshold:
        raise SystemExit("Require 0 < --warning-threshold < --threshold.")

    result = run_drift_check(
        reference_path=args.reference,
        data_path=args.data,
        threshold=args.threshold,
        warning_threshold=args.warning_threshold,
        predictions_path=args.predictions,
    )
    payload = json.dumps(result, indent=2, sort_keys=True)
    print(payload)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
