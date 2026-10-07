from __future__ import annotations

import json
from unittest.mock import patch

from app.clients.azure_ml import AzureMLInferenceClient
from app.core.config import Settings


class DummyCredential:
    def get_token(self, scope: str):
        assert scope == "https://ml.azure.com/.default"
        return type("Token", (), {"token": "test-token"})()


def test_request_payload_matches_azure_ml_schema() -> None:
    settings = Settings(azure_ml_scoring_uri="https://example.test/score")
    client = AzureMLInferenceClient(settings)

    payload = json.loads(
        client._request_payload({"incident_id": "INC-1"}).decode("utf-8")
    )

    assert payload == {
        "input_data": {
            "data": [{"incident_id": "INC-1"}]
        }
    }


def test_parse_double_encoded_response() -> None:
    raw = json.dumps(
        json.dumps(
            {"predictions": [{"severity": "Medium", "confidence": 0.47}]}
        )
    )

    assert AzureMLInferenceClient._parse_response(raw) == {
        "predictions": [{"severity": "Medium", "confidence": 0.47}]
    }


def test_predict_parses_azure_ml_response(monkeypatch) -> None:
    settings = Settings(
        azure_ml_scoring_uri="https://example.test/score",
        azure_ml_deployment_name="blue",
    )
    client = AzureMLInferenceClient(settings)

    class DummyResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return json.dumps(
                json.dumps(
                    {"predictions": [{"severity": "Medium", "confidence": 0.47}]}
                )
            ).encode("utf-8")

    monkeypatch.setattr(client, "_token", lambda: "test-token")

    with patch("app.clients.azure_ml.urlopen", return_value=DummyResponse()):
        result = client.predict({"incident_id": "INC-1"})

    assert result == {"severity": "Medium", "confidence": 0.47}
