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
    assert "data_path:" in text
    assert "auto_retrain:" in text
    assert "python -m mlops.drift_check" in text
    assert "--reference data/reference/drift_baseline.json" in text
    assert "--threshold 0.25" in text
    assert "--warning-threshold 0.10" in text
    assert "production-drift-report-${{ github.run_id }}" in text
    assert "gh workflow run retraining.yml" in text
    assert "-f demo_drift=false" in text
    assert "actions: write" in text


def test_custom_monitoring_dataset_never_dispatches_retraining() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "steps.config.outputs.data_path == 'data/synthetic_incidents.csv'" in text
    assert "steps.config.outputs.data_path != 'data/synthetic_incidents.csv'" in text
