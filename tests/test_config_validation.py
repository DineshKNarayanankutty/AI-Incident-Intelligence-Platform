from pathlib import Path

import yaml


def test_all_yaml_is_parseable() -> None:
    for path in Path(".").glob("azure_ml/**/*.yml"):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert isinstance(data, dict), path


def test_bicep_contains_required_resource_types() -> None:
    text = Path("infra/bicep/main.bicep").read_text(encoding="utf-8")
    for resource_type in [
        "Microsoft.Storage/storageAccounts",
        "Microsoft.MachineLearningServices/workspaces",
        "Microsoft.CognitiveServices/accounts",
        "Microsoft.CognitiveServices/accounts/projects",
        "Microsoft.KeyVault/vaults",
        "Microsoft.Insights/components",
        "Microsoft.OperationalInsights/workspaces",
    ]:
        assert resource_type in text
