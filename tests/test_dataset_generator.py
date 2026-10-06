from __future__ import annotations

import csv

from src.data.generate_synthetic_data import FIELDNAMES, SEVERITIES, generate_dataset


def test_generate_dataset_writes_expected_schema_and_labels(tmp_path) -> None:
    output_path = tmp_path / "synthetic_incidents.csv"

    generate_dataset(output_path, rows=80, seed=7)

    with output_path.open("r", newline="", encoding="utf-8") as csv_file:
        rows = list(csv.DictReader(csv_file))

    assert len(rows) == 80
    assert list(rows[0].keys()) == FIELDNAMES
    assert {row["severity"] for row in rows}.issubset(set(SEVERITIES))
    assert len({row["severity"] for row in rows}) >= 3
    assert all(row["incident_id"].startswith("INC-") for row in rows)
    assert all(row["severity"].lower() not in row["title"].lower() for row in rows)


def test_generate_dataset_is_reproducible_with_fixed_seed(tmp_path) -> None:
    first_path = tmp_path / "first.csv"
    second_path = tmp_path / "second.csv"

    generate_dataset(first_path, rows=80, seed=42)
    generate_dataset(second_path, rows=80, seed=42)

    assert first_path.read_text(encoding="utf-8") == second_path.read_text(encoding="utf-8")
