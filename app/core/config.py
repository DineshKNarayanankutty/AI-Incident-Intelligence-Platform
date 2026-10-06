"""Application configuration with environment-only secrets and identifiers."""
from __future__ import annotations

from functools import lru_cache
from pydantic import BaseModel, Field
import os


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

    foundry_project_endpoint: str = ""
    foundry_agent_name: str = ""
    foundry_agent_version: str = ""
    foundry_model_deployment: str = ""

    applicationinsights_connection_string: str = ""
    otel_service_name: str = "ai-incident-intelligence-api"

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            app_name=os.getenv("APP_NAME", "AI Incident Intelligence Platform"),
            environment=os.getenv("APP_ENV", "local"),
            inference_backend=os.getenv("INFERENCE_BACKEND", "local"),
            foundry_backend=os.getenv("FOUNDRY_BACKEND", "local"),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            model_path=os.getenv("MODEL_PATH", "outputs/model/model.joblib"),
            drift_baseline_path=os.getenv("DRIFT_BASELINE_PATH", "outputs/model/drift_baseline.json"),
            azure_subscription_id=os.getenv("AZURE_SUBSCRIPTION_ID", ""),
            azure_resource_group=os.getenv("AZURE_RESOURCE_GROUP", ""),
            azure_ml_workspace=os.getenv("AZURE_ML_WORKSPACE", ""),
            azure_ml_endpoint_name=os.getenv("AZURE_ML_ENDPOINT_NAME", ""),
            azure_ml_deployment_name=os.getenv("AZURE_ML_DEPLOYMENT_NAME", "blue"),
            azure_ml_model_name=os.getenv("AZURE_ML_MODEL_NAME", "incident-severity"),
            azure_ml_model_version=os.getenv("AZURE_ML_MODEL_VERSION", "1"),
            foundry_project_endpoint=os.getenv("AZURE_AI_PROJECT_ENDPOINT", ""),
            foundry_agent_name=os.getenv("FOUNDRY_AGENT_NAME", ""),
            foundry_agent_version=os.getenv("FOUNDRY_AGENT_VERSION", ""),
            foundry_model_deployment=os.getenv("AZURE_AI_MODEL_DEPLOYMENT_NAME", ""),
            applicationinsights_connection_string=os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING", ""),
            otel_service_name=os.getenv("OTEL_SERVICE_NAME", "ai-incident-intelligence-api"),
        )


@lru_cache
def get_settings() -> Settings:
    return Settings.from_env()
