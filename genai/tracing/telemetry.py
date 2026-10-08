"""OpenTelemetry setup for FastAPI, Azure SDKs, and Microsoft Foundry."""
from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)
_configured = False


def _ensure_local_tracer_provider(console_exporter: bool, service_name: str) -> bool:
    """Install a local SDK provider when Azure Monitor is not configured."""
    try:
        from opentelemetry import trace
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider

        provider = trace.get_tracer_provider()
        if provider.__class__.__name__ != "ProxyTracerProvider":
            return True

        provider = TracerProvider(
            resource=Resource.create({"service.name": service_name})
        )

        if console_exporter:
            from opentelemetry.sdk.trace.export import (
                ConsoleSpanExporter,
                SimpleSpanProcessor,
            )

            provider.add_span_processor(
                SimpleSpanProcessor(ConsoleSpanExporter())
            )

        trace.set_tracer_provider(provider)
        logger.info(
            "Local OpenTelemetry tracing configured%s.",
            " with console export" if console_exporter else "",
        )
        return True
    except ImportError:
        logger.warning(
            "OpenTelemetry SDK is not installed; custom tracing is unavailable."
        )
        return False
    except Exception:
        logger.exception("Failed to configure local OpenTelemetry tracing.")
        return False


def configure_tracing() -> bool:
    """Configure Azure Monitor and local OpenTelemetry tracing once.

    Azure Monitor is preferred when a connection string is available. When it
    is not available, a local SDK tracer provider is still installed so custom
    spans receive valid trace IDs during development and tests.
    """
    global _configured
    if _configured:
        return True

    app_insights_connection_string = os.getenv(
        "APPLICATIONINSIGHTS_CONNECTION_STRING", ""
    ).strip()
    console_exporter = (
        os.getenv("OTEL_CONSOLE_EXPORTER", "false").lower() == "true"
    )
    azure_foundry = os.getenv("FOUNDRY_BACKEND", "local").lower() == "azure"
    genai_tracing = (
        os.getenv("AZURE_EXPERIMENTAL_ENABLE_GENAI_TRACING", "false").lower()
        == "true"
    )
    service_name = os.getenv(
        "OTEL_SERVICE_NAME", "ai-incident-intelligence-api"
    ).strip()

    configured = False

    if app_insights_connection_string:
        try:
            from azure.monitor.opentelemetry import configure_azure_monitor

            configure_azure_monitor(
                connection_string=app_insights_connection_string,
                enable_live_metrics=True,
            )
            configured = True
            logger.info("Azure Monitor OpenTelemetry configured.")
        except ImportError:
            logger.warning(
                "azure-monitor-opentelemetry is not installed; "
                "Azure Monitor export is unavailable."
            )
        except Exception:
            logger.exception("Failed to configure Azure Monitor OpenTelemetry.")

    if not configured:
        configured = _ensure_local_tracer_provider(
            console_exporter=console_exporter,
            service_name=service_name,
        )

    if azure_foundry and genai_tracing:
        os.environ["AZURE_EXPERIMENTAL_ENABLE_GENAI_TRACING"] = "true"
        try:
            from azure.ai.projects.telemetry import AIProjectInstrumentor

            AIProjectInstrumentor().instrument()
            configured = True
            logger.info("Microsoft Foundry GenAI tracing instrumentation enabled.")
        except ImportError:
            logger.warning(
                "azure-ai-projects tracing support is unavailable; "
                "custom application spans remain enabled."
            )
        except Exception:
            logger.exception("Failed to enable Microsoft Foundry GenAI tracing.")

    _configured = True
    return configured


def get_tracer(name: str):
    """Return an OpenTelemetry tracer for application-level custom spans."""
    from opentelemetry import trace

    return trace.get_tracer(name)


def current_trace_id() -> str | None:
    """Return the current trace ID as a 32-character hex string when valid."""
    try:
        from opentelemetry import trace

        span = trace.get_current_span()
        context = span.get_span_context()
        if context.is_valid:
            return format(context.trace_id, "032x")
    except Exception:
        logger.debug(
            "Unable to obtain current OpenTelemetry trace ID.",
            exc_info=True,
        )
    return None


def record_exception(span: Any, exc: BaseException) -> None:
    """Record an exception and mark a custom span as failed."""
    try:
        from opentelemetry.trace import Status, StatusCode

        span.record_exception(exc)
        span.set_status(Status(StatusCode.ERROR, str(exc)))
    except Exception:
        logger.debug(
            "Unable to record OpenTelemetry exception.",
            exc_info=True,
        )
