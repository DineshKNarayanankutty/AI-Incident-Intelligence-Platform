from __future__ import annotations

import csv

import numpy as np
from pathlib import Path

from scripts.generate_drift_demo import generate_demo
from src.data.generate_synthetic_data import generate_dataset
from src.training.drift import build_drift_profile, compare_profiles, load_incident_rows
from src.training.features import incident_text
from src.data.generate_synthetic_data import SEVERITIES
from mlops.model_gate import evaluate_candidate
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline


def test_demo_generator_preserves_schema_and_creates_drift(tmp_path: Path) -> None:
    source = tmp_path / "source.csv"
    demo = tmp_path / "demo.csv"
    generate_dataset(source, rows=250, seed=42)

    generate_demo(source, demo)

    with source.open(newline="", encoding="utf-8") as handle:
        source_fields = next(csv.reader(handle))
    with demo.open(newline="", encoding="utf-8") as handle:
        demo_fields = next(csv.reader(handle))

    assert demo_fields == source_fields

    reference_rows = load_incident_rows(source)
    current_rows = load_incident_rows(demo)
    reference = build_drift_profile(reference_rows)
    current = build_drift_profile(current_rows, reference_numeric=reference["numeric"])
    result = compare_profiles(reference, current)

    assert result["drift_detected"] is True
    assert "numeric.text_length" in result["drifted_features"]


def test_demo_dataset_preserves_candidate_quality_gate(tmp_path: Path) -> None:
    source = tmp_path / "source.csv"
    demo = tmp_path / "demo.csv"
    generate_dataset(source, rows=400, seed=42)
    generate_demo(source, demo)

    rows = load_incident_rows(demo)
    features = [incident_text(row) for row in rows]
    labels = [row["severity"] for row in rows]
    x_train, x_test, y_train, y_test = train_test_split(
        features, labels, test_size=0.25, random_state=42, stratify=labels
    )
    model = Pipeline([
        ("tfidf", TfidfVectorizer(ngram_range=(1, 2), min_df=2, max_features=5000)),
        ("classifier", LogisticRegression(max_iter=1000, class_weight="balanced", random_state=42)),
    ])
    model.fit(x_train, y_train)
    predictions = model.predict(x_test)
    candidate = {
        "accuracy": accuracy_score(y_test, predictions),
        "macro_f1": f1_score(y_test, predictions, labels=SEVERITIES, average="macro", zero_division=0),
    }
    production = {
        "model_name": "incident-severity",
        "model_version": "1",
        "accuracy": 0.80,
        "macro_f1": 0.809,
    }
    gate = evaluate_candidate(candidate, production)
    assert gate["passed"] is True

    # The demo must not change model tokens; it only changes whitespace.
    source_features = [incident_text(row) for row in load_incident_rows(source)]
    demo_features = [incident_text(row) for row in rows]
    vectorizer = TfidfVectorizer(ngram_range=(1, 2), min_df=2, max_features=5000)
    source_matrix = vectorizer.fit_transform(source_features)
    demo_matrix = vectorizer.transform(demo_features)
    assert np.allclose(source_matrix.toarray(), demo_matrix.toarray())
