from __future__ import annotations

from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential


class FoundryAgentClient:
    def __init__(self, settings) -> None:
        self.settings = settings

        self.project = AIProjectClient(
            endpoint=settings.foundry_project_endpoint,
            credential=DefaultAzureCredential(),
            allow_preview=True,
        )

        self.openai = self.project.get_openai_client(
            agent_name=settings.foundry_agent_name,
        )

    def analyze(self, prompt: str) -> str:
        response = self.openai.responses.create(
            input=prompt,
        )

        return response.output_text