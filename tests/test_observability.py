from __future__ import annotations

import sys
from types import ModuleType

from app.api.schemas import PredictionResponse
from genai.monitoring.metrics import Metrics
from genai.tracing.telemetry import current_trace_id


def test_metrics_snapshot() -> None:
    metrics = Metrics()
    metrics.record("azureml.predict", 100.0, failed=False)
    metrics.record("azureml.predict", 300.0, failed=True)

    snapshot = metrics.snapshot()
    assert snapshot["requests"] == 2
    assert snapshot["failures"] == 1
    assert snapshot["average_latency_ms"] == 200.0
    assert snapshot["operations"]["azureml.predict"]["requests"] == 2
    assert snapshot["operations"]["azureml.predict"]["failures"] == 1


def test_otel_custom_metrics_are_recorded(monkeypatch) -> None:
    calls: list[tuple] = []

    class Instrument:
        def __init__(self, name: str) -> None:
            self.name = name

        def add(self, value: float, attributes: dict[str, str]) -> None:
            calls.append(("add", self.name, value, attributes))

        def record(self, value: float, attributes: dict[str, str]) -> None:
            calls.append(("record", self.name, value, attributes))

    class Meter:
        def create_counter(self, name: str, **kwargs):
            return Instrument(name)

        def create_histogram(self, name: str, **kwargs):
            return Instrument(name)

    from opentelemetry import metrics as otel_metrics

    monkeypatch.setattr(otel_metrics, "get_meter", lambda name: Meter())

    metrics = Metrics()
    metrics.record("foundry.analyze", 250.0, failed=True)

    assert ("add", "incident.operation.requests", 1, {"operation": "foundry.analyze"}) in calls
    assert ("add", "incident.operation.failures", 1, {"operation": "foundry.analyze"}) in calls
    assert ("record", "incident.operation.duration", 250.0, {"operation": "foundry.analyze"}) in calls


def test_prediction_trace_id_optional() -> None:
    response = PredictionResponse(
        incident_id="TEST-1",
        severity="Medium",
        confidence=0.8,
        model_backend="azureml",
        model_version="1",
    )
    assert response.trace_id is None


def test_current_trace_id_outside_span() -> None:
    # Outside an active span the OpenTelemetry API may return None.
    assert current_trace_id() is None


def test_bicep_cloud_observability_settings() -> None:
    from pathlib import Path

    text = Path("infra/bicep/main.bicep").read_text(encoding="utf-8")
    assert "APPLICATIONINSIGHTS_CONNECTION_STRING" in text
    assert "OTEL_SERVICE_NAME" in text
    assert "APPLICATIONINSIGHTS_METRIC_NAMESPACE_OPT_IN" in text


def test_azure_monitor_configuration_uses_app_insights_connection_string(monkeypatch) -> None:
    import genai.tracing.telemetry as telemetry

    captured: dict[str, object] = {}

    azure = ModuleType("azure")
    azure.__path__ = []
    monitor = ModuleType("azure.monitor")
    monitor.__path__ = []
    otel = ModuleType("azure.monitor.opentelemetry")

    def fake_configure_azure_monitor(**kwargs):
        captured.update(kwargs)

    otel.configure_azure_monitor = fake_configure_azure_monitor
    monkeypatch.setitem(sys.modules, "azure", azure)
    monkeypatch.setitem(sys.modules, "azure.monitor", monitor)
    monkeypatch.setitem(sys.modules, "azure.monitor.opentelemetry", otel)
    monkeypatch.setenv(
        "APPLICATIONINSIGHTS_CONNECTION_STRING",
        "InstrumentationKey=test-key;IngestionEndpoint=https://example.test/",
    )
    monkeypatch.setenv("OTEL_SERVICE_NAME", "test-ai-api")
    monkeypatch.setenv("FOUNDRY_BACKEND", "local")
    monkeypatch.setattr(telemetry, "_configured", False)

    assert telemetry.configure_tracing() is True
    assert captured["connection_string"].startswith("InstrumentationKey=test-key")
    assert captured["enable_live_metrics"] is True
