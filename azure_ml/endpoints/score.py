"""Azure ML managed online endpoint scoring entrypoint."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any


# Azure ML executes this file from azure_ml/endpoints/.
# Add the repository root so the sibling src/ package is importable.
PROJECT_ROOT = Path(__file__).resolve().parents[1]

if not (PROJECT_ROOT / "src").is_dir():
    raise RuntimeError(
        f"Expected project root containing src/: {PROJECT_ROOT}"
    )

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


import joblib
import mlflow

from src.training.features import incident_text


_model: Any = None


def init() -> None:
    global _model

    model_dir = Path(os.environ.get("AZUREML_MODEL_DIR", "."))

    # Case 1: custom Joblib artifact.
    joblib_candidates = [
        model_dir / "model.joblib",
        model_dir / "outputs" / "model.joblib",
    ]

    for candidate in joblib_candidates:
        if candidate.exists():
            _model = joblib.load(candidate)
            return

    joblib_matches = list(model_dir.rglob("model.joblib"))
    if joblib_matches:
        _model = joblib.load(joblib_matches[0])
        return

    # Case 2: MLflow model registered from the training run.
    mlmodel_matches = list(model_dir.rglob("MLmodel"))
    if mlmodel_matches:
        mlflow_model_dir = mlmodel_matches[0].parent
        _model = mlflow.pyfunc.load_model(str(mlflow_model_dir))
        return

    raise FileNotFoundError(
        f"No supported model artifact found below {model_dir}"
    )


def _normalize(payload: dict | list) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return payload

    if "input_data" not in payload:
        return [payload]

    data = payload["input_data"]

    if isinstance(data, list):
        return data

    if isinstance(data, dict) and "data" in data:
        rows = data["data"]
        columns = data.get("columns", [])

        if rows and isinstance(rows[0], dict):
            return rows

        return [dict(zip(columns, row)) for row in rows]

    raise ValueError("Unsupported input_data format")


def run(raw_data: str | dict | list) -> str:
    if isinstance(raw_data, str):
        payload = json.loads(raw_data)
    else:
        payload = raw_data

    rows = _normalize(payload)

    features = [
        incident_text({**row, "severity": "Low"})
        for row in rows
    ]

    predictions = _model.predict(features)

    if hasattr(predictions, "tolist"):
        predictions = predictions.tolist()

    probabilities = (
        _model.predict_proba(features)
        if hasattr(_model, "predict_proba")
        else None
    )

    result = []

    for index, prediction in enumerate(predictions):
        item = {
            "severity": str(prediction)
        }

        if probabilities is not None:
            item["confidence"] = float(max(probabilities[index]))

        result.append(item)

    return json.dumps({
        "predictions": result
    })