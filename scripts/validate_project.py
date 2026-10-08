"""Static validation that does not contact Azure."""
from __future__ import annotations

import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]

REQUIRED_FILES = [
    "azure_ml/data/incident-data.yml",
    "azure_ml/compute/compute.yml",
    "azure_ml/environments/training-environment.yml",
    "azure_ml/components/train.yml",
    "azure_ml/pipeline.yml",
    "azure_ml/model.yml",
    "azure_ml/endpoints/managed-endpoint.yml",
    "azure_ml/endpoints/managed-deployment.yml",
    "infra/bicep/main.bicep",
    "infra/bicep/main.json",
    "requirements-runtime.txt",
    "data/reference/drift_baseline.json",
    "scripts/package_api.py",
    ".github/workflows/ci.yml",
    ".github/workflows/api-deployment.yml",
    ".github/workflows/deployment.yml",
    ".github/workflows/evaluation.yml",
    ".github/workflows/infrastructure.yml",
    ".github/workflows/retraining.yml",
    ".github/workflows/training.yml",
]


def main() -> None:
    missing = [path for path in REQUIRED_FILES if not (ROOT / path).exists()]
    if missing:
        raise SystemExit(f"Missing required project files: {missing}")

    for path in ROOT.glob("azure_ml/**/*.yml"):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise SystemExit(f"Invalid YAML document: {path}")
    for path in ROOT.glob(".github/workflows/*.yml"):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or "jobs" not in data:
            raise SystemExit(f"Invalid workflow: {path}")

    schema = json.loads((ROOT / "data/schema/incident.schema.json").read_text(encoding="utf-8"))
    assert schema["required"]
    print(f"Validated {len(REQUIRED_FILES)} required project artifacts; no Azure calls were made.")


if __name__ == "__main__":
    main()
