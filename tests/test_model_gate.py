from __future__ import annotations

from mlops.model_gate import evaluate_candidate


def test_candidate_passes_when_it_meets_minimums_and_does_not_regress() -> None:
    result = evaluate_candidate(
        {"accuracy": 0.82, "macro_f1": 0.83},
        {"model_name": "incident-severity", "model_version": "1", "accuracy": 0.80, "macro_f1": 0.809},
    )

    assert result["passed"] is True
    assert result["delta"]["macro_f1"] > 0


def test_candidate_fails_when_macro_f1_regresses() -> None:
    result = evaluate_candidate(
        {"accuracy": 0.81, "macro_f1": 0.80},
        {"model_name": "incident-severity", "model_version": "1", "accuracy": 0.80, "macro_f1": 0.809},
    )

    assert result["passed"] is False
    assert result["checks"]["candidate_macro_f1_not_below_production"] is False


def test_candidate_fails_below_minimum_quality() -> None:
    result = evaluate_candidate(
        {"accuracy": 0.79, "macro_f1": 0.79},
        {"model_name": "incident-severity", "model_version": "1", "accuracy": 0.78, "macro_f1": 0.78},
    )

    assert result["passed"] is False
