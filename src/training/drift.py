"""Data-drift profiling and PSI-based comparison helpers.

The drift implementation is intentionally dependency-light so it can run in
local CI, Azure ML jobs, or a GitHub Actions drift gate without requiring the
serving application or a model artifact to be imported.
"""

from __future__ import annotations

import csv
import math
from bisect import bisect_right
from collections import Counter
from statistics import mean, median
from typing import Iterable, Mapping

DEFAULT_NUMERIC_BINS = 10
DEFAULT_WARNING_THRESHOLD = 0.10
DEFAULT_ALERT_THRESHOLD = 0.25

CATEGORICAL_FEATURES = (
    "service",
    "region",
    "incident_type",
    "customer_impact",
    "detected_by",
    "has_data_loss",
    "is_security_related",
)

NUMERIC_FEATURES = (
    "duration_minutes",
    "affected_users",
    "error_rate",
    "latency_ms",
    "text_length",
)


REQUIRED_COLUMNS = (
    "incident_id",
    "title",
    "description",
    "service",
    "region",
    "incident_type",
    "customer_impact",
    "detected_by",
    "duration_minutes",
    "affected_users",
    "error_rate",
    "latency_ms",
    "has_data_loss",
    "is_security_related",
    "severity",
)


def load_incident_rows(data_path: str | "Path") -> list[dict[str, str]]:
    """Load and validate incident CSV rows without importing ML dependencies."""
    from pathlib import Path

    path = Path(data_path)
    with path.open("r", newline="", encoding="utf-8") as csv_file:
        reader = csv.DictReader(csv_file)
        rows = list(reader)
    if not rows:
        raise ValueError("Dataset is empty.")
    missing_columns = sorted(set(REQUIRED_COLUMNS) - set(rows[0]))
    if missing_columns:
        raise ValueError(f"Dataset is missing required columns: {missing_columns}")
    return rows


def categorical_distribution(values: Iterable[object]) -> dict[str, float]:
    materialized = [str(value) for value in values]
    counts = Counter(materialized)
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
        position = (len(numeric_values) - 1) * percent
        lower = math.floor(position)
        upper = math.ceil(position)
        if lower == upper:
            return numeric_values[lower]
        weight = position - lower
        return numeric_values[lower] + weight * (numeric_values[upper] - numeric_values[lower])

    return {
        "count": len(numeric_values),
        "min": min(numeric_values),
        "max": max(numeric_values),
        "mean": mean(numeric_values),
        "median": median(numeric_values),
        "p90": percentile(0.90),
    }


def population_stability_index(
    expected: Mapping[str, float],
    actual: Mapping[str, float],
    epsilon: float = 1e-6,
) -> float:
    """Calculate PSI for two discrete distributions."""
    buckets = set(expected) | set(actual)
    score = 0.0
    for bucket in buckets:
        expected_pct = max(float(expected.get(bucket, 0.0)), epsilon)
        actual_pct = max(float(actual.get(bucket, 0.0)), epsilon)
        score += (actual_pct - expected_pct) * math.log(actual_pct / expected_pct)
    return float(score)


def _quantile(values: list[float], percent: float) -> float:
    if not values:
        raise ValueError("Cannot calculate quantiles for an empty collection.")
    if len(values) == 1:
        return values[0]
    position = (len(values) - 1) * percent
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return values[lower]
    weight = position - lower
    return values[lower] + weight * (values[upper] - values[lower])


def _numeric_bin_edges(values: list[float], bin_count: int) -> list[float]:
    if bin_count < 2:
        raise ValueError("bin_count must be at least 2")
    if not values:
        return []

    ordered = sorted(values)
    raw_edges = [_quantile(ordered, index / bin_count) for index in range(bin_count + 1)]

    # Duplicate quantiles are common with small or low-cardinality data. Keep
    # only unique edges so we never construct zero-width bins.
    edges: list[float] = []
    for edge in raw_edges:
        if not edges or edge > edges[-1]:
            edges.append(float(edge))

    if len(edges) == 1:
        center = edges[0]
        margin = max(abs(center) * 0.01, 0.5)
        edges = [center - margin, center + margin]

    return edges


def _binned_distribution(values: Iterable[float], edges: list[float]) -> dict[str, float]:
    materialized = [float(value) for value in values]
    if not materialized or len(edges) < 2:
        return {}

    bucket_count = len(edges) - 1
    counts = [0] * bucket_count
    for value in materialized:
        index = bisect_right(edges, value) - 1
        index = max(0, min(index, bucket_count - 1))
        counts[index] += 1

    total = len(materialized)
    return {
        f"bin_{index}": count / total
        for index, count in enumerate(counts)
    }


def _numeric_profile(
    values: Iterable[float],
    *,
    reference_edges: list[float] | None = None,
    bin_count: int = DEFAULT_NUMERIC_BINS,
) -> dict[str, object]:
    materialized = [float(value) for value in values]
    summary = numeric_summary(materialized)
    if not materialized:
        return summary

    edges = reference_edges or _numeric_bin_edges(materialized, bin_count)
    return {
        **summary,
        "bin_edges": edges,
        "bin_distribution": _binned_distribution(materialized, edges),
    }


def _reference_edges(reference_numeric: Mapping[str, object], feature: str) -> list[float] | None:
    profile = reference_numeric.get(feature)
    if not isinstance(profile, dict):
        return None
    raw_edges = profile.get("bin_edges")
    if not isinstance(raw_edges, list):
        return None
    return [float(edge) for edge in raw_edges]


def build_drift_profile(
    rows: list[dict[str, object]],
    predictions: list[str] | None = None,
    *,
    reference_numeric: Mapping[str, object] | None = None,
    numeric_bins: int = DEFAULT_NUMERIC_BINS,
) -> dict[str, object]:
    """Build a serializable reference/current profile for incident data."""
    if not rows:
        raise ValueError("Cannot build a drift profile from an empty dataset.")

    text_lengths = [
        len(f"{row['title']} {row['description']}")
        for row in rows
    ]

    categorical = {
        feature: categorical_distribution(row[feature] for row in rows)
        for feature in CATEGORICAL_FEATURES
    }

    numeric_values: dict[str, list[float]] = {
        "duration_minutes": [float(row["duration_minutes"]) for row in rows],
        "affected_users": [float(row["affected_users"]) for row in rows],
        "error_rate": [float(row["error_rate"]) for row in rows],
        "latency_ms": [float(row["latency_ms"]) for row in rows],
        "text_length": [float(value) for value in text_lengths],
    }

    reference_numeric = reference_numeric or {}
    numeric = {
        feature: _numeric_profile(
            values,
            reference_edges=_reference_edges(reference_numeric, feature),
            bin_count=numeric_bins,
        )
        for feature, values in numeric_values.items()
    }

    profile: dict[str, object] = {
        "profile_version": 2,
        "sample_size": len(rows),
        "categorical": categorical,
        "numeric": numeric,
    }

    if predictions is not None:
        if len(predictions) != len(rows):
            raise ValueError(
                f"Prediction count ({len(predictions)}) must match row count ({len(rows)})."
            )
        profile["categorical"]["prediction"] = categorical_distribution(predictions)  # type: ignore[index]

    return profile


def _status(psi: float, warning_threshold: float, alert_threshold: float) -> str:
    if psi >= alert_threshold:
        return "alert"
    if psi >= warning_threshold:
        return "warning"
    return "ok"


def compare_categorical_profiles(
    reference: Mapping[str, Mapping[str, float]],
    current: Mapping[str, Mapping[str, float]],
    warning_threshold: float = DEFAULT_WARNING_THRESHOLD,
    alert_threshold: float = DEFAULT_ALERT_THRESHOLD,
) -> dict[str, dict[str, float | str]]:
    results: dict[str, dict[str, float | str]] = {}
    for feature, reference_distribution in reference.items():
        current_distribution = current.get(feature, {})
        psi = population_stability_index(reference_distribution, current_distribution)
        results[feature] = {
            "psi": psi,
            "status": _status(psi, warning_threshold, alert_threshold),
        }
    return results


def compare_numeric_profiles(
    reference: Mapping[str, Mapping[str, object]],
    current: Mapping[str, Mapping[str, object]],
    warning_threshold: float = DEFAULT_WARNING_THRESHOLD,
    alert_threshold: float = DEFAULT_ALERT_THRESHOLD,
) -> dict[str, dict[str, float | str]]:
    """Compare numeric distributions using the reference profile's bins."""
    results: dict[str, dict[str, float | str]] = {}
    for feature, reference_profile in reference.items():
        current_profile = current.get(feature, {})
        reference_distribution = reference_profile.get("bin_distribution", {})
        current_distribution = current_profile.get("bin_distribution", {})

        if not isinstance(reference_distribution, dict) or not isinstance(current_distribution, dict):
            results[feature] = {"psi": 0.0, "status": "unavailable"}
            continue

        psi = population_stability_index(
            {str(key): float(value) for key, value in reference_distribution.items()},
            {str(key): float(value) for key, value in current_distribution.items()},
        )

        reference_mean = float(reference_profile.get("mean", 0.0))
        current_mean = float(current_profile.get("mean", 0.0))
        relative_mean_shift = (
            abs(current_mean - reference_mean) / max(abs(reference_mean), 1e-6)
        )

        results[feature] = {
            "psi": psi,
            "status": _status(psi, warning_threshold, alert_threshold),
            "reference_mean": reference_mean,
            "current_mean": current_mean,
            "relative_mean_shift": relative_mean_shift,
        }
    return results


def compare_profiles(
    reference: Mapping[str, object],
    current: Mapping[str, object],
    *,
    threshold: float = DEFAULT_ALERT_THRESHOLD,
    warning_threshold: float = DEFAULT_WARNING_THRESHOLD,
) -> dict[str, object]:
    """Compare full categorical and numeric profiles and return a drift gate."""
    categorical_reference = reference.get("categorical", {})
    categorical_current = current.get("categorical", {})
    numeric_reference = reference.get("numeric", {})
    numeric_current = current.get("numeric", {})

    if not isinstance(categorical_reference, dict) or not isinstance(categorical_current, dict):
        raise ValueError("Invalid categorical drift profile format.")
    if not isinstance(numeric_reference, dict) or not isinstance(numeric_current, dict):
        raise ValueError("Invalid numeric drift profile format.")

    categorical = compare_categorical_profiles(
        categorical_reference,
        categorical_current,
        warning_threshold=warning_threshold,
        alert_threshold=threshold,
    )
    numeric = compare_numeric_profiles(
        numeric_reference,  # type: ignore[arg-type]
        numeric_current,  # type: ignore[arg-type]
        warning_threshold=warning_threshold,
        alert_threshold=threshold,
    )

    all_results = {
        "categorical": categorical,
        "numeric": numeric,
    }
    scored = [
        (feature_type, feature, float(values["psi"]))
        for feature_type, group in all_results.items()
        for feature, values in group.items()
        if "psi" in values
    ]
    scored.sort(key=lambda item: item[2], reverse=True)

    max_psi = scored[0][2] if scored else 0.0
    max_feature = f"{scored[0][0]}.{scored[0][1]}" if scored else None
    drifted_features = [
        f"{feature_type}.{feature}"
        for feature_type, feature, psi in scored
        if psi >= threshold
    ]
    warning_features = [
        f"{feature_type}.{feature}"
        for feature_type, feature, psi in scored
        if warning_threshold <= psi < threshold
    ]

    return {
        "drift_detected": bool(drifted_features),
        "threshold": threshold,
        "warning_threshold": warning_threshold,
        "max_psi": max_psi,
        "max_psi_feature": max_feature,
        "drifted_features": drifted_features,
        "warning_features": warning_features,
        "comparison": all_results,
    }
