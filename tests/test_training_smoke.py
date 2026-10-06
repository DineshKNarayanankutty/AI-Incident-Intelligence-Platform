from __future__ import annotations

import json

from src.data.generate_synthetic_data import generate_dataset
from src.training.train import train_model


def test_train_model_smoke(tmp_path) -> None:
    data_path = tmp_path / "incidents.csv"
    output_dir = tmp_path / "model"
    tracking_uri = f"sqlite:///{tmp_path.as_posix()}/mlflow.db"
    generate_dataset(data_path, rows=120, seed=11)

    summary = train_model(
        data_path=data_path,
        output_dir=output_dir,
        mlflow_tracking_uri=tracking_uri,
        experiment_name="pytest-incident-severity",
        model_name="pytest-incident-severity-model",
        register_model=True,
    )

    metrics = json.loads((output_dir / "metrics.json").read_text(encoding="utf-8"))

    assert (output_dir / "model.joblib").exists()
    assert (output_dir / "drift_baseline.json").exists()
    assert summary["registered_model_version"] is not None
    assert summary["registration_error"] is None
    assert "majority_class_baseline" in metrics
    assert summary["metrics"]["macro_f1"] >= 0.6
    assert metrics["accuracy"] >= 0.6
    assert metrics["accuracy"] > metrics["majority_class_baseline"]["accuracy"]
