"""Inference service selecting local or Azure ML without changing API contracts."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import joblib

from app.api.schemas import IncidentRequest, PredictionResponse
from app.clients.azure_ml import AzureMLInferenceClient
from app.core.config import Settings
from src.training.features import incident_text


class LocalInference:
    def __init__(self, model_path: str):
        self.model = joblib.load(Path(model_path))

    def predict(self, incident: dict[str, Any]) -> dict[str, Any]:
        text = incident_text({**incident, "severity": "Low"})
        severity = str(self.model.predict([text])[0])
        confidence = None
        if hasattr(self.model, "predict_proba"):
            probabilities = self.model.predict_proba([text])[0]
            confidence = float(max(probabilities))
        return {"severity": severity, "confidence": confidence}


class InferenceService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.local = LocalInference(settings.model_path) if settings.inference_backend == "local" else None
        self.azure = AzureMLInferenceClient(settings) if settings.inference_backend == "azureml" else None

    def predict(self, incident: IncidentRequest) -> PredictionResponse:
        payload = incident.model_dump()
        if self.settings.inference_backend == "azureml":
            result = self.azure.predict(payload)
            return PredictionResponse(
                incident_id=incident.incident_id,
                severity=str(result["severity"]),
                confidence=float(result["confidence"]) if result.get("confidence") is not None else None,
                model_backend="azureml",
                model_version=self.settings.azure_ml_model_version,
            )
        if self.local is None:
            raise RuntimeError("Local inference backend is not configured.")
        result = self.local.predict(payload)
        return PredictionResponse(
            incident_id=incident.incident_id,
            severity=result["severity"],
            confidence=result["confidence"],
            model_backend="local",
            model_version="local-artifact",
        )
