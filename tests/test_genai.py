from pathlib import Path

from genai.evaluation.evaluators import evaluate_response
from genai.evaluation.runner import compare_reports, load_dataset
from genai.prompts.loader import load_prompt


def test_prompt_versions_are_distinct() -> None:
    assert load_prompt("v1") != load_prompt("v2")


def test_evaluation_dataset_is_valid() -> None:
    cases = load_dataset(Path("genai/evaluation/dataset.jsonl"))
    assert len(cases) >= 3
    assert all("expected_severity" in case for case in cases)
    assert all("criteria" in case for case in cases)


def test_evaluator_returns_bounded_scores() -> None:
    incident = {
        "service": "orders",
        "region": "westus",
        "incident_type": "availability",
    }
    scores = evaluate_response(
        "High severity impact with latency signals. Investigate dependency health."
        " Uncertainty remains about the root cause.",
        "High",
        incident,
        ["mentions customer impact", "uses observed signals"],
    )
    assert all(0 <= value <= 1 for value in scores.values())


def test_grounding_regression_prevents_v2_promotion() -> None:
    v1 = {"averages": {"grounding": 0.9, "overall": 0.7}}
    v2 = {"averages": {"grounding": 0.8, "overall": 0.8}}
    comparison = compare_reports(v1, v2)
    assert comparison["grounding_regression"] is True
    assert comparison["winner"] == "v1"
