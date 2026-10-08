"""Quality gate for candidate incident-severity models.

The production model remains the source of truth until a candidate satisfies
both minimum quality requirements and non-regression checks against the
committed production baseline.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DEFAULT_MIN_ACCURACY = 0.80
DEFAULT_MIN_MACRO_F1 = 0.80


def _metric(payload: dict[str, Any], key: str) -> float:
    try:
        value = payload[key]
        return float(value)
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"Missing or invalid metric: {key}") from exc


def load_metrics(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Metrics file must contain a JSON object: {path}")
    return payload


def evaluate_candidate(
    candidate: dict[str, Any],
    production: dict[str, Any],
    *,
    min_accuracy: float = DEFAULT_MIN_ACCURACY,
    min_macro_f1: float = DEFAULT_MIN_MACRO_F1,
) -> dict[str, Any]:
    candidate_accuracy = _metric(candidate, "accuracy")
    candidate_macro_f1 = _metric(candidate, "macro_f1")
    production_accuracy = _metric(production, "accuracy")
    production_macro_f1 = _metric(production, "macro_f1")

    checks = {
        "candidate_accuracy_meets_minimum": candidate_accuracy >= min_accuracy,
        "candidate_macro_f1_meets_minimum": candidate_macro_f1 >= min_macro_f1,
        "candidate_accuracy_not_below_production": candidate_accuracy >= production_accuracy,
        "candidate_macro_f1_not_below_production": candidate_macro_f1 >= production_macro_f1,
    }

    return {
        "passed": all(checks.values()),
        "checks": checks,
        "candidate": {
            "accuracy": candidate_accuracy,
            "macro_f1": candidate_macro_f1,
        },
        "production": {
            "model_name": production.get("model_name"),
            "model_version": production.get("model_version"),
            "accuracy": production_accuracy,
            "macro_f1": production_macro_f1,
        },
        "thresholds": {
            "min_accuracy": min_accuracy,
            "min_macro_f1": min_macro_f1,
        },
        "delta": {
            "accuracy": candidate_accuracy - production_accuracy,
            "macro_f1": candidate_macro_f1 - production_macro_f1,
        },
    }
