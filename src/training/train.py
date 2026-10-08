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


from src.training.features import incident_text

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
    evaluation_data_path: Path | None = None,
) -> dict[str, Any]:
    rows = load_rows(data_path)
    features = [incident_text(row) for row in rows]
    labels = [row["severity"] for row in rows]

    # Candidate retraining can use all current/drifted data for fitting and a
    # fixed clean reference dataset for evaluation. This makes the quality gate
    # comparable with the committed production baseline instead of comparing
    # metrics measured on two different holdout distributions.
    if evaluation_data_path is not None:
        evaluation_rows = load_rows(evaluation_data_path)
        evaluation_features = [incident_text(row) for row in evaluation_rows]
        evaluation_labels = [row["severity"] for row in evaluation_rows]
        _, x_test, _, y_test, _, rows_test = train_test_split(
            evaluation_features,
            evaluation_labels,
            evaluation_rows,
            test_size=test_size,
            random_state=random_state,
            stratify=evaluation_labels,
        )
        x_train, y_train, rows_train = features, labels, rows
    else:
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
            "evaluation_mode": "fixed_reference" if evaluation_data_path is not None else "random_holdout",
            "evaluation_data": str(evaluation_data_path) if evaluation_data_path is not None else str(data_path),
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
    parser.add_argument(
        "--evaluation-data",
        type=Path,
        default=None,
        help="Optional fixed reference dataset used only for candidate evaluation.",
    )
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
        evaluation_data_path=args.evaluation_data,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
