from __future__ import annotations

import os

os.environ["INFERENCE_BACKEND"] = "local"
os.environ["FOUNDRY_BACKEND"] = "local"

from fastapi.testclient import TestClient

from app.main import app


def test_health() -> None:
    response = TestClient(app).get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_predict(monkeypatch) -> None:
    from app.api.schemas import PredictionResponse
    import app.main as main_module

    class FakeInferenceService:
        def predict(self, incident):
            return PredictionResponse(
                incident_id=incident.incident_id,
                severity="High",
                confidence=0.91,
                model_backend="local",
                model_version="test",
            )

    monkeypatch.setattr(
        main_module,
        "get_inference_service",
        lambda: FakeInferenceService(),
    )

    payload = {
        "incident_id": "TEST-1",
        "title": "Checkout timeout",
        "description": "Customer requests are timing out.",
        "service": "checkout",
        "region": "eastus",
        "incident_type": "latency",
        "customer_impact": "broad",
        "detected_by": "log_alert",
        "duration_minutes": 180,
        "affected_users": 9000,
        "error_rate": 0.3,
        "latency_ms": 4000,
        "has_data_loss": False,
        "is_security_related": False,
    }

    response = TestClient(app).post("/predict", json=payload)

    assert response.status_code == 200
    assert response.json()["severity"] == "High"
    assert response.json()["confidence"] == 0.91