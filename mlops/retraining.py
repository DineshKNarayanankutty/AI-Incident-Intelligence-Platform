"""Drift-gated retraining adapter.

This module intentionally stops after creating a candidate training run. Model
registration, deployment, promotion, and rollback remain later lifecycle steps.
"""
from __future__ import annotations

import json
from pathlib import Path

from src.training.drift import build_drift_profile, compare_profiles
from src.training.train import load_rows, train_model


def drift_requires_retraining(reference: dict, current: dict, threshold: float = 0.25) -> bool:
    result = compare_profiles(reference, current, threshold=threshold)
    return bool(result["drift_detected"])


def retrain_if_needed(
    data_path: Path,
    reference_profile_path: Path,
    output_dir: Path,
    tracking_uri: str,
    threshold: float = 0.25,
) -> dict:
    reference = json.loads(reference_profile_path.read_text(encoding="utf-8"))
    rows = load_rows(data_path)
    current = build_drift_profile(rows, reference_numeric=reference.get("numeric", {}))
    drift_result = compare_profiles(reference, current, threshold=threshold)

    if not drift_result["drift_detected"]:
        return {
            "retrained": False,
            "reason": "drift_threshold_not_exceeded",
            "drift": drift_result,
        }

    summary = train_model(
        data_path,
        output_dir,
        mlflow_tracking_uri=tracking_uri,
        register_model=False,
    )
    return {
        "retrained": True,
        "reason": "drift_threshold_exceeded",
        "drift": drift_result,
        "summary": summary,
    }
