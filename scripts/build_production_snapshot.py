"""Build production drift and optional supervised-training snapshots from events."""
from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime
from pathlib import Path

REQUIRED_INPUT_COLUMNS = [
    "incident_id",
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

OUTPUT_COLUMNS = [*REQUIRED_INPUT_COLUMNS, "severity"]


def _recorded_at(payload: dict) -> datetime:
    value = payload.get("recorded_at")
    if not value:
        return datetime.min
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return datetime.min


def _load_events(events_dir: Path) -> list[dict]:
    files = sorted(events_dir.rglob("*.json"))
    if not files:
        raise SystemExit(f"No production event JSON files found under {events_dir}.")

    latest_by_incident: dict[str, dict] = {}
    for path in files:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise SystemExit(f"Invalid production event {path}: {exc}") from exc

        missing = [key for key in REQUIRED_INPUT_COLUMNS if key not in payload]
        if missing:
            raise SystemExit(f"Production event {path} missing fields: {missing}")

        incident_id = str(payload["incident_id"])
        current = latest_by_incident.get(incident_id)
        if current is None or _recorded_at(payload) >= _recorded_at(current):
            latest_by_incident[incident_id] = payload

    return sorted(latest_by_incident.values(), key=_recorded_at, reverse=True)


def _write_csv(rows: list[dict], output: Path, *, severity_key: str) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        for payload in rows:
            writer.writerow({
                **{key: payload[key] for key in REQUIRED_INPUT_COLUMNS},
                "severity": payload[severity_key],
            })


def build_snapshots(
    events_dir: Path,
    drift_output: Path,
    training_output: Path,
    max_rows: int = 1000,
) -> tuple[int, int]:
    rows = _load_events(events_dir)
    drift_rows = rows[:max_rows]

    # Drift monitoring only needs a stable categorical severity field to satisfy
    # the shared incident schema. This is the model prediction, not ground truth.
    for row in drift_rows:
        if not row.get("predicted_severity") and not row.get("observed_severity"):
            raise SystemExit(
                f"Incident {row['incident_id']} has neither predicted_severity nor observed_severity."
            )
        row["drift_severity"] = row.get("predicted_severity") or row.get("observed_severity")

    _write_csv(drift_rows, drift_output, severity_key="drift_severity")

    # Retraining is supervised. Only events with an approved observed severity
    # label are eligible; model predictions are never used as training labels.
    labeled_rows = [row for row in rows if str(row.get("observed_severity") or "").strip()]
    training_rows = labeled_rows[:max_rows]
    if training_rows:
        _write_csv(training_rows, training_output, severity_key="observed_severity")

    print(f"Unique incidents found: {len(rows)}")
    print(f"Drift snapshot rows: {len(drift_rows)}")
    print(f"Ground-truth labeled training rows: {len(training_rows)}")
    if not training_rows:
        print("Training snapshot not written because no ground-truth labels are available.")

    return len(drift_rows), len(training_rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--events-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--training-output", type=Path, required=True)
    parser.add_argument("--max-rows", type=int, default=1000)
    args = parser.parse_args()

    if args.max_rows < 1:
        raise SystemExit("--max-rows must be >= 1")

    build_snapshots(
        args.events_dir,
        args.output,
        args.training_output,
        args.max_rows,
    )


if __name__ == "__main__":
    main()
