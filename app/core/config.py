"""Application configuration with environment-only secrets and identifiers."""
from __future__ import annotations

from functools import lru_cache
import os

from pydantic import BaseModel, Field


def _env(*names: str, default: str = "") -> str:
    """Return the first non-empty environment variable from the supplied names."""
    for name in names:
        value = os.getenv(name)
        if value is not None and value.strip():
            return value.strip()
    return default


def _clean_url(value: str) -> str:
    """Normalize URLs copied from PowerShell/CLI output."""
    value = value.strip().strip('"').strip("'")
    if value.startswith("[") and value.endswith("]"):
        value = value[1:-1].strip().strip('"').strip("'")
    return value


class Settings(BaseModel):
    app_name: str = "AI Incident Intelligence Platform"
    environment: str = Field(default="local")
    inference_backend: str = Field(default="local")  # local | azureml
    foundry_backend: str = Field(default="local")  # local | azure
    log_level: str = "INFO"

    model_path: str = "outputs/model/model.joblib"
    drift_baseline_path: str = "outputs/model/drift_baseline.json"

    azure_subscription_id: str = ""
    azure_resource_group: str = ""
    azure_ml_workspace: str = ""
    azure_ml_endpoint_name: str = ""
    azure_ml_deployment_name: str = "blue"
    azure_ml_model_name: str = "incident-severity"
    azure_ml_model_version: str = "1"
    azure_ml_scoring_uri: str = ""
    azure_ml_timeout_seconds: float = 30.0

    foundry_project_endpoint: str = ""
    foundry_agent_name: str = ""
    foundry_agent_version: str = ""
    foundry_model_deployment: str = ""

    applicationinsights_connection_string: str = ""
    otel_service_name: str = "ai-incident-intelligence-api"

    @classmethod
    def from_env(cls) -> "Settings":
        foundry_endpoint = _clean_url(
            _env(
                "AZURE_AI_PROJECT_ENDPOINT",
                "FOUNDRY_PROJECT_ENDPOINT",
            )
        )
        foundry_agent_name = _env("FOUNDRY_AGENT_NAME")

        inference_backend = _env("INFERENCE_BACKEND", default="local").lower()
        explicit_foundry_backend = _env("FOUNDRY_BACKEND").lower()
        if explicit_foundry_backend:
            foundry_backend = explicit_foundry_backend
        elif foundry_endpoint and foundry_agent_name:
            # Make the Azure backend deterministic when a complete Foundry
            # configuration is supplied, even if FOUNDRY_BACKEND was omitted.
            foundry_backend = "azure"
        else:
            foundry_backend = "local"

        return cls(
            app_name=_env("APP_NAME", default="AI Incident Intelligence Platform"),
            environment=_env("APP_ENV", default="local"),
            inference_backend=inference_backend,
            foundry_backend=foundry_backend,
            log_level=_env("LOG_LEVEL", default="INFO"),
            model_path=_env("MODEL_PATH", default="outputs/model/model.joblib"),
            drift_baseline_path=_env(
                "DRIFT_BASELINE_PATH",
                default="outputs/model/drift_baseline.json",
            ),
            azure_subscription_id=_env("AZURE_SUBSCRIPTION_ID"),
            azure_resource_group=_env("AZURE_RESOURCE_GROUP"),
            azure_ml_workspace=_env("AZURE_ML_WORKSPACE"),
            azure_ml_endpoint_name=_env("AZURE_ML_ENDPOINT_NAME"),
            azure_ml_deployment_name=_env("AZURE_ML_DEPLOYMENT_NAME", default="blue"),
            azure_ml_model_name=_env("AZURE_ML_MODEL_NAME", default="incident-severity"),
            azure_ml_model_version=_env("AZURE_ML_MODEL_VERSION", default="1"),
            azure_ml_scoring_uri=_clean_url(_env("AZURE_ML_SCORING_URI")),
            azure_ml_timeout_seconds=float(_env("AZURE_ML_TIMEOUT_SECONDS", default="30")),
            foundry_project_endpoint=foundry_endpoint,
            foundry_agent_name=foundry_agent_name,
            foundry_agent_version=_env("FOUNDRY_AGENT_VERSION"),
            foundry_model_deployment=_env("AZURE_AI_MODEL_DEPLOYMENT_NAME"),
            applicationinsights_connection_string=_env(
                "APPLICATIONINSIGHTS_CONNECTION_STRING"
            ),
            otel_service_name=_env(
                "OTEL_SERVICE_NAME",
                default="ai-incident-intelligence-api",
            ),
        )


@lru_cache
def get_settings() -> Settings:
    return Settings.from_env()
