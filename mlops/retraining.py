"""Drift-triggered retraining decision and local retraining adapter."""
from __future__ import annotations

from pathlib import Path

from src.training.drift import build_drift_profile, compare_categorical_profiles
from src.training.train import train_model


def drift_requires_retraining(reference: dict, current: dict, threshold: float = 0.25) -> bool:
    result = compare_categorical_profiles(reference.get("categorical", {}), current.get("categorical", {}))
    return any(float(value["psi"]) >= threshold for value in result.values())


def retrain_if_needed(
    data_path: Path,
    reference_profile_path: Path,
    output_dir: Path,
    tracking_uri: str,
) -> dict:
    # This function is intentionally local-safe. The workflow decides when to call it in Azure.
    import json
    reference = json.loads(reference_profile_path.read_text(encoding="utf-8"))
    rows = __import__("src.training.train", fromlist=["load_rows"]).load_rows(data_path)
    current = build_drift_profile(rows)
    if not drift_requires_retraining(reference, current):
        return {"retrained": False, "reason": "drift_threshold_not_exceeded"}
    summary = train_model(data_path, output_dir, mlflow_tracking_uri=tracking_uri, register_model=False)
    return {"retrained": True, "summary": summary}
