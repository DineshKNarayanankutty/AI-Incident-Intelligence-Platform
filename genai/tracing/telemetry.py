"""OpenTelemetry setup with Azure Monitor exporter as an optional cloud sink."""
from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)


def configure_tracing() -> bool:
    connection_string = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING", "")
    if not connection_string:
        return False
    try:
        from azure.monitor.opentelemetry import configure_azure_monitor
        configure_azure_monitor(
            connection_string=connection_string,
            enable_live_metrics=True,
        )
        return True
    except ImportError:
        logger.warning("azure-monitor-opentelemetry is not installed; tracing remains local.")
        return False
