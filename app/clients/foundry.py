"""Microsoft Foundry agent client with tracing and a local-safe fallback."""
from __future__ import annotations

from time import monotonic

from app.core.auth import get_default_azure_credential
from app.core.config import Settings
from genai.monitoring.metrics import runtime_metrics
from genai.tracing.telemetry import get_tracer, record_exception


class FoundryAgentClient:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._tracer = get_tracer("ai-incident-intelligence.foundry")

    def analyze(self, prompt: str, prompt_version: str | None = None) -> str:
        with self._tracer.start_as_current_span("foundry.agent.invoke") as span:
            span.set_attribute("app.backend", self.settings.foundry_backend)
            span.set_attribute("app.agent_name", self.settings.foundry_agent_name)
            span.set_attribute(
                "app.agent_version", self.settings.foundry_agent_version
            )
            if prompt_version:
                span.set_attribute("app.prompt_version", prompt_version)

            started = monotonic()
            try:
                if self.settings.foundry_backend == "local":
                    result = (
                        "LOCAL DEMO ANALYSIS: "
                        "Use the incident severity, customer impact, error rate, latency, "
                        "duration, and security/data-loss signals to explain the operational risk."
                    )
                    runtime_metrics.record(
                        "foundry.analyze",
                        (monotonic() - started) * 1000,
                        failed=False,
                    )
                    return result

                if self.settings.foundry_backend != "azure":
                    raise ValueError(
                        "FOUNDRY_BACKEND must be either 'local' or 'azure'."
                    )

                if (
                    not self.settings.foundry_project_endpoint
                    or not self.settings.foundry_agent_name
                ):
                    raise ValueError(
                        "AZURE_AI_PROJECT_ENDPOINT (or FOUNDRY_PROJECT_ENDPOINT) "
                        "and FOUNDRY_AGENT_NAME are required for the Azure Foundry backend."
                    )

                try:
                    from azure.ai.projects import AIProjectClient
                except ImportError as exc:
                    raise RuntimeError(
                        "Install azure-ai-projects to use the Azure Foundry backend."
                    ) from exc

                with AIProjectClient(
                    endpoint=self.settings.foundry_project_endpoint,
                    credential=get_default_azure_credential(),
                    allow_preview=True,
                ) as project:
                    openai = project.get_openai_client(
                        agent_name=self.settings.foundry_agent_name,
                    )
                    response = openai.responses.create(input=prompt)
                    result = response.output_text

                runtime_metrics.record(
                    "foundry.analyze",
                    (monotonic() - started) * 1000,
                    failed=False,
                )
                return result
            except Exception as exc:
                runtime_metrics.record(
                    "foundry.analyze",
                    (monotonic() - started) * 1000,
                    failed=True,
                )
                span.set_attribute("app.success", False)
                record_exception(span, exc)
                raise
