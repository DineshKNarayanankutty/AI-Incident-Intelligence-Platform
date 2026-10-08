from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/retraining.yml"


def test_retraining_accepts_current_production_training_blob() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "training_data_blob:" in text
    assert "Download production training snapshot" in text
    assert "outputs/production-training/incidents.csv" in text
    assert "jobs.train.inputs.training_data.path" in text
    assert "training_data_blob" in text


def test_retraining_keeps_fixed_clean_evaluation_data() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "evaluation_data always comes from azure_ml/pipeline.yml" in text
    assert "data/reference/candidate_evaluation.csv" in text


def test_retraining_never_uses_prediction_only_snapshot() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "production/training/current/incidents.csv" not in text or "training_data_blob" in text
    assert "demo_drift" in text
    assert "DEMO_DRIFT" in text
