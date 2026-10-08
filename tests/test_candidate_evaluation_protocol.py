"""Candidate evaluation uses the fixed clean holdout, never the candidate's own data."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from mlops.model_gate import evaluate_candidate
from mlops.retraining import retrain_if_needed
from scripts.build_candidate_evaluation import write_evaluation_csv
from scripts.generate_drift_demo import generate_demo
from src.training.reference_split import dataset_fingerprint, reference_split
from src.training.train import load_rows, train_model

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data" / "synthetic_incidents.csv"
EVALUATION = ROOT / "data" / "reference" / "candidate_evaluation.csv"
BASELINE = ROOT / "data" / "reference" / "production_model_metrics.json"
DRIFT_BASELINE = ROOT / "data" / "reference" / "drift_baseline.json"


def test_committed_evaluation_set_is_the_deterministic_holdout(tmp_path):
    _, expected = reference_split(load_rows(SOURCE))
    committed = load_rows(EVALUATION)
    assert committed == expected
    assert len(committed) == 100

    rebuilt = tmp_path / "rebuilt.csv"
    write_evaluation_csv(expected, rebuilt)
    assert dataset_fingerprint(load_rows(rebuilt)) == dataset_fingerprint(committed)


def test_production_baseline_is_full_precision_on_the_fixed_set():
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    assert baseline["evaluation_dataset"] == "data/reference/candidate_evaluation.csv"
    assert baseline["evaluation_random_state"] == 42
    assert baseline["evaluation_dataset_sha256"] == dataset_fingerprint(load_rows(EVALUATION))
    assert baseline["macro_f1"] != 0.809  # not the rounded value
    assert round(baseline["accuracy"], 2) == 0.80 and round(baseline["macro_f1"], 3) == 0.809


def test_training_uses_evaluation_data_as_is_and_keeps_it_out_of_training(tmp_path):
    summary = train_model(
        SOURCE, tmp_path / "m", mlflow_tracking_uri=f"sqlite:///{tmp_path / 'ml.db'}",
        register_model=False, evaluation_data_path=EVALUATION,
    )
    metrics = json.loads((tmp_path / "m" / "metrics.json").read_text(encoding="utf-8"))
    assert metrics["evaluation_rows"] == 100  # not re-split
    assert metrics["train_rows"] == 300
    assert metrics["training_rows_excluded_as_evaluation_overlap"] == 100
    assert metrics["evaluation_dataset_sha256"] == dataset_fingerprint(load_rows(EVALUATION))
    assert summary["metrics"]["accuracy"] == metrics["accuracy"]


def test_controlled_demo_detects_drift_and_candidate_passes_gate(tmp_path):
    drifted = tmp_path / "drifted.csv"
    generate_demo(SOURCE, drifted)

    result = retrain_if_needed(
        drifted, DRIFT_BASELINE, tmp_path / "candidate",
        tracking_uri=f"sqlite:///{tmp_path / 'ml.db'}",
        production_metrics_path=BASELINE,
        evaluation_data_path=EVALUATION,
    )

    assert result["drift"]["drift_detected"] is True
    assert result["retrained"] is True
    gate = result["candidate_gate"]
    assert gate["passed"] is True, gate
    assert all(gate["checks"].values())
    assert gate["checks"]["same_evaluation_dataset"] is True


def test_bad_candidate_fails_gate_on_fixed_evaluation(tmp_path):
    rows = load_rows(SOURCE)
    labels = sorted({r["severity"] for r in rows})
    for index, row in enumerate(rows):  # corrupt labels: a deliberately bad candidate
        row["severity"] = labels[(index * 7) % len(labels)]
    bad = tmp_path / "bad.csv"
    write_evaluation_csv(rows, bad)

    train_model(
        bad, tmp_path / "m", mlflow_tracking_uri=f"sqlite:///{tmp_path / 'ml.db'}",
        register_model=False, evaluation_data_path=EVALUATION,
    )
    candidate = json.loads((tmp_path / "m" / "metrics.json").read_text(encoding="utf-8"))
    gate = evaluate_candidate(candidate, json.loads(BASELINE.read_text(encoding="utf-8")))

    assert gate["passed"] is False
    assert gate["checks"]["candidate_accuracy_meets_minimum"] is False
    assert gate["checks"]["candidate_accuracy_not_below_production"] is False


def test_gate_rejects_mismatched_evaluation_datasets():
    gate = evaluate_candidate(
        {"accuracy": 0.9, "macro_f1": 0.9, "evaluation_dataset_sha256": "a"},
        {"accuracy": 0.8, "macro_f1": 0.8, "evaluation_dataset_sha256": "b"},
    )
    assert gate["passed"] is False
    assert gate["checks"]["same_evaluation_dataset"] is False
