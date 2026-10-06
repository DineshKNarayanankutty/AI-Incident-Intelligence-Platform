"""Small local drift helpers for Phase 1 artifacts."""

from __future__ import annotations

from collections import Counter
from statistics import mean, median
from typing import Iterable


def categorical_distribution(values: Iterable[str]) -> dict[str, float]:
    counts = Counter(str(value) for value in values)
    total = sum(counts.values())
    if total == 0:
        return {}
    return {key: count / total for key, count in sorted(counts.items())}


def numeric_summary(values: Iterable[float]) -> dict[str, float]:
    numeric_values = sorted(float(value) for value in values)
    if not numeric_values:
        return {"count": 0}

    def percentile(percent: float) -> float:
        if len(numeric_values) == 1:
            return numeric_values[0]
        index = round((len(numeric_values) - 1) * percent)
        return numeric_values[index]

    return {
        "count": len(numeric_values),
        "min": min(numeric_values),
        "max": max(numeric_values),
        "mean": mean(numeric_values),
        "median": median(numeric_values),
        "p90": percentile(0.9),
    }


def population_stability_index(expected: dict[str, float], actual: dict[str, float], epsilon: float = 1e-6) -> float:
    buckets = set(expected) | set(actual)
    score = 0.0
    for bucket in buckets:
        expected_pct = max(expected.get(bucket, 0.0), epsilon)
        actual_pct = max(actual.get(bucket, 0.0), epsilon)
        score += (actual_pct - expected_pct) * __import__("math").log(actual_pct / expected_pct)
    return score


def build_drift_profile(rows: list[dict[str, str]], predictions: list[str] | None = None) -> dict[str, object]:
    text_lengths = [len(f"{row['title']} {row['description']}") for row in rows]
    profile: dict[str, object] = {
        "categorical": {
            "severity": categorical_distribution(row["severity"] for row in rows),
            "service": categorical_distribution(row["service"] for row in rows),
            "region": categorical_distribution(row["region"] for row in rows),
            "incident_type": categorical_distribution(row["incident_type"] for row in rows),
            "customer_impact": categorical_distribution(row["customer_impact"] for row in rows),
        },
        "numeric": {
            "duration_minutes": numeric_summary(float(row["duration_minutes"]) for row in rows),
            "affected_users": numeric_summary(float(row["affected_users"]) for row in rows),
            "error_rate": numeric_summary(float(row["error_rate"]) for row in rows),
            "latency_ms": numeric_summary(float(row["latency_ms"]) for row in rows),
            "text_length": numeric_summary(float(value) for value in text_lengths),
        },
    }

    if predictions is not None:
        profile["categorical"]["prediction"] = categorical_distribution(predictions)  # type: ignore[index]

    return profile


def compare_categorical_profiles(
    reference: dict[str, dict[str, float]],
    current: dict[str, dict[str, float]],
    warning_threshold: float = 0.1,
    alert_threshold: float = 0.25,
) -> dict[str, dict[str, float | str]]:
    results: dict[str, dict[str, float | str]] = {}
    for feature, reference_distribution in reference.items():
        current_distribution = current.get(feature, {})
        psi = population_stability_index(reference_distribution, current_distribution)
        if psi >= alert_threshold:
            status = "alert"
        elif psi >= warning_threshold:
            status = "warning"
        else:
            status = "ok"
        results[feature] = {"psi": psi, "status": status}
    return results

