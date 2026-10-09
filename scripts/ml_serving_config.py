"""Resolve and validate the Azure ML serving configuration the platform depends on.

The live Azure ML endpoint is the source of truth for which deployment is
active and which registered model version it serves. The FastAPI App Service
only stores copies of these values (AZURE_ML_SCORING_URI,
AZURE_ML_DEPLOYMENT_NAME, AZURE_ML_MODEL_VERSION), and the API reports the
stored version in /predict responses, so the copies must be re-synchronised
whenever traffic moves. This script only READS Azure (az ... show/list); it
never writes. Callers decide what to do with the KEY=VALUE output.

  python -m scripts.ml_serving_config resolve-ml --resource-group RG --workspace WS
  python -m scripts.ml_serving_config resolve-foundry --resource-group RG --app APP
  python -m scripts.ml_serving_config check-env
  python -m scripts.ml_serving_config check-app-settings --template main.json --resource-group RG --app APP
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from typing import Any

MODEL_NAME = "incident-severity"
DEFAULT_ENDPOINT = "incident-severity-endpoint"
SLOTS = {"blue", "green"}
ML_KEYS = ("AZURE_ML_SCORING_URI", "AZURE_ML_DEPLOYMENT_NAME", "AZURE_ML_MODEL_VERSION")
# Settings Bicep passes through from the live App Service (see main.bicepparam).
FOUNDRY_REQUIRED = ("FOUNDRY_AGENT_NAME", "AZURE_AI_MODEL_DEPLOYMENT_NAME")
FOUNDRY_KEYS = ("FOUNDRY_AGENT_NAME", "FOUNDRY_AGENT_VERSION", "AZURE_AI_MODEL_DEPLOYMENT_NAME")


def active_deployment(traffic: dict[str, Any]) -> str:
    """Return the single blue/green slot that receives 100% of traffic."""
    active = [name for name, value in traffic.items() if int(value or 0) > 0]
    if len(active) != 1 or int(traffic[active[0]]) != 100:
        raise ValueError(f"Expected exactly one deployment at 100% traffic, found {traffic!r}")
    if active[0] not in SLOTS:
        raise ValueError(f"Unexpected active deployment {active[0]!r}; expected one of {sorted(SLOTS)}")
    return active[0]


def model_version_from_id(model_id: str, expected_name: str = MODEL_NAME) -> str:
    """Extract the version from an Azure ML model reference."""
    match = re.search(r"models/([^/]+)/versions/(\d+)\s*$", model_id) or re.match(
        r"^azureml:/?([^:/]+):(\d+)\s*$", model_id
    )
    if not match:
        raise ValueError(f"Cannot parse model name/version from {model_id!r}")
    name, version = match.group(1), match.group(2)
    if name != expected_name:
        raise ValueError(f"Active deployment serves model {name!r}, expected {expected_name!r}")
    return version


def validate_ml_settings(values: dict[str, str]) -> list[str]:
    errors = []
    for key in ML_KEYS:
        if not (values.get(key) or "").strip():
            errors.append(f"{key} is missing or empty")
    uri = values.get("AZURE_ML_SCORING_URI", "")
    if uri and not uri.startswith("https://"):
        errors.append(f"AZURE_ML_SCORING_URI must start with https:// (got {uri!r})")
    slot = values.get("AZURE_ML_DEPLOYMENT_NAME", "")
    if slot and slot not in SLOTS:
        errors.append(f"AZURE_ML_DEPLOYMENT_NAME must be one of {sorted(SLOTS)} (got {slot!r})")
    version = values.get("AZURE_ML_MODEL_VERSION", "")
    if version and not (version.isdigit() and int(version) >= 1):
        errors.append(f"AZURE_ML_MODEL_VERSION must be a positive integer (got {version!r})")
    return errors


def declared_app_setting_names(template: dict[str, Any]) -> set[str]:
    names: set[str] = set()
    for resource in template.get("resources", []):
        if resource.get("type") == "Microsoft.Web/sites":
            for setting in resource["properties"]["siteConfig"].get("appSettings", []):
                names.add(setting["name"])
    return names


def live_only_settings(live_names: set[str], declared: set[str]) -> list[str]:
    """Live settings the template does not declare (an ARM deployment would remove them)."""
    return sorted(live_names - declared)


def _az(*args: str) -> Any:
    az = shutil.which("az")
    if not az:
        raise RuntimeError("Azure CLI (az) not found on PATH")
    result = subprocess.run([az, *args, "-o", "json"], capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"az {' '.join(args)} failed: {result.stderr.strip()}")
    return json.loads(result.stdout or "null")


def resolve_ml(endpoint: str, resource_group: str, workspace: str) -> dict[str, str]:
    scope = ["--resource-group", resource_group, "--workspace-name", workspace]
    info = _az("ml", "online-endpoint", "show", "--name", endpoint, *scope)
    slot = active_deployment(info["traffic"])
    deployment = _az("ml", "online-deployment", "show", "--name", slot, "--endpoint-name", endpoint, *scope)
    values = {
        "AZURE_ML_SCORING_URI": info["scoring_uri"],
        "AZURE_ML_DEPLOYMENT_NAME": slot,
        "AZURE_ML_MODEL_VERSION": model_version_from_id(deployment["model"]),
    }
    errors = validate_ml_settings(values)
    if errors:
        raise ValueError("; ".join(errors))
    return values


def resolve_foundry(resource_group: str, app: str) -> dict[str, str]:
    live = {s["name"]: s["value"] for s in _az("webapp", "config", "appsettings", "list",
                                               "--resource-group", resource_group, "--name", app)}
    missing = [key for key in FOUNDRY_REQUIRED if not (live.get(key) or "").strip()]
    if missing:
        raise ValueError(f"Live App Service {app} has no value for {missing}; refusing to pass blanks to Bicep")
    return {key: live.get(key, "") for key in FOUNDRY_KEYS}


def _print_env(values: dict[str, str]) -> None:
    for key, value in values.items():
        print(f"{key}={value}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    ml = sub.add_parser("resolve-ml")
    ml.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    ml.add_argument("--resource-group", required=True)
    ml.add_argument("--workspace", required=True)
    fy = sub.add_parser("resolve-foundry")
    fy.add_argument("--resource-group", required=True)
    fy.add_argument("--app", required=True)
    sub.add_parser("check-env")
    drift = sub.add_parser("check-app-settings")
    drift.add_argument("--template", required=True, help="Compiled ARM template (az bicep build --stdout).")
    drift.add_argument("--resource-group", required=True)
    drift.add_argument("--app", required=True)
    drift.add_argument("--strict", action="store_true", help="Exit 1 if live-only settings exist.")
    args = parser.parse_args()

    try:
        if args.command == "resolve-ml":
            _print_env(resolve_ml(args.endpoint, args.resource_group, args.workspace))
        elif args.command == "resolve-foundry":
            _print_env(resolve_foundry(args.resource_group, args.app))
        elif args.command == "check-env":
            values = {key: os.environ.get(key, "") for key in ML_KEYS}
            errors = validate_ml_settings(values)
            errors += [f"{key} is missing or empty" for key in FOUNDRY_REQUIRED if not os.environ.get(key, "").strip()]
            if errors:
                for error in errors:
                    print(f"::error::{error}")
                return 1
            print("Serving configuration environment is complete.")
        else:
            with open(args.template, encoding="utf-8") as handle:
                declared = declared_app_setting_names(json.load(handle))
            live = {s["name"] for s in _az("webapp", "config", "appsettings", "list",
                                            "--resource-group", args.resource_group, "--name", args.app)}
            extra = live_only_settings(live, declared)
            if extra:
                level = "error" if args.strict else "warning"
                print(f"::{level}::Live App Service settings not declared in main.bicep (a full deployment "
                      f"would REMOVE them): {', '.join(extra)}")
                return 1 if args.strict else 0
            print("Every live App Service setting is declared in the template.")
    except (RuntimeError, ValueError, KeyError) as exc:
        print(f"::error::{exc}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
