"""Evaluate a trained candidate model's metrics against the production baseline."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mlops.model_gate import DEFAULT_TOLERANCE, evaluate_candidate, load_metrics


def format_report(result: dict) -> str:
    cand, prod, delta = result["candidate"], result["production"], result["delta"]
    lines = [
        "Candidate metrics:",
        f"  accuracy: {cand['accuracy']:.6f}",
        f"  macro_f1: {cand['macro_f1']:.6f}",
        f"Production metrics (v{prod.get('model_version')}):",
        f"  accuracy: {prod['accuracy']:.6f}",
        f"  macro_f1: {prod['macro_f1']:.6f}",
        "Deltas (candidate - production):",
        f"  accuracy: {delta['accuracy']:+.6f}",
        f"  macro_f1: {delta['macro_f1']:+.6f}",
        "Thresholds: " + ", ".join(f"{k}={v}" for k, v in result["thresholds"].items()),
        "Checks:",
    ]
    lines += [f"  {name}: {'PASS' if ok else 'FAIL'}" for name, ok in result["checks"].items()]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate a candidate model against production.")
    parser.add_argument("--candidate-metrics", type=Path, required=True)
    parser.add_argument(
        "--production-metrics",
        type=Path,
        default=Path("data/reference/production_model_metrics.json"),
    )
    parser.add_argument("--min-accuracy", type=float, default=0.80)
    parser.add_argument("--min-macro-f1", type=float, default=0.80)
    parser.add_argument("--tolerance", type=float, default=DEFAULT_TOLERANCE)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    result = evaluate_candidate(
        load_metrics(args.candidate_metrics),
        load_metrics(args.production_metrics),
        min_accuracy=args.min_accuracy,
        min_macro_f1=args.min_macro_f1,
        tolerance=args.tolerance,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(format_report(result))
    print("gate.json:")
    print(json.dumps(result, indent=2, sort_keys=True))

    if not result["passed"]:
        failed = [name for name, ok in result["checks"].items() if not ok]
        print(f"Candidate quality gate FAILED. Failed checks: {', '.join(failed)}")
        return 1

    print("Candidate quality gate PASSED.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
