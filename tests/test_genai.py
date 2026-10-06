from pathlib import Path

from genai.evaluation.runner import heuristic_score, load_dataset
from genai.prompts.loader import load_prompt


def test_prompt_versions_are_distinct() -> None:
    assert load_prompt("v1") != load_prompt("v2")


def test_evaluation_dataset_is_valid() -> None:
    cases = load_dataset(Path("genai/evaluation/dataset.jsonl"))
    assert len(cases) >= 3
    assert all("expected_severity" in case for case in cases)


def test_heuristic_evaluator_returns_bounded_scores() -> None:
    scores = heuristic_score("High impact with latency signals.", "High", [])
    assert 0 <= scores["overall"] <= 1
