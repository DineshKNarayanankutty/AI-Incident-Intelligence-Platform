"""Azure ML managed online endpoint scoring entrypoint."""
from __future__ import annotations

import json
import os
from pathlib import Path

import joblib

from src.training.features import incident_text


_model = None


def init() -> None:
    global _model
    model_dir = Path(os.environ.get("AZUREML_MODEL_DIR", "."))
    candidates = [model_dir / "model.joblib", model_dir / "outputs" / "model.joblib"]
    for candidate in candidates:
        if candidate.exists():
            _model = joblib.load(candidate)
            return
    # Recursive fallback for registered folder layouts.
    matches = list(model_dir.rglob("model.joblib"))
    if not matches:
        raise FileNotFoundError(f"model.joblib not found below {model_dir}")
    _model = joblib.load(matches[0])


def _normalize(payload: dict) -> list[dict]:
    if "input_data" not in payload:
        return payload if isinstance(payload, list) else [payload]
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


def run(raw_data: str) -> str:
    payload = json.loads(raw_data)
    rows = _normalize(payload)
    features = [incident_text({**row, "severity": "Low"}) for row in rows]
    predictions = _model.predict(features).tolist()
    result = []
    probabilities = _model.predict_proba(features) if hasattr(_model, "predict_proba") else None
    for i, prediction in enumerate(predictions):
        item = {"severity": str(prediction)}
        if probabilities is not None:
            item["confidence"] = float(max(probabilities[i]))
        result.append(item)
    return json.dumps({"predictions": result})


init()
