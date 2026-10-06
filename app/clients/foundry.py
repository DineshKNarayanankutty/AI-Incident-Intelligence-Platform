"""Microsoft Foundry agent client with a local-safe fallback boundary."""
from __future__ import annotations

from typing import Any

from app.core.auth import get_default_azure_credential
from app.core.config import Settings


class FoundryAgentClient:
    def __init__(self, settings: Settings):
        self.settings = settings

    def analyze(self, prompt: str) -> str:
        if self.settings.foundry_backend == "local":
            return (
                "LOCAL DEMO ANALYSIS: "
                "Use the incident severity, customer impact, error rate, latency, "
                "duration, and security/data-loss signals to explain the operational risk."
            )

        if not self.settings.foundry_project_endpoint or not self.settings.foundry_agent_name:
            raise ValueError("AZURE_AI_PROJECT_ENDPOINT and FOUNDRY_AGENT_NAME are required.")

        try:
            from azure.ai.projects import AIProjectClient
        except ImportError as exc:
            raise RuntimeError("Install azure-ai-projects to use the Azure Foundry backend.") from exc

        project = AIProjectClient(
            endpoint=self.settings.foundry_project_endpoint,
            credential=get_default_azure_credential(),
            allow_preview=True,
        )
        openai = project.get_openai_client(agent_name=self.settings.foundry_agent_name)
        response = openai.responses.create(input=prompt)
        return response.output_text
