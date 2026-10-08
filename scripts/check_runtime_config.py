"""Print non-secret runtime configuration used by the FastAPI application."""
from app.core.config import get_settings

settings = get_settings()

print(f"environment={settings.environment}")
print(f"inference_backend={settings.inference_backend}")
print(f"foundry_backend={settings.foundry_backend}")
print(f"foundry_project_endpoint_configured={bool(settings.foundry_project_endpoint)}")
print(f"foundry_agent_name={settings.foundry_agent_name or '<missing>'}")
print(f"azure_ml_scoring_uri_configured={bool(settings.azure_ml_scoring_uri)}")
print(f"applicationinsights_configured={bool(settings.applicationinsights_connection_string)}")
