"""Feature construction shared by local training and managed online scoring."""
from __future__ import annotations


def _normalize(value: object) -> str:
    return str(value).strip().lower()


def incident_text(row: dict[str, object]) -> str:
    duration_minutes = float(row["duration_minutes"])
    affected_users = float(row["affected_users"])
    error_rate = float(row["error_rate"])
    latency_ms = float(row["latency_ms"])

    return " ".join(
        [
            str(row["title"]),
            str(row["description"]),
            f"service_{_normalize(row['service'])}",
            f"region_{_normalize(row['region'])}",
            f"type_{_normalize(row['incident_type'])}",
            f"impact_{_normalize(row['customer_impact'])}",
            f"detected_{_normalize(row['detected_by'])}",
            f"duration_{_duration_bucket(duration_minutes)}",
            f"users_{_affected_users_bucket(affected_users)}",
            f"error_rate_{_error_rate_bucket(error_rate)}",
            f"latency_{_latency_bucket(latency_ms)}",
            f"data_loss_{_normalize(row['has_data_loss'])}",
            f"security_{_normalize(row['is_security_related'])}",
        ]
    )


def _duration_bucket(value: float) -> str:
    if value < 30:
        return "short"
    if value < 120:
        return "moderate"
    if value < 360:
        return "long"
    return "extended"


def _affected_users_bucket(value: float) -> str:
    if value < 100:
        return "small"
    if value < 1000:
        return "localized"
    if value < 5000:
        return "many"
    if value < 20000:
        return "large"
    return "massive"


def _error_rate_bucket(value: float) -> str:
    if value < 0.03:
        return "low"
    if value < 0.10:
        return "elevated"
    if value < 0.25:
        return "high"
    if value < 0.50:
        return "major"
    return "severe"


def _latency_bucket(value: float) -> str:
    if value < 300:
        return "normal"
    if value < 1000:
        return "slow"
    if value < 2500:
        return "degraded"
    if value < 6000:
        return "bad"
    return "extreme"