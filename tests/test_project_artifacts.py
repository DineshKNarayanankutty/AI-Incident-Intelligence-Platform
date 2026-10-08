from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_bicep_compiled_artifact_matches_s1_default() -> None:
    template = json.loads((ROOT / "infra/bicep/main.json").read_text(encoding="utf-8"))
    parameter = template["parameters"]["apiPlanSku"]
    assert parameter["defaultValue"] == "S1"
    assert parameter["allowedValues"] == ["F1", "B1", "S1"]

    serverfarm = next(
        resource
        for resource in template["resources"]
        if resource["type"] == "Microsoft.Web/serverfarms"
    )
    assert "Standard" in serverfarm["sku"]["tier"]


def test_reference_drift_baseline_is_present() -> None:
    baseline = json.loads(
        (ROOT / "data/reference/drift_baseline.json").read_text(encoding="utf-8")
    )
    assert "categorical" in baseline
    assert "numeric" in baseline
    assert {"service", "region", "incident_type", "customer_impact", "detected_by"} <= set(baseline["categorical"])
    assert baseline["profile_version"] == 2
    for feature in ("duration_minutes", "affected_users", "error_rate", "latency_ms", "text_length"):
        assert "bin_edges" in baseline["numeric"][feature]
        assert "bin_distribution" in baseline["numeric"][feature]


def test_required_workflow_set_is_present() -> None:
    workflows = {path.name for path in (ROOT / ".github/workflows").glob("*.yml")}
    assert {
        "ci.yml",
        "api-deployment.yml",
        "deployment.yml",
        "evaluation.yml",
        "infrastructure.yml",
        "retraining.yml",
        "training.yml",
        "rollback.yml",
    } <= workflows
