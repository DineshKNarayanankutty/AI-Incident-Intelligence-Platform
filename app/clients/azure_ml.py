"""Azure ML managed online endpoint client."""
from __future__ import annotations

import json
from typing import Any
import urllib.request

from app.core.auth import get_default_azure_credential
from app.core.config import Settings


class AzureMLInferenceClient:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._credential = None

    def _token(self) -> str:
        if self._credential is None:
            self._credential = get_default_azure_credential()
        token = self._credential.get_token("https://ml.azure.com/.default")
        return token.token

    def _endpoint_url(self) -> str:
        if not self.settings.azure_ml_endpoint_name:
            raise ValueError("AZURE_ML_ENDPOINT_NAME is required for Azure ML inference.")
        if not self.settings.azure_subscription_id or not self.settings.azure_resource_group or not self.settings.azure_ml_workspace:
            raise ValueError("Azure subscription, resource group, and workspace are required.")
        # The scoring URL is normally retrieved once from `az ml online-endpoint show`.
        # Keeping it as an env var avoids hardcoding regional URLs.
        import os
        url = os.getenv("AZURE_ML_SCORING_URI", "")
        if not url:
            raise ValueError("AZURE_ML_SCORING_URI is required for Azure ML inference.")
        return url

    def predict(self, incident: dict[str, Any]) -> dict[str, Any]:
        payload = json.dumps({"input_data": [incident]}).encode("utf-8")
        request = urllib.request.Request(
            self._endpoint_url(),
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._token()}",
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            body = json.loads(response.read().decode("utf-8"))
        if isinstance(body, dict) and "predictions" in body:
            prediction = body["predictions"][0]
        elif isinstance(body, list):
            prediction = body[0]
        else:
            prediction = body
        if isinstance(prediction, dict):
            return prediction
        return {"severity": prediction}
