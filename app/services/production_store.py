"""Production incident event persistence in Azure Blob Storage."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
from typing import Any
from uuid import uuid4

from app.api.schemas import IncidentRequest, PredictionResponse
from app.core.config import Settings

logger = logging.getLogger(__name__)


class ProductionIncidentStore:
    """Append-only event store for incidents observed by the production API.

    Storage is disabled by default so local development and tests remain
    completely offline. In Azure, DefaultAzureCredential uses the App Service
    managed identity; no storage key or connection string is required.
    """

    def __init__(self, settings: Settings):
        self.enabled = settings.production_snapshot_enabled
        self.container_name = settings.production_snapshot_container
        self.events_prefix = settings.production_events_prefix.strip("/")
        self._container_client = None

        if not self.enabled:
            return

        if not settings.azure_storage_account_name:
            raise RuntimeError(
                "AZURE_STORAGE_ACCOUNT_NAME is required when "
                "PRODUCTION_SNAPSHOT_ENABLED=true."
            )

        from azure.identity import DefaultAzureCredential
        from azure.storage.blob import BlobServiceClient

        account_url = (
            f"https://{settings.azure_storage_account_name}.blob.core.windows.net"
        )
        credential = DefaultAzureCredential(
            exclude_interactive_browser_credential=True
        )
        service_client = BlobServiceClient(
            account_url=account_url,
            credential=credential,
        )
        self._container_client = service_client.get_container_client(
            self.container_name
        )

    def record(
        self,
        incident: IncidentRequest,
        prediction: PredictionResponse,
        trace_id: str | None,
    ) -> None:
        """Persist one production observation without storing secrets."""
        if not self.enabled or self._container_client is None:
            return

        observed_at = datetime.now(timezone.utc)
        payload: dict[str, Any] = {
            **incident.model_dump(),
            "predicted_severity": prediction.severity,
            # Ground-truth severity is intentionally not inferred from the model
            # output. It can be populated later by an approved labeling process.
            "observed_severity": None,
            "model_backend": prediction.model_backend,
            "model_version": prediction.model_version,
            "trace_id": trace_id,
            "recorded_at": observed_at.isoformat(),
        }

        blob_name = (
            f"{self.events_prefix}/{observed_at:%Y/%m/%d}/"
            f"{observed_at:%Y%m%dT%H%M%S.%fZ}-{uuid4().hex}.json"
        )

        self._container_client.upload_blob(
            name=blob_name,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            overwrite=False,
            content_type="application/json",
        )


def safe_record(
    store: ProductionIncidentStore,
    incident: IncidentRequest,
    prediction: PredictionResponse,
    trace_id: str | None,
) -> None:
    """Best-effort persistence so storage outages never break inference."""
    try:
        store.record(incident, prediction, trace_id)
    except Exception:
        logger.exception(
            "Failed to persist production incident observation; "
            "the API response will continue. incident_id=%s",
            incident.incident_id,
        )
