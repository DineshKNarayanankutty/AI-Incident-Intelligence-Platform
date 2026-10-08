from genai.evaluation.gate import evaluate_gate


def _comparison(*, v1_overall=0.55, v2_overall=0.98, v1_grounding=0.67, v2_grounding=1.0):
    return {
        "v1": {"overall": v1_overall, "grounding": v1_grounding},
        "v2": {"overall": v2_overall, "grounding": v2_grounding},
        "grounding_regression": v2_grounding < v1_grounding,
        "winner": "v2" if v2_overall >= v1_overall else "v1",
    }


def test_current_style_comparison_passes() -> None:
    passed, errors = evaluate_gate(_comparison())
    assert passed is True
    assert errors == []


def test_grounding_regression_fails() -> None:
    passed, errors = evaluate_gate(
        _comparison(v1_grounding=0.9, v2_grounding=0.8, v2_overall=0.95)
    )
    assert passed is False
    assert any("Grounding regression" in error for error in errors)


def test_minimum_overall_fails() -> None:
    passed, errors = evaluate_gate(_comparison(v2_overall=0.79), min_overall=0.80)
    assert passed is False
    assert any("below minimum" in error for error in errors)


def test_v2_cannot_regress_overall() -> None:
    passed, errors = evaluate_gate(_comparison(v2_overall=0.50), min_overall=0.40)
    assert passed is False
    assert any("below V1" in error for error in errors)
