"""Generate a deterministic synthetic incident dataset for local training."""

from __future__ import annotations

import argparse
import csv
import random
from pathlib import Path


FIELDNAMES = [
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
    "severity",
]

SERVICES = ["checkout", "payments", "identity", "orders", "notifications", "search", "analytics", "support"]
REGIONS = ["eastus", "westus", "centralus", "westeurope", "uksouth", "southeastasia"]
INCIDENT_TYPES = ["latency", "availability", "data_quality", "security", "dependency", "capacity", "deployment"]
CUSTOMER_IMPACTS = ["none", "internal", "limited", "broad", "global"]
DETECTED_BY = ["synthetic_monitor", "customer_ticket", "on_call", "log_alert", "security_alert"]
SEVERITIES = ["Low", "Medium", "High", "Critical"]

SIGNAL_PROFILES = {
    "Low": {
        "impact_weights": [0.42, 0.28, 0.22, 0.06, 0.02],
        "detected_by_weights": [0.42, 0.10, 0.18, 0.28, 0.02],
        "duration": (5, 160),
        "users": (0, 900),
        "error_rate": (0.0, 0.12),
        "latency": (80, 1100),
        "phrases": [
            "brief warning threshold breach with stable customer traffic",
            "retry spike with mostly successful automatic recovery",
            "isolated background job delay observed by monitoring",
            "health probe warning while core transactions continue",
        ],
    },
    "Medium": {
        "impact_weights": [0.08, 0.22, 0.42, 0.22, 0.06],
        "detected_by_weights": [0.24, 0.24, 0.20, 0.28, 0.04],
        "duration": (20, 320),
        "users": (40, 3200),
        "error_rate": (0.02, 0.28),
        "latency": (180, 2800),
        "phrases": [
            "elevated latency and intermittent request failures",
            "partial feature degradation reported by support",
            "retry queue growing after dependency timeout",
            "deployment regression causing repeated warning alerts",
        ],
    },
    "High": {
        "impact_weights": [0.02, 0.08, 0.28, 0.48, 0.14],
        "detected_by_weights": [0.08, 0.34, 0.24, 0.24, 0.10],
        "duration": (45, 620),
        "users": (400, 18000),
        "error_rate": (0.08, 0.58),
        "latency": (550, 6500),
        "phrases": [
            "customer-facing outage with sustained request failures",
            "payment authorization failures affecting checkout",
            "authentication errors blocking active sessions",
            "regional availability drop with rising support tickets",
        ],
    },
    "Critical": {
        "impact_weights": [0.01, 0.03, 0.16, 0.44, 0.36],
        "detected_by_weights": [0.04, 0.42, 0.22, 0.14, 0.18],
        "duration": (90, 960),
        "users": (1800, 60000),
        "error_rate": (0.14, 0.95),
        "latency": (900, 12000),
        "phrases": [
            "widespread outage causing repeated transaction failure",
            "possible data exposure under active investigation",
            "data consistency errors detected across customer records",
            "security alert with confirmed customer-facing symptoms",
        ],
    },
}

TYPE_HINTS = {
    "latency": ["slow responses", "timeout", "p95 latency", "request queue"],
    "availability": ["unavailable", "outage", "health probe", "5xx errors"],
    "data_quality": ["missing records", "corrupt payload", "stale data", "schema mismatch"],
    "security": ["unauthorized access", "token misuse", "suspicious login", "policy violation"],
    "dependency": ["upstream timeout", "provider error", "third-party failure", "circuit breaker"],
    "capacity": ["cpu saturation", "memory pressure", "autoscale lag", "queue backlog"],
    "deployment": ["rollback", "release regression", "configuration drift", "bad build"],
}


TYPE_WEIGHTS_BY_SIGNAL = {
    "Low": [3, 1, 1, 1, 1, 2, 2],
    "Medium": [3, 2, 1, 1, 2, 2, 2],
    "High": [2, 3, 2, 2, 3, 2, 2],
    "Critical": [1, 3, 3, 3, 2, 1, 1],
}

SIGNAL_OFFSETS = {
    "Low": [0, 1],
    "Medium": [-1, 0, 1],
    "High": [-1, 0, 1],
    "Critical": [-1, 0],
}

SIGNAL_OFFSET_WEIGHTS = {
    "Low": [0.86, 0.14],
    "Medium": [0.12, 0.76, 0.12],
    "High": [0.14, 0.74, 0.12],
    "Critical": [0.20, 0.80],
}


def _choose_signal_severity(rng: random.Random, severity: str) -> str:
    severity_index = SEVERITIES.index(severity)
    offset = rng.choices(SIGNAL_OFFSETS[severity], weights=SIGNAL_OFFSET_WEIGHTS[severity], k=1)[0]
    signal_index = max(0, min(len(SEVERITIES) - 1, severity_index + offset))
    return SEVERITIES[signal_index]


def _choose_incident_type(rng: random.Random, signal_severity: str) -> str:
    return rng.choices(INCIDENT_TYPES, weights=TYPE_WEIGHTS_BY_SIGNAL[signal_severity], k=1)[0]


def _bool_as_text(value: bool) -> str:
    return "true" if value else "false"


def generate_incident(index: int, rng: random.Random) -> dict[str, str]:
    severity = rng.choices(SEVERITIES, weights=[0.25, 0.35, 0.25, 0.15], k=1)[0]
    signal_severity = _choose_signal_severity(rng, severity)
    profile = SIGNAL_PROFILES[signal_severity]
    incident_type = _choose_incident_type(rng, signal_severity)
    service = rng.choice(SERVICES)
    region = rng.choice(REGIONS)
    impact = rng.choices(CUSTOMER_IMPACTS, weights=profile["impact_weights"], k=1)[0]
    detected_by = rng.choices(DETECTED_BY, weights=profile["detected_by_weights"], k=1)[0]
    duration = rng.randint(*profile["duration"])
    affected_users = rng.randint(*profile["users"])
    error_rate = round(rng.uniform(*profile["error_rate"]), 4)
    latency_ms = rng.randint(*profile["latency"])
    phrase = rng.choice(profile["phrases"])
    hint = rng.choice(TYPE_HINTS[incident_type])

    signal_index = SEVERITIES.index(signal_severity)
    is_security_related = incident_type == "security" and rng.random() < 0.82
    if incident_type != "security" and rng.random() < 0.03 + (signal_index * 0.02):
        is_security_related = True

    data_loss_probability = [0.01, 0.04, 0.10, 0.18][signal_index]
    if incident_type == "data_quality":
        data_loss_probability += 0.12
    has_data_loss = rng.random() < min(data_loss_probability, 0.35)

    readable_type = incident_type.replace("_", " ")
    title = f"{service.title()} {readable_type} incident in {region}"
    description = (
        f"{phrase}. Signals include {hint}, customer impact is {impact}, "
        f"and the incident was detected by {detected_by}."
    )

    return {
        "incident_id": f"INC-{index:05d}",
        "title": title,
        "description": description,
        "service": service,
        "region": region,
        "incident_type": incident_type,
        "customer_impact": impact,
        "detected_by": detected_by,
        "duration_minutes": str(duration),
        "affected_users": str(affected_users),
        "error_rate": str(error_rate),
        "latency_ms": str(latency_ms),
        "has_data_loss": _bool_as_text(has_data_loss),
        "is_security_related": _bool_as_text(is_security_related),
        "severity": severity,
    }


def generate_dataset(output_path: Path, rows: int = 400, seed: int = 42) -> Path:
    if rows < 40:
        raise ValueError("Generate at least 40 rows so the train/test split has all severity classes.")

    rng = random.Random(seed)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    incidents = [generate_incident(index + 1, rng) for index in range(rows)]
    with output_path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(incidents)

    return output_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate synthetic incident data for Phase 1.")
    parser.add_argument("--output", type=Path, default=Path("data/synthetic_incidents.csv"))
    parser.add_argument("--rows", type=int, default=400)
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_path = generate_dataset(args.output, args.rows, args.seed)
    print(f"Wrote synthetic incident dataset: {output_path}")


if __name__ == "__main__":
    main()
