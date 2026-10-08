from __future__ import annotations

import csv
from pathlib import Path

from scripts.generate_drift_demo import generate_demo
from src.data.generate_synthetic_data import generate_dataset
from src.training.drift import build_drift_profile, compare_profiles, load_incident_rows


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
    assert "categorical.region" in result["drifted_features"]
    assert any(
        feature in result["drifted_features"]
        for feature in {"numeric.error_rate", "numeric.latency_ms"}
    )
