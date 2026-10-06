"""API request/response schemas."""
from __future__ import annotations

from pydantic import BaseModel, Field


class IncidentRequest(BaseModel):
    incident_id: str = Field(default="LOCAL-00001")
    title: str
    description: str
    service: str
    region: str
    incident_type: str
    customer_impact: str
    detected_by: str
    duration_minutes: float
    affected_users: float
    error_rate: float
    latency_ms: float
    has_data_loss: bool
    is_security_related: bool


class PredictionResponse(BaseModel):
    incident_id: str
    severity: str
    confidence: float | None = None
    model_backend: str
    model_version: str | None = None


class IncidentAnalysisRequest(BaseModel):
    incident: IncidentRequest
    include_explanation: bool = True


class IncidentAnalysisResponse(BaseModel):
    prediction: PredictionResponse
    analysis: str
    prompt_version: str
