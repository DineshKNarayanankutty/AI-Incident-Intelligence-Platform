from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/drift-monitoring.yml"


def test_production_drift_monitoring_workflow_contract() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "name: Production Drift Monitoring" in text
    assert "schedule:" in text
    assert "cron: '17 2 * * *'" in text
    assert "workflow_dispatch:" in text
    assert "auto_retrain:" in text
    assert "max_rows:" in text
    assert "python -m mlops.drift_check" in text
    assert "--reference data/reference/drift_baseline.json" in text
    assert "--threshold 0.25" in text
    assert "--warning-threshold 0.10" in text
    assert "az storage blob download-batch" in text
    assert "python -m scripts.build_production_snapshot" in text
    assert "production/snapshots/current/incidents.csv" in text
    assert "production-drift-report-${{ github.run_id }}" in text
    assert "gh workflow run retraining.yml" in text
    assert '-f training_data_blob="training/current/incidents.csv"' in text
    assert "actions: write" in text
    assert "id-token: write" in text


def test_monitoring_uses_blob_production_source() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "data/synthetic_incidents.csv" not in text
    assert 'pattern "${EVENTS_PREFIX}/*.json"' in text
    assert "--source \"$CONTAINER\"" in text
    assert "outputs/drift-monitoring/production/current/incidents.csv" in text


def test_monitoring_publishes_snapshot_before_auto_retraining() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    publish = text.index("Publish current production drift snapshot")
    retrain = text.index("Trigger Drift Retraining with labeled production snapshot")
    assert publish < retrain
