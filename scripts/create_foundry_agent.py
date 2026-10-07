import os

from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import PromptAgentDefinition
from azure.identity import DefaultAzureCredential


def main() -> None:
    project_endpoint = os.environ["AZURE_AI_PROJECT_ENDPOINT"]
    agent_name = os.environ["FOUNDRY_AGENT_NAME"]

    with AIProjectClient(
        endpoint=project_endpoint,
        credential=DefaultAzureCredential(),
        allow_preview=True,
    ) as project:

        agent = project.agents.create_version(
            agent_name=agent_name,
            definition=PromptAgentDefinition(
                model="incident-gpt",
                instructions=(
                    "You are an incident operations copilot for an SRE/MLOps team. "
                    "Analyze only the incident information provided. "
                    "Never invent telemetry, root cause, or remediation results. "
                    "Keep responses concise, factual, and actionable."
                ),
            ),
        )

        print(f"Agent name: {agent.name}")
        print(f"Agent version: {agent.version}")


if __name__ == "__main__":
    main()