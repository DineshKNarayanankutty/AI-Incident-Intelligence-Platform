"""Evaluate a trained candidate model's metrics against the production baseline.

Exit codes: 0 gate passed, 1 gate failed, 2 candidate provenance invalid
(metrics not produced against the committed fixed evaluation dataset).
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mlops.model_gate import DEFAULT_TOLERANCE, evaluate_candidate, load_metrics
from src.training.reference_split import dataset_fingerprint


def format_report(result: dict) -> str:
    cand, prod, delta = result["candidate"], result["production"], result["delta"]
    lines = [
        "Candidate metrics:",
        f"  accuracy: {cand['accuracy']!r}",
        f"  macro_f1: {cand['macro_f1']!r}",
        f"  evaluation_dataset_sha256: {cand.get('evaluation_dataset_sha256')}",
        f"Production metrics (v{prod.get('model_version')}):",
        f"  accuracy: {prod['accuracy']!r}",
        f"  macro_f1: {prod['macro_f1']!r}",
        f"  evaluation_dataset_sha256: {prod.get('evaluation_dataset_sha256')}",
        "Deltas (candidate - production):",
        f"  accuracy: {delta['accuracy']:+.9f}",
        f"  macro_f1: {delta['macro_f1']:+.9f}",
        "Thresholds: " + ", ".join(f"{k}={v}" for k, v in result["thresholds"].items()),
        "Checks:",
    ]
    lines += [f"  {name}: {'PASS' if ok else 'FAIL'}" for name, ok in result["checks"].items()]
    return "\n".join(lines)


def committed_fingerprint(evaluation_data: Path) -> str:
    """Fingerprint the committed evaluation CSV (read only, never regenerated)."""
    with evaluation_data.open("r", newline="", encoding="utf-8") as handle:
        return dataset_fingerprint(list(csv.DictReader(handle)))


def provenance_errors(candidate: dict, production: dict, committed_sha: str) -> list[str]:
    errors = []
    if candidate.get("evaluation_mode") != "fixed_reference":
        errors.append(
            f"candidate evaluation_mode is {candidate.get('evaluation_mode')!r}, expected 'fixed_reference' "
            "(candidate was not evaluated on a separate fixed dataset)"
        )
    if candidate.get("evaluation_dataset_sha256") != committed_sha:
        errors.append(
            "candidate evaluation_dataset_sha256 "
            f"{candidate.get('evaluation_dataset_sha256')!r} != committed dataset {committed_sha!r}"
        )
    if production.get("evaluation_dataset_sha256") != committed_sha:
        errors.append(
            "production baseline evaluation_dataset_sha256 "
            f"{production.get('evaluation_dataset_sha256')!r} != committed dataset {committed_sha!r}"
        )
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate a candidate model against production.")
    parser.add_argument("--candidate-metrics", type=Path, required=True)
    parser.add_argument(
        "--production-metrics",
        type=Path,
        default=Path("data/reference/production_model_metrics.json"),
    )
    parser.add_argument(
        "--evaluation-data",
        type=Path,
        default=Path("data/reference/candidate_evaluation.csv"),
        help="Committed fixed evaluation dataset both models must have been scored on.",
    )
    parser.add_argument("--min-accuracy", type=float, default=0.80)
    parser.add_argument("--min-macro-f1", type=float, default=0.80)
    parser.add_argument("--tolerance", type=float, default=DEFAULT_TOLERANCE)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    print(f"=== candidate metrics file: {args.candidate_metrics}")
    print(args.candidate_metrics.read_text(encoding="utf-8"))
    print(f"=== production metrics file: {args.production_metrics}")
    print(args.production_metrics.read_text(encoding="utf-8"))

    candidate = load_metrics(args.candidate_metrics)
    production = load_metrics(args.production_metrics)

    committed_sha = committed_fingerprint(args.evaluation_data)
    print(f"=== committed evaluation dataset {args.evaluation_data}\n  sha256: {committed_sha}")
    print(f"  candidate  sha256: {candidate.get('evaluation_dataset_sha256')}")
    print(f"  production sha256: {production.get('evaluation_dataset_sha256')}")
    errors = provenance_errors(candidate, production, committed_sha)
    if errors:
        for error in errors:
            print(f"::error::Candidate provenance check failed: {error}")
        print("Candidate rejected before the quality gate: metrics are not comparable. Production model unchanged.")
        return 2

    result = evaluate_candidate(
        candidate,
        production,
        min_accuracy=args.min_accuracy,
        min_macro_f1=args.min_macro_f1,
        tolerance=args.tolerance,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(format_report(result))
    print(f"=== {args.output}")
    print(json.dumps(result, indent=2, sort_keys=True))

    if not result["passed"]:
        failed = [name for name, ok in result["checks"].items() if not ok]
        print(f"::error::Candidate quality gate FAILED. Failed checks: {', '.join(failed)}")
        return 1

    print("Candidate quality gate PASSED.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
