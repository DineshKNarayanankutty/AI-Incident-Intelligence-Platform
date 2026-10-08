"""FastAPI application for incident intelligence."""
from __future__ import annotations

# Configure OpenTelemetry before importing FastAPI so supported framework
# instrumentation can attach to the application correctly.
from genai.tracing.telemetry import configure_tracing

configure_tracing()

from fastapi import FastAPI

from app.api.schemas import (
    IncidentAnalysisRequest,
    IncidentAnalysisResponse,
    IncidentRequest,
)
from app.clients.foundry import FoundryAgentClient
from app.core.config import get_settings
from app.services.inference import InferenceService
from app.services.production_store import ProductionIncidentStore, safe_record
from genai.monitoring.metrics import runtime_metrics
from genai.prompts.loader import load_prompt
from genai.tracing.telemetry import current_trace_id, get_tracer, record_exception


settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version="2.0.0",
)

# Lazy initialization prevents local model loading during pytest/module import.
inference: InferenceService | None = None

foundry = FoundryAgentClient(settings)
production_store = ProductionIncidentStore(settings)
tracer = get_tracer("ai-incident-intelligence.api")


def get_inference_service() -> InferenceService:
    """Create the inference service only when inference is actually requested."""
    global inference

    if inference is None:
        inference = InferenceService(settings)

    return inference


@app.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "environment": settings.environment,
        "inference_backend": settings.inference_backend,
        "foundry_backend": settings.foundry_backend,
    }


@app.get("/metrics")
def metrics() -> dict:
    """Expose lightweight runtime counters without request payloads."""
    return runtime_metrics.snapshot()


@app.post("/predict")
def predict(request: IncidentRequest):
    with tracer.start_as_current_span("incident.predict") as span:
        span.set_attribute("app.operation", "predict")
        span.set_attribute(
            "app.inference_backend",
            settings.inference_backend,
        )

        try:
            result = get_inference_service().predict(request)
            safe_record(production_store, request, result, current_trace_id())

            return result.model_copy(
                update={"trace_id": current_trace_id()}
            )

        except Exception as exc:
            record_exception(span, exc)
            raise


@app.post("/analyze", response_model=IncidentAnalysisResponse)
def analyze(
    request: IncidentAnalysisRequest,
) -> IncidentAnalysisResponse:
    with tracer.start_as_current_span("incident.analyze") as span:
        prompt_version = (
            "v2" if request.include_explanation else "v1"
        )

        span.set_attribute("app.operation", "analyze")
        span.set_attribute("app.prompt_version", prompt_version)
        span.set_attribute(
            "app.agent_name",
            settings.foundry_agent_name,
        )
        span.set_attribute(
            "app.agent_version",
            settings.foundry_agent_version,
        )

        try:
            prediction = get_inference_service().predict(
                request.incident
            )

            prompt = load_prompt(prompt_version).format(
                severity=prediction.severity,
                incident=request.incident.model_dump_json(
                    indent=2
                ),
            )

            analysis = foundry.analyze(
                prompt,
                prompt_version=prompt_version,
            )

            trace_id = current_trace_id()
            safe_record(production_store, request.incident, prediction, trace_id)

            prediction = prediction.model_copy(
                update={"trace_id": trace_id}
            )

            return IncidentAnalysisResponse(
                prediction=prediction,
                analysis=analysis,
                prompt_version=prompt_version,
                trace_id=trace_id,
            )

        except Exception as exc:
            record_exception(span, exc)
            raise
