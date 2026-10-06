from __future__ import annotations

import json
from pathlib import Path

from src.data.generate_synthetic_data import FIELDNAMES, SEVERITIES


def test_schema_contains_required_dataset_fields() -> None:
    schema = json.loads(Path("data/schema/incident.schema.json").read_text(encoding="utf-8"))

    assert schema["required"] == FIELDNAMES
    assert schema["properties"]["severity"]["enum"] == SEVERITIES

