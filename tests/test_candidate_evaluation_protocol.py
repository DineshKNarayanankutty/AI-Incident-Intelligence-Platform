from __future__ import annotations

from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline

from src.data.generate_synthetic_data import SEVERITIES
from src.training.drift import load_incident_rows
from src.training.features import incident_text
from mlops.model_gate import evaluate_candidate


ROOT = Path(__file__).resolve().parents[1]


def test_candidate_is_evaluated_against_fixed_reference_holdout() -> None:
    reference_path = ROOT / "data" / "synthetic_incidents.csv"
    demo_path = ROOT / "outputs" / "_test_drift_candidate.csv"

    # Recreate the controlled demo in-memory so the test does not require
    # generated artifacts in the repository.
    import csv
    source_rows = load_incident_rows(reference_path)
    demo_rows = [dict(row) for row in source_rows]
    for index, row in enumerate(demo_rows):
        row["description"] = f"{row['description']}{' ' * (600 if index % 2 == 0 else 900)}"

    reference_features = [incident_text(row) for row in source_rows]
    reference_labels = [row["severity"] for row in source_rows]
    _, _, _, _, _, reference_holdout = train_test_split(
        reference_features,
        reference_labels,
        source_rows,
        test_size=0.25,
        random_state=42,
        stratify=reference_labels,
    )

    candidate_features = [incident_text(row) for row in demo_rows]
    candidate_labels = [row["severity"] for row in demo_rows]

    candidate_model = Pipeline([
        ("tfidf", TfidfVectorizer(ngram_range=(1, 2), min_df=2, max_features=5000)),
        ("classifier", LogisticRegression(max_iter=1000, class_weight="balanced", random_state=42)),
    ])
    candidate_model.fit(candidate_features, candidate_labels)

    eval_features = [incident_text(row) for row in reference_holdout]
    eval_labels = [row["severity"] for row in reference_holdout]
    predictions = candidate_model.predict(eval_features)

    candidate_metrics = {
        "accuracy": accuracy_score(eval_labels, predictions),
        "macro_f1": f1_score(
            eval_labels,
            predictions,
            labels=SEVERITIES,
            average="macro",
            zero_division=0,
        ),
    }
    production_metrics = {
        "model_name": "incident-severity",
        "model_version": "1",
        "accuracy": 0.80,
        "macro_f1": 0.809,
    }

    result = evaluate_candidate(candidate_metrics, production_metrics)
    assert result["passed"] is True
    assert candidate_metrics["macro_f1"] >= production_metrics["macro_f1"]
