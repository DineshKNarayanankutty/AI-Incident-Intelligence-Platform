"""Credential abstraction; no secrets are stored in application code."""
from __future__ import annotations

from typing import Any


def get_default_azure_credential() -> Any:
    """Return DefaultAzureCredential only when an Azure client actually needs it."""
    try:
        from azure.identity import DefaultAzureCredential
    except ImportError as exc:
        raise RuntimeError(
            "Azure authentication dependencies are not installed. "
            "Install requirements.txt before using an Azure backend."
        ) from exc
    return DefaultAzureCredential(exclude_interactive_browser_credential=False)
