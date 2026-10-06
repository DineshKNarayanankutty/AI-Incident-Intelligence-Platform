"""Train and locally register the incident severity classifier."""

from __future__ import annotations

import argparse
import csv
import json
import os
from pathlib import Path
from typing import Any

import joblib
import mlflow
import mlflow.sklearn
from mlflow.exceptions import MlflowException
from mlflow.models import infer_signature
from mlflow.tracking import MlflowClient
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline

from src.data.generate_synthetic_data import FIELDNAMES, SEVERITIES
from src.training.drift import build_drift_profile
from src.training.evaluate import classification_metrics, majority_class_baseline


DEFAULT_TRACKING_URI = "sqlite:///outputs/mlflow/mlflow.db"
DEFAULT_EXPERIMENT = "incident-severity-local"
DEFAULT_MODEL_NAME = "incident-severity-tfidf-logreg"


def load_rows(data_path: Path) -> list[dict[str, str]]:
    with data_path.open("r", newline="", encoding="utf-8") as csv_file:
        reader = csv.DictReader(csv_file)
        rows = list(reader)
    validate_rows(rows)
    return rows


def validate_rows(rows: list[dict[str, str]]) -> None:
    if not rows:
        raise ValueError("Dataset is empty.")

    missing_columns = sorted(set(FIELDNAMES) - set(rows[0]))
    if missing_columns:
        raise ValueError(f"Dataset is missing required columns: {missing_columns}")

    invalid_labels = sorted({row["severity"] for row in rows if row["severity"] not in SEVERITIES})
    if invalid_labels:
        raise ValueError(f"Dataset has invalid severity labels: {invalid_labels}")


def incident_text(row: dict[str, str]) -> str:
    duration_minutes = float(row["duration_minutes"])
    affected_users = float(row["affected_users"])
    error_rate = float(row["error_rate"])
    latency_ms = float(row["latency_ms"])

    return " ".join(
        [
            row["title"],
            row["description"],
            f"service_{row['service']}",
            f"region_{row['region']}",
            f"type_{row['incident_type']}",
            f"impact_{row['customer_impact']}",
            f"detected_{row['detected_by']}",
            f"duration_{_duration_bucket(duration_minutes)}",
            f"users_{_affected_users_bucket(affected_users)}",
            f"error_rate_{_error_rate_bucket(error_rate)}",
            f"latency_{_latency_bucket(latency_ms)}",
            f"data_loss_{row['has_data_loss']}",
            f"security_{row['is_security_related']}",
        ]
    )


def _duration_bucket(value: float) -> str:
    if value < 30:
        return "short"
    if value < 120:
        return "moderate"
    if value < 360:
        return "long"
    return "extended"


def _affected_users_bucket(value: float) -> str:
    if value < 100:
        return "small"
    if value < 1000:
        return "localized"
    if value < 5000:
        return "many"
    if value < 20000:
        return "large"
    return "massive"


def _error_rate_bucket(value: float) -> str:
    if value < 0.03:
        return "low"
    if value < 0.10:
        return "elevated"
    if value < 0.25:
        return "high"
    if value < 0.50:
        return "major"
    return "severe"


def _latency_bucket(value: float) -> str:
    if value < 300:
        return "normal"
    if value < 1000:
        return "slow"
    if value < 2500:
        return "degraded"
    if value < 6000:
        return "bad"
    return "extreme"


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as json_file:
        json.dump(payload, json_file, indent=2, sort_keys=True)
        json_file.write("\n")


def _ensure_registered_model(client: MlflowClient, model_name: str) -> None:
    try:
        client.get_registered_model(model_name)
    except MlflowException:
        client.create_registered_model(model_name)


def train_model(
    data_path: Path,
    output_dir: Path,
    mlflow_tracking_uri: str | None = None,
    experiment_name: str | None = None,
    model_name: str = DEFAULT_MODEL_NAME,
    register_model: bool = True,
    test_size: float = 0.25,
    random_state: int = 42,
) -> dict[str, Any]:
    rows = load_rows(data_path)
    features = [incident_text(row) for row in rows]
    labels = [row["severity"] for row in rows]

    x_train, x_test, y_train, y_test, rows_train, rows_test = train_test_split(
        features,
        labels,
        rows,
        test_size=test_size,
        random_state=random_state,
        stratify=labels,
    )

    pipeline = Pipeline(
        steps=[
            ("tfidf", TfidfVectorizer(ngram_range=(1, 2), min_df=2, max_features=5000)),
            ("classifier", LogisticRegression(max_iter=1000, class_weight="balanced", random_state=random_state)),
        ]
    )

    tracking_uri = mlflow_tracking_uri or os.getenv("MLFLOW_TRACKING_URI", DEFAULT_TRACKING_URI)
    experiment = experiment_name or os.getenv("MLFLOW_EXPERIMENT_NAME", DEFAULT_EXPERIMENT)
    Path("outputs/mlflow").mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    mlflow.set_tracking_uri(tracking_uri)
    mlflow.set_experiment(experiment)

    with mlflow.start_run(run_name="tfidf-logreg-local") as run:
        pipeline.fit(x_train, y_train)
        predictions = pipeline.predict(x_test).tolist()
        metrics = classification_metrics(y_test, predictions, SEVERITIES)
        baseline_metrics = majority_class_baseline(y_train, y_test, SEVERITIES)
        metrics["majority_class_baseline"] = baseline_metrics

        params = {
            "model_type": "TF-IDF + LogisticRegression",
            "tfidf_ngram_range": "1,2",
            "tfidf_min_df": 2,
            "tfidf_max_features": 5000,
            "class_weight": "balanced",
            "train_rows": len(x_train),
            "test_rows": len(x_test),
            "random_state": random_state,
        }

        mlflow.log_params(params)
        mlflow.log_metric("accuracy", float(metrics["accuracy"]))
        mlflow.log_metric("macro_f1", float(metrics["macro_f1"]))
        mlflow.log_metric("weighted_f1", float(metrics["weighted_f1"]))
        mlflow.log_metric("baseline_accuracy", float(baseline_metrics["accuracy"]))
        mlflow.log_metric("baseline_macro_f1", float(baseline_metrics["macro_f1"]))
        mlflow.log_metric("baseline_weighted_f1", float(baseline_metrics["weighted_f1"]))

        model_path = output_dir / "model.joblib"
        metrics_path = output_dir / "metrics.json"
        labels_path = output_dir / "label_order.json"
        drift_path = output_dir / "drift_baseline.json"
        summary_path = output_dir / "run_summary.json"

        joblib.dump(pipeline, model_path)
        write_json(metrics_path, metrics)
        write_json(labels_path, {"labels": SEVERITIES})

        train_predictions = pipeline.predict(x_train).tolist()
        drift_profile = build_drift_profile(rows_train, predictions=train_predictions)
        drift_profile["holdout_profile"] = build_drift_profile(rows_test, predictions=predictions)
        write_json(drift_path, drift_profile)

        mlflow.log_artifact(str(metrics_path))
        mlflow.log_artifact(str(labels_path))
        mlflow.log_artifact(str(drift_path))
        signature = infer_signature(x_train[:5], pipeline.predict(x_train[:5]).tolist())
        mlflow.sklearn.log_model(
            pipeline,
            artifact_path="model",
            signature=signature,
        )

        run_id = run.info.run_id
        model_uri = f"runs:/{run_id}/model"
        registered_model_version = None
        registration_error = None

        if register_model:
            client = MlflowClient(tracking_uri=tracking_uri)
            try:
                _ensure_registered_model(client, model_name)
                registered_model = mlflow.register_model(model_uri=model_uri, name=model_name)
                registered_model_version = registered_model.version
            except Exception as exc:  # Registration should not hide usable local training artifacts.
                registration_error = f"{type(exc).__name__}: {exc}"
                mlflow.set_tag("registration_error", registration_error)

        summary = {
            "run_id": run_id,
            "experiment_name": experiment,
            "tracking_uri": tracking_uri,
            "model_uri": model_uri,
            "registered_model_name": model_name if register_model else None,
            "registered_model_version": registered_model_version,
            "registration_error": registration_error,
            "metrics": {
                "accuracy": metrics["accuracy"],
                "macro_f1": metrics["macro_f1"],
                "weighted_f1": metrics["weighted_f1"],
            },
            "baseline_metrics": {
                "majority_class": baseline_metrics["majority_class"],
                "accuracy": baseline_metrics["accuracy"],
                "macro_f1": baseline_metrics["macro_f1"],
                "weighted_f1": baseline_metrics["weighted_f1"],
            },
            "artifacts": {
                "model": str(model_path),
                "metrics": str(metrics_path),
                "labels": str(labels_path),
                "drift_baseline": str(drift_path),
            },
        }
        write_json(summary_path, summary)
        mlflow.log_artifact(str(summary_path))

    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train the local incident severity classifier.")
    parser.add_argument("--data", type=Path, default=Path("data/synthetic_incidents.csv"))
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/model"))
    parser.add_argument("--mlflow-tracking-uri", default=os.getenv("MLFLOW_TRACKING_URI", DEFAULT_TRACKING_URI))
    parser.add_argument("--experiment-name", default=os.getenv("MLFLOW_EXPERIMENT_NAME", DEFAULT_EXPERIMENT))
    parser.add_argument("--model-name", default=DEFAULT_MODEL_NAME)
    parser.add_argument("--register-model", action="store_true")
    parser.add_argument("--test-size", type=float, default=0.25)
    parser.add_argument("--random-state", type=int, default=42)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary = train_model(
        data_path=args.data,
        output_dir=args.output_dir,
        mlflow_tracking_uri=args.mlflow_tracking_uri,
        experiment_name=args.experiment_name,
        model_name=args.model_name,
        register_model=args.register_model,
        test_size=args.test_size,
        random_state=args.random_state,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
