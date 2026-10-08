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
    "data/reference/candidate_evaluation.csv",
    "data/reference/production_model_metrics.json",
    "infra/bicep/main.bicep",
    "infra/bicep/main.json",
    "requirements-runtime.txt",
    "data/reference/drift_baseline.json",
    "data/reference/production_model_metrics.json",
    "scripts/package_api.py",
    "scripts/evaluate_candidate.py",
    "scripts/generate_drift_demo.py",
    "scripts/next_model_version.py",
    "mlops/model_gate.py",
    ".github/workflows/ci.yml",
    ".github/workflows/api-deployment.yml",
    ".github/workflows/deployment.yml",
    ".github/workflows/evaluation.yml",
    ".github/workflows/infrastructure.yml",
    ".github/workflows/retraining.yml",
    ".github/workflows/training.yml",
    ".github/workflows/drift-monitoring.yml",
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

    compute = yaml.safe_load((ROOT / "azure_ml/compute/compute.yml").read_text(encoding="utf-8"))
    if compute.get("size") != "Standard_D4ds_v5":
        raise SystemExit(
            f"Training compute must remain Standard_D4ds_v5; found {compute.get('size')!r}."
        )

    component = yaml.safe_load((ROOT / "azure_ml/components/train.yml").read_text(encoding="utf-8"))
    if component.get("version") != 2:
        raise SystemExit("Training component version must be 2 after the evaluation-protocol change.")

    pipeline = yaml.safe_load((ROOT / "azure_ml/pipeline.yml").read_text(encoding="utf-8"))
    train_inputs = pipeline.get("jobs", {}).get("train", {}).get("inputs", {})
    if "evaluation_data" not in train_inputs:
        raise SystemExit("Azure ML training pipeline must define evaluation_data.")

    baseline = json.loads((ROOT / "data/reference/drift_baseline.json").read_text(encoding="utf-8"))
    if baseline.get("profile_version") != 2:
        raise SystemExit("Drift baseline must use profile_version=2.")
    for feature in ["duration_minutes", "affected_users", "error_rate", "latency_ms", "text_length"]:
        numeric_profile = baseline.get("numeric", {}).get(feature, {})
        if not numeric_profile.get("bin_edges") or not numeric_profile.get("bin_distribution"):
            raise SystemExit(f"Drift baseline is missing numeric bins for {feature}.")

    print(f"Validated {len(REQUIRED_FILES)} required project artifacts; no Azure calls were made.")


if __name__ == "__main__":
    main()
