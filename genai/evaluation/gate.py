"""Promotion quality gate for GenAIOps prompt comparisons."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


DEFAULT_MIN_OVERALL = 0.80


def evaluate_gate(
    comparison: dict[str, Any],
    *,
    min_overall: float = DEFAULT_MIN_OVERALL,
    require_non_regression: bool = True,
) -> tuple[bool, list[str]]:
    """Return whether the candidate prompt/version is eligible for promotion."""
    errors: list[str] = []

    try:
        v1 = comparison["v1"]
        v2 = comparison["v2"]
        grounding_regression = bool(comparison.get("grounding_regression", False))
    except KeyError as exc:
        return False, [f"Comparison is missing required field: {exc.args[0]}"]

    required_metrics = {"overall", "grounding"}
    for version, scores in (("v1", v1), ("v2", v2)):
        missing = required_metrics - set(scores)
        if missing:
            errors.append(f"{version} is missing metrics: {sorted(missing)}")

    if errors:
        return False, errors

    if v2["overall"] < min_overall:
        errors.append(
            f"V2 overall score {v2['overall']:.4f} is below minimum {min_overall:.4f}."
        )

    if v2["overall"] < v1["overall"]:
        errors.append(
            f"V2 overall score {v2['overall']:.4f} is below V1 {v1['overall']:.4f}."
        )

    if require_non_regression and (
        grounding_regression or v2["grounding"] < v1["grounding"]
    ):
        errors.append(
            f"Grounding regression detected: V1={v1['grounding']:.4f}, "
            f"V2={v2['grounding']:.4f}."
        )

    return not errors, errors


def run_gate(comparison_path: Path, *, min_overall: float) -> int:
    """Print the gate result and return a process exit code."""
    comparison = json.loads(comparison_path.read_text(encoding="utf-8"))
    passed, errors = evaluate_gate(comparison, min_overall=min_overall)

    if passed:
        print("QUALITY GATE: PASS")
        print(f"V2 overall: {comparison['v2']['overall']:.4f}")
        print(f"V2 grounding: {comparison['v2']['grounding']:.4f}")
        return 0

    print("QUALITY GATE: FAIL")
    for error in errors:
        print(f"- {error}")
    return 1


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate a GenAIOps prompt promotion gate.")
    parser.add_argument(
        "--comparison",
        type=Path,
        default=Path("outputs/evaluation/comparison.json"),
    )
    parser.add_argument("--min-overall", type=float, default=DEFAULT_MIN_OVERALL)
    args = parser.parse_args()

    raise SystemExit(run_gate(args.comparison, min_overall=args.min_overall))


if __name__ == "__main__":
    main()
