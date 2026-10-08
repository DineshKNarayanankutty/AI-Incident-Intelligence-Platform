"""Drift-gated candidate retraining and quality-gate helpers."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from mlops.model_gate import evaluate_candidate, load_metrics
from src.training.drift import build_drift_profile, compare_profiles
from src.training.train import load_rows, train_model


def drift_requires_retraining(reference: dict, current: dict, threshold: float = 0.25) -> bool:
    result = compare_profiles(reference, current, threshold=threshold)
    return bool(result["drift_detected"])


def evaluate_candidate_metrics(
    candidate_metrics_path: Path,
    production_metrics_path: Path = Path("data/reference/production_model_metrics.json"),
    *,
    min_accuracy: float = 0.80,
    min_macro_f1: float = 0.80,
) -> dict[str, Any]:
    return evaluate_candidate(
        load_metrics(candidate_metrics_path),
        load_metrics(production_metrics_path),
        min_accuracy=min_accuracy,
        min_macro_f1=min_macro_f1,
    )


def retrain_if_needed(
    data_path: Path,
    reference_profile_path: Path,
    output_dir: Path,
    tracking_uri: str,
    threshold: float = 0.25,
    production_metrics_path: Path = Path("data/reference/production_model_metrics.json"),
    min_accuracy: float = 0.80,
    min_macro_f1: float = 0.80,
    evaluation_data_path: Path | None = Path("data/reference/candidate_evaluation.csv"),
) -> dict[str, Any]:
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
        evaluation_data_path=evaluation_data_path,
    )
    candidate_gate = evaluate_candidate_metrics(
        output_dir / "metrics.json",
        production_metrics_path,
        min_accuracy=min_accuracy,
        min_macro_f1=min_macro_f1,
    )
    return {
        "retrained": True,
        "reason": "drift_threshold_exceeded",
        "drift": drift_result,
        "summary": summary,
        "candidate_gate": candidate_gate,
    }
