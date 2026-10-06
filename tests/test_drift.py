from __future__ import annotations

from src.training.drift import compare_categorical_profiles, population_stability_index


def test_population_stability_index_is_zero_for_matching_distributions() -> None:
    expected = {"Low": 0.5, "High": 0.5}

    assert population_stability_index(expected, expected) == 0


def test_compare_categorical_profiles_flags_shifted_distribution() -> None:
    reference = {"severity": {"Low": 0.8, "Critical": 0.2}}
    current = {"severity": {"Low": 0.2, "Critical": 0.8}}

    result = compare_categorical_profiles(reference, current)

    assert result["severity"]["status"] == "alert"
    assert result["severity"]["psi"] > 0.25

