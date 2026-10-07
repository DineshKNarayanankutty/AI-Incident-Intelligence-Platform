"""Azure ML managed online endpoint client."""
from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.core.auth import get_default_azure_credential
from app.core.config import Settings


class AzureMLInferenceClient:
    """Call an Azure ML managed online endpoint using Entra ID authentication."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self._credential: Any | None = None

    def _token(self) -> str:
        if self._credential is None:
            self._credential = get_default_azure_credential()
        token = self._credential.get_token("https://ml.azure.com/.default")
        return token.token

    def _endpoint_url(self) -> str:
        url = self.settings.azure_ml_scoring_uri.strip()
        if not url:
            raise ValueError("AZURE_ML_SCORING_URI is required for Azure ML inference.")
        return url

    def _request_payload(self, incident: dict[str, Any]) -> bytes:
        # Azure ML managed online endpoints expect tabular request data under
        # input_data.data for this scoring script.
        return json.dumps(
            {"input_data": {"data": [incident]}}
        ).encode("utf-8")

    @staticmethod
    def _parse_response(raw_body: str) -> Any:
        """Parse both normal JSON responses and JSON strings returned by score.py."""
        body: Any = json.loads(raw_body)

        # The current scoring script returns json.dumps(...), which Azure ML can
        # surface as a JSON string. Decode that second JSON layer when present.
        if isinstance(body, str):
            try:
                body = json.loads(body)
            except json.JSONDecodeError:
                return body

        return body

    def predict(self, incident: dict[str, Any]) -> dict[str, Any]:
        request = Request(
            self._endpoint_url(),
            data=self._request_payload(incident),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._token()}",
                "Accept": "application/json",
            },
            method="POST",
        )

        # The deployment-specific header is useful for safe rollout scenarios.
        # With the current endpoint routing it may be omitted, but setting it
        # makes the client deterministic when blue is the configured deployment.
        deployment = self.settings.azure_ml_deployment_name.strip()
        if deployment:
            request.add_header("azureml-model-deployment", deployment)

        try:
            with urlopen(request, timeout=self.settings.azure_ml_timeout_seconds) as response:
                raw_body = response.read().decode("utf-8")
        except HTTPError as exc:
            details = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(
                f"Azure ML endpoint returned HTTP {exc.code}: {details}"
            ) from exc
        except URLError as exc:
            raise RuntimeError(f"Azure ML endpoint request failed: {exc.reason}") from exc

        body = self._parse_response(raw_body)

        if isinstance(body, dict) and "predictions" in body:
            predictions = body["predictions"]
            if not predictions:
                raise RuntimeError("Azure ML endpoint returned an empty predictions list.")
            prediction = predictions[0]
        elif isinstance(body, list):
            if not body:
                raise RuntimeError("Azure ML endpoint returned an empty response list.")
            prediction = body[0]
        else:
            prediction = body

        if isinstance(prediction, dict):
            return prediction

        return {"severity": prediction}
