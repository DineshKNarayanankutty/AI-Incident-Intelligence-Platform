"""Serving-config discovery, metadata synchronisation and infra preflight guards."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.ml_serving_config import (
    active_deployment,
    declared_app_setting_names,
    live_only_settings,
    model_version_from_id,
    validate_ml_settings,
)

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"


def test_active_deployment_requires_single_slot_at_100():
    assert active_deployment({"blue": 0, "green": 100}) == "green"
    for bad in ({"blue": 50, "green": 50}, {"blue": 0, "green": 0}, {"canary": 100}):
        with pytest.raises(ValueError):
            active_deployment(bad)


@pytest.mark.parametrize(
    "model_id",
    [
        "azureml:/subscriptions/s/resourceGroups/r/providers/Microsoft.MachineLearningServices/workspaces/w/models/incident-severity/versions/2",
        "/subscriptions/s/resourceGroups/r/providers/Microsoft.MachineLearningServices/workspaces/w/models/incident-severity/versions/2",
        "azureml:incident-severity:2",
    ],
)
def test_model_version_is_parsed_from_deployment_model_reference(model_id):
    assert model_version_from_id(model_id) == "2"


def test_model_version_rejects_other_models_and_garbage():
    with pytest.raises(ValueError):
        model_version_from_id("azureml:other-model:2")
    with pytest.raises(ValueError):
        model_version_from_id("azureml:incident-severity:latest")


def test_validate_ml_settings_rejects_empty_or_malformed_values():
    good = {"AZURE_ML_SCORING_URI": "https://e.centralus.inference.ml.azure.com/score",
            "AZURE_ML_DEPLOYMENT_NAME": "green", "AZURE_ML_MODEL_VERSION": "2"}
    assert validate_ml_settings(good) == []
    assert validate_ml_settings({**good, "AZURE_ML_MODEL_VERSION": ""})
    assert validate_ml_settings({**good, "AZURE_ML_SCORING_URI": ""})
    assert validate_ml_settings({**good, "AZURE_ML_DEPLOYMENT_NAME": "red"})
    assert validate_ml_settings({**good, "AZURE_ML_MODEL_VERSION": "v2"})


def test_live_only_settings_are_reported():
    assert live_only_settings({"A", "B", "C"}, {"A", "B"}) == ["C"]


def test_template_declares_every_setting_the_api_needs_and_blanks_none():
    template = json.loads((ROOT / "infra/bicep/main.json").read_text(encoding="utf-8"))
    site = next(r for r in template["resources"] if r["type"] == "Microsoft.Web/sites")
    settings = {s["name"]: s["value"] for s in site["properties"]["siteConfig"]["appSettings"]}
    assert {"AZURE_ML_SCORING_URI", "AZURE_ML_DEPLOYMENT_NAME", "AZURE_ML_MODEL_VERSION"} <= declared_app_setting_names(template)
    for name in ("FOUNDRY_AGENT_NAME", "AZURE_AI_MODEL_DEPLOYMENT_NAME", "FOUNDRY_AGENT_VERSION"):
        assert settings[name] != "", f"{name} must be a parameter pass-through, not a literal blank"
    for param in ("azureMlScoringUri", "azureMlModelVersion", "foundryAgentName", "foundryModelDeploymentName"):
        assert template["parameters"][param]["minLength"] == 1


def test_parameter_file_has_no_hardcoded_serving_values():
    text = (ROOT / "infra/bicep/main.bicepparam").read_text(encoding="utf-8")
    for name in ("AZURE_ML_SCORING_URI", "AZURE_ML_DEPLOYMENT_NAME", "AZURE_ML_MODEL_VERSION",
                 "FOUNDRY_AGENT_NAME", "AZURE_AI_MODEL_DEPLOYMENT_NAME"):
        assert f"readEnvironmentVariable('{name}')" in text


@pytest.mark.parametrize("workflow", ["deployment.yml", "rollback.yml"])
def test_traffic_changing_workflows_resync_all_ml_settings_from_live_endpoint(workflow):
    text = (WORKFLOWS / workflow).read_text(encoding="utf-8")
    assert "scripts.ml_serving_config resolve-ml" in text
    assert "az webapp config appsettings set" in text and "--output none" in text
    assert "AZURE_ML_SCORING_URI=" not in text  # no longer syncs only the URI


def test_infrastructure_workflow_runs_preflight_before_what_if_and_stays_read_only():
    text = (WORKFLOWS / "infrastructure.yml").read_text(encoding="utf-8")
    assert text.index("check-env") < text.index("az deployment group what-if") and text.index("resolve-ml") < text.index("build-params")
    assert "--template-file" not in text  # .bicepparam carries its own `using`
    assert "deployment group create" not in text
