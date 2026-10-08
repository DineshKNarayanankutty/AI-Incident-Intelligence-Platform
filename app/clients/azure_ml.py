"""Azure ML managed online endpoint client with OpenTelemetry spans."""
from __future__ import annotations

import json
import os
from time import monotonic
from typing import Any

from urllib.request import Request, urlopen

from app.core.auth import get_default_azure_credential
from app.core.config import Settings
from genai.monitoring.metrics import runtime_metrics
from genai.tracing.telemetry import get_tracer, record_exception


class AzureMLInferenceClient:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._credential = None
        self._tracer = get_tracer("ai-incident-intelligence.azureml")

    def _token(self) -> str:
        if self._credential is None:
            self._credential = get_default_azure_credential()

        token = self._credential.get_token(
            "https://ml.azure.com/.default"
        )
        return token.token

    def _endpoint_url(self) -> str:
        url = (
            self.settings.azure_ml_scoring_uri
            or os.getenv("AZURE_ML_SCORING_URI", "")
        ).strip()

        if not url:
            raise ValueError(
                "AZURE_ML_SCORING_URI is required for Azure ML inference."
            )

        if not url.startswith("https://"):
            raise ValueError(
                "AZURE_ML_SCORING_URI must be a valid https:// URL. "
                "Do not include brackets or surrounding quotes."
            )

        return url

    @staticmethod
    def _request_payload(incident: dict[str, Any]) -> bytes:
        """Build the Azure ML managed online endpoint request payload."""
        return json.dumps(
            {
                "input_data": {
                    "data": [incident],
                }
            }
        ).encode("utf-8")

    @staticmethod
    def _parse_response(raw: str) -> dict[str, Any]:
        """Parse normal and double-encoded Azure ML JSON responses."""
        body: Any = json.loads(raw)

        # Some endpoint responses can be JSON encoded twice.
        if isinstance(body, str):
            body = json.loads(body)

        if isinstance(body, dict):
            if "predictions" in body:
                return body

            return {
                "predictions": [body],
            }

        if isinstance(body, list):
            return {
                "predictions": body,
            }

        raise ValueError(
            f"Unexpected Azure ML response type: {type(body).__name__}"
        )

    def predict(self, incident: dict[str, Any]) -> dict[str, Any]:
        with self._tracer.start_as_current_span(
            "azureml.predict"
        ) as span:
            span.set_attribute("app.backend", "azureml")
            span.set_attribute(
                "app.endpoint_name",
                self.settings.azure_ml_endpoint_name,
            )
            span.set_attribute(
                "app.deployment_name",
                self.settings.azure_ml_deployment_name,
            )
            span.set_attribute(
                "app.model_name",
                self.settings.azure_ml_model_name,
            )
            span.set_attribute(
                "app.model_version",
                self.settings.azure_ml_model_version,
            )

            started = monotonic()

            try:
                request = Request(
                    self._endpoint_url(),
                    data=self._request_payload(incident),
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {self._token()}",
                    },
                    method="POST",
                )

                with urlopen(request, timeout=30) as response:
                    body = self._parse_response(
                        response.read().decode("utf-8")
                    )

                prediction = body["predictions"][0]

                if not isinstance(prediction, dict):
                    prediction = {
                        "severity": prediction,
                    }

                span.set_attribute(
                    "app.prediction_success",
                    True,
                )

                runtime_metrics.record(
                    "azureml.predict",
                    (monotonic() - started) * 1000,
                    failed=False,
                )

                return prediction

            except Exception as exc:
                span.set_attribute(
                    "app.prediction_success",
                    False,
                )

                runtime_metrics.record(
                    "azureml.predict",
                    (monotonic() - started) * 1000,
                    failed=True,
                )

                record_exception(span, exc)
                raise
