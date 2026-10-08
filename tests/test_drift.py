from __future__ import annotations

from src.data.generate_synthetic_data import generate_dataset
from src.training.drift import (
    DEFAULT_ALERT_THRESHOLD,
    build_drift_profile,
    compare_profiles,
    population_stability_index,
)
from src.training.drift import load_incident_rows


def test_population_stability_index_is_zero_for_matching_distributions() -> None:
    expected = {"Low": 0.5, "High": 0.5}
    assert population_stability_index(expected, expected) == 0


def test_matching_profile_has_no_drift(tmp_path) -> None:
    path = tmp_path / "incidents.csv"
    generate_dataset(path, rows=200, seed=42)
    rows = load_incident_rows(path)
    reference = build_drift_profile(rows)
    current = build_drift_profile(rows, reference_numeric=reference["numeric"])

    result = compare_profiles(reference, current)

    assert result["drift_detected"] is False
    assert result["drifted_features"] == []
    assert result["max_psi"] < 1e-12


def test_compare_categorical_profiles_flags_shifted_distribution() -> None:
    reference = build_drift_profile(
        [
            {"service": "payments", "region": "eastus", "incident_type": "latency",
             "customer_impact": "none", "detected_by": "synthetic_monitor",
             "has_data_loss": "false", "is_security_related": "false",
             "title": "a", "description": "b", "duration_minutes": "10",
             "affected_users": "10", "error_rate": "0.01", "latency_ms": "100"}
        ] * 10
    )
    current = build_drift_profile(
        [
            {"service": "checkout", "region": "eastus", "incident_type": "latency",
             "customer_impact": "none", "detected_by": "synthetic_monitor",
             "has_data_loss": "false", "is_security_related": "false",
             "title": "a", "description": "b", "duration_minutes": "10",
             "affected_users": "10", "error_rate": "0.01", "latency_ms": "100"}
        ] * 10,
        reference_numeric=reference["numeric"],
    )

    result = compare_profiles(reference, current)

    assert result["drift_detected"] is True
    assert "categorical.service" in result["drifted_features"]
    assert result["comparison"]["categorical"]["service"]["psi"] >= DEFAULT_ALERT_THRESHOLD


def test_numeric_shift_is_detected(tmp_path) -> None:
    reference_path = tmp_path / "reference.csv"
    current_path = tmp_path / "current.csv"
    generate_dataset(reference_path, rows=300, seed=42)
    generate_dataset(current_path, rows=300, seed=84)

    reference_rows = load_incident_rows(reference_path)
    current_rows = load_incident_rows(current_path)
    # Force a material numeric shift while preserving the real schema.
    for row in current_rows:
        row["latency_ms"] = str(float(row["latency_ms"]) * 4.0)
        row["error_rate"] = str(min(float(row["error_rate"]) + 0.35, 0.99))

    reference = build_drift_profile(reference_rows)
    current = build_drift_profile(current_rows, reference_numeric=reference["numeric"])
    result = compare_profiles(reference, current)

    assert result["drift_detected"] is True
    assert any(feature in result["drifted_features"] for feature in {
        "numeric.latency_ms", "numeric.error_rate"
    })


def test_new_categorical_value_is_detected(tmp_path) -> None:
    path = tmp_path / "incidents.csv"
    generate_dataset(path, rows=200, seed=42)
    rows = load_incident_rows(path)
    reference = build_drift_profile(rows)

    shifted_rows = [dict(row) for row in rows]
    for row in shifted_rows:
        row["region"] = "new-region"
    current = build_drift_profile(shifted_rows, reference_numeric=reference["numeric"])
    result = compare_profiles(reference, current)

    assert result["drift_detected"] is True
    assert "categorical.region" in result["drifted_features"]
