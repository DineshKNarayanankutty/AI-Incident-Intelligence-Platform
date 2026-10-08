"""Evaluate a trained candidate model's metrics against the production baseline."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from mlops.model_gate import evaluate_candidate, load_metrics


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
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    result = evaluate_candidate(
        load_metrics(args.candidate_metrics),
        load_metrics(args.production_metrics),
        min_accuracy=args.min_accuracy,
        min_macro_f1=args.min_macro_f1,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))

    if not result["passed"]:
        print("Candidate quality gate FAILED.")
        return 1

    print("Candidate quality gate PASSED.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
