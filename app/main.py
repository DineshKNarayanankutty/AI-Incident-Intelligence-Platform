"""FastAPI application for incident intelligence."""
from __future__ import annotations

from fastapi import FastAPI

from app.api.schemas import IncidentAnalysisRequest, IncidentAnalysisResponse, IncidentRequest
from app.clients.foundry import FoundryAgentClient
from app.core.config import get_settings
from app.services.inference import InferenceService
from genai.prompts.loader import load_prompt

settings = get_settings()
app = FastAPI(title=settings.app_name, version="2.0.0")
inference = InferenceService(settings)
foundry = FoundryAgentClient(settings)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "environment": settings.environment}


@app.post("/predict")
def predict(request: IncidentRequest):
    return inference.predict(request)


@app.post("/analyze", response_model=IncidentAnalysisResponse)
def analyze(request: IncidentAnalysisRequest) -> IncidentAnalysisResponse:
    prediction = inference.predict(request.incident)
    prompt_version = "v2" if request.include_explanation else "v1"
    prompt = load_prompt(prompt_version).format(
        severity=prediction.severity,
        incident=request.incident.model_dump_json(indent=2),
    )
    analysis = foundry.analyze(prompt)
    return IncidentAnalysisResponse(prediction=prediction, analysis=analysis, prompt_version=prompt_version)
