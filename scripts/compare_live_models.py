from __future__ import annotations

import csv
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from sklearn.metrics import accuracy_score, classification_report, f1_score


RG = "rg-ai-incident-dev-central"
WORKSPACE = "aiincident77a8b195-ml"
ENDPOINT = "incident-severity-endpoint"
DATASET = Path("data/reference/candidate_evaluation.csv")

DEPLOYMENTS = {"green": "2", "blue": "5"}
BATCH_SIZE = 20
LABELS = ["Critical", "High", "Low", "Medium"]

FEATURE_FIELDS = [
    "title",
    "description",
    "service",
    "region",
    "incident_type",
    "customer_impact",
    "detected_by",
    "duration_minutes",
    "affected_users",
    "error_rate",
    "latency_ms",
    "has_data_loss",
    "is_security_related",
]


def run_az(args: list[str]) -> str:
    """Run Azure CLI and return stdout, supporting Windows and Unix."""

    if os.name == "nt":
        command = subprocess.list2cmdline(["az", *args])
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            check=False,
        )
    else:
        result = subprocess.run(
            ["az", *args],
            capture_output=True,
            text=True,
            check=False,
        )

    if result.returncode != 0:
        raise RuntimeError(
            f"Azure CLI command failed: az {' '.join(args)}\n"
            f"Exit code: {result.returncode}\n"
            f"Error: {result.stderr.strip()}"
        )

    return result.stdout.strip()


def decode_json_response(raw: str) -> Any:
    """Decode nested JSON-string wrappers until a JSON object or array appears."""

    value: Any = raw.strip()

    for _ in range(10):
        if isinstance(value, (dict, list)):
            return value

        if not isinstance(value, str):
            break

        text_value = value.strip()

        if not text_value:
            break

        try:
            value = json.loads(text_value)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                "Could not decode Azure ML scoring response as JSON. "
                f"Response starts with: {text_value[:500]!r}"
            ) from exc

    if isinstance(value, (dict, list)):
        return value

    raise RuntimeError(
        "Azure ML response remained a string or unexpected value after "
        "10 decoding attempts. "
        f"Response starts with: {str(value)[:500]!r}"
    )


def verify_live_state() -> None:
    """Fail safely if production traffic or model assignments differ."""

    traffic_raw = run_az([
        "ml", "online-endpoint", "show",
        "--name", ENDPOINT,
        "--resource-group", RG,
        "--workspace-name", WORKSPACE,
        "--query", "traffic",
        "--output", "json",
    ])

    traffic = json.loads(traffic_raw)

    if not isinstance(traffic, dict):
        raise RuntimeError(
            f"Unexpected endpoint traffic response: {traffic!r}"
        )

    if traffic.get("green") != 100 or traffic.get("blue") != 0:
        raise RuntimeError(
            "Unexpected traffic allocation; stopping before inference. "
            f"Actual traffic: {traffic}"
        )

    for deployment, expected_version in DEPLOYMENTS.items():
        details_raw = run_az([
            "ml", "online-deployment", "show",
            "--name", deployment,
            "--endpoint-name", ENDPOINT,
            "--resource-group", RG,
            "--workspace-name", WORKSPACE,
            "--output", "json",
        ])

        details = json.loads(details_raw)

        if details.get("provisioning_state") != "Succeeded":
            raise RuntimeError(
                f"Deployment {deployment} is not in Succeeded state: "
                f"{details.get('provisioning_state')}"
            )

        model_ref = str(details.get("model", ""))
        match = re.search(r"/versions/(\d+)/?$", model_ref)

        if not match or match.group(1) != expected_version:
            raise RuntimeError(
                f"{deployment} does not serve expected model "
                f"version {expected_version}. Actual model reference: "
                f"{model_ref}"
            )

    print("Preflight passed: green=v2 at 100%; blue=v5 at 0%.")


def invoke_batch(
    deployment: str,
    records: list[dict[str, str]],
) -> list[str]:
    """Invoke one deployment directly without changing endpoint traffic."""

    request_path: str | None = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            suffix=".json",
            delete=False,
        ) as handle:
            json.dump(records, handle)
            request_path = handle.name

        raw = run_az([
            "ml", "online-endpoint", "invoke",
            "--name", ENDPOINT,
            "--deployment-name", deployment,
            "--request-file", request_path,
            "--resource-group", RG,
            "--workspace-name", WORKSPACE,
            "--output", "json",
        ])

        payload = decode_json_response(raw)

        if not isinstance(payload, dict):
            raise RuntimeError(
                f"{deployment} returned {type(payload).__name__}, "
                "not a JSON object. "
                f"Response: {str(payload)[:500]}"
            )

        predictions = payload.get("predictions")

        if not isinstance(predictions, list):
            raise RuntimeError(
                f"{deployment} response has no valid 'predictions' list. "
                f"Response: {str(payload)[:500]}"
            )

        if len(predictions) != len(records):
            raise RuntimeError(
                f"{deployment}: expected {len(records)} predictions, "
                f"received {len(predictions)}"
            )

        severities: list[str] = []

        for index, prediction in enumerate(predictions):
            if not isinstance(prediction, dict):
                raise RuntimeError(
                    f"{deployment}: prediction {index} is not an object."
                )

            severity = prediction.get("severity")

            if not isinstance(severity, str) or severity not in LABELS:
                raise RuntimeError(
                    f"{deployment}: invalid severity in prediction "
                    f"{index}: {severity!r}"
                )

            severities.append(severity)

        return severities

    finally:
        if request_path is not None:
            Path(request_path).unlink(missing_ok=True)


def evaluate(
    deployment: str,
    records: list[dict[str, str]],
) -> list[str]:
    """Evaluate every record in small batches."""

    output: list[str] = []

    for start in range(0, len(records), BATCH_SIZE):
        batch = records[start : start + BATCH_SIZE]
        output.extend(invoke_batch(deployment, batch))

        completed = min(start + len(batch), len(records))
        print(f"{deployment}: evaluated {completed}/{len(records)} rows")

    return output


def main() -> None:
    verify_live_state()

    if not DATASET.is_file():
        raise FileNotFoundError(
            f"Evaluation dataset not found: {DATASET}"
        )

    with DATASET.open(
        newline="",
        encoding="utf-8-sig",
    ) as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        columns = set(reader.fieldnames or [])

    required = set(FEATURE_FIELDS + ["severity"])
    missing = required - columns

    if missing:
        raise RuntimeError(
            f"Evaluation dataset is missing columns: {sorted(missing)}"
        )

    if not rows:
        raise RuntimeError("Evaluation dataset contains no rows.")

    records = [
        {field: row[field] for field in FEATURE_FIELDS}
        for row in rows
    ]

    truth = [row["severity"].strip() for row in rows]

    invalid_labels = sorted(set(truth) - set(LABELS))

    if invalid_labels:
        raise RuntimeError(
            f"Unexpected ground-truth severity labels: {invalid_labels}"
        )

    results: dict[str, dict[str, float]] = {}

    for deployment in ("green", "blue"):
        print(f"\nEvaluating deployment: {deployment}")

        predictions = evaluate(deployment, records)

        metrics = {
            "accuracy": float(accuracy_score(truth, predictions)),
            "macro_f1": float(
                f1_score(
                    truth,
                    predictions,
                    labels=LABELS,
                    average="macro",
                    zero_division=0,
                )
            ),
        }

        results[deployment] = metrics

        print(f"\n=== {deployment.upper()} ===")
        print(json.dumps(metrics, indent=2))
        print(
            classification_report(
                truth,
                predictions,
                labels=LABELS,
                zero_division=0,
            )
        )

    print("\n=== BLUE v5 MINUS GREEN v2 ===")

    for metric in ("accuracy", "macro_f1"):
        delta = results["blue"][metric] - results["green"][metric]
        print(f"{metric}: {delta:+.6f}")

    candidate_not_lower = all(
        results["blue"][metric] >= results["green"][metric] - 1e-9
        for metric in ("accuracy", "macro_f1")
    )

    print(
        "\nCandidate metrics not lower than production: "
        f"{candidate_not_lower}"
    )
    print(
        "Comparison complete. No traffic changes or model "
        "registrations made."
    )


if __name__ == "__main__":
    main()