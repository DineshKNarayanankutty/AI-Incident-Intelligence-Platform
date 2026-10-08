from __future__ import annotations

import json
from pathlib import Path

from app.api.schemas import IncidentRequest, PredictionResponse
from app.core.config import Settings
from app.services.production_store import ProductionIncidentStore, safe_record
from scripts.build_production_snapshot import build_snapshots


def _incident() -> IncidentRequest:
    return IncidentRequest(
        incident_id="INC-1",
        title="Checkout timeout",
        description="Requests are timing out.",
        service="checkout",
        region="eastus",
        incident_type="latency",
        customer_impact="broad",
        detected_by="log_alert",
        duration_minutes=10,
        affected_users=100,
        error_rate=0.2,
        latency_ms=2000,
        has_data_loss=False,
        is_security_related=False,
    )


def _prediction() -> PredictionResponse:
    return PredictionResponse(
        incident_id="INC-1",
        severity="High",
        confidence=0.9,
        model_backend="azureml",
        model_version="2",
        trace_id="abc",
    )


def test_store_disabled_by_default() -> None:
    store = ProductionIncidentStore(Settings())
    assert store.enabled is False
    safe_record(store, _incident(), _prediction(), "abc")


def test_build_production_snapshot_uses_latest_unique_incident(tmp_path: Path) -> None:
    events = tmp_path / "events"
    events.mkdir()
    older = _incident().model_dump() | {
        "predicted_severity": "Low",
        "observed_severity": "Low",
        "recorded_at": "2026-10-08T00:00:00+00:00",
    }
    newer = _incident().model_dump() | {
        "predicted_severity": "High",
        "observed_severity": "High",
        "recorded_at": "2026-10-08T01:00:00+00:00",
    }
    (events / "older.json").write_text(json.dumps(older), encoding="utf-8")
    (events / "newer.json").write_text(json.dumps(newer), encoding="utf-8")

    output = tmp_path / "snapshot.csv"
    training = tmp_path / "training.csv"
    drift_rows, training_rows = build_snapshots(events, output, training, max_rows=1000)
    assert drift_rows == 1
    assert training_rows == 1
    text = output.read_text(encoding="utf-8")
    assert "INC-1" in text
    assert ",High" in text
