"""Generate a controlled incident-data shift for the retraining demonstration.

The source dataset remains untouched. The generated CSV preserves the production
schema and labels while intentionally shifting a small set of features so the
PSI drift gate crosses the retraining threshold.
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

# Make repository packages importable when this file is executed directly with
# ``python scripts/generate_drift_demo.py`` in CI or a local shell.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.training.drift import REQUIRED_COLUMNS


def generate_demo(source: Path, output: Path) -> None:
    with source.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fieldnames = list(reader.fieldnames or [])

    missing = sorted(set(REQUIRED_COLUMNS) - set(fieldnames))
    if missing:
        raise ValueError(f"Source dataset is missing required columns: {missing}")
    if not rows:
        raise ValueError("Source dataset is empty.")

    # Controlled shift: keep labels and text intact, move operational
    # characteristics into a materially different distribution.
    for index, row in enumerate(rows):
        row["region"] = "centralus" if index % 5 else "eastus"
        row["error_rate"] = f"{min(float(row['error_rate']) * 3.5 + 0.20, 0.99):.4f}"
        row["latency_ms"] = str(int(float(row["latency_ms"]) * 2.5 + 500))

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Generated controlled drift dataset: {output}")
    print(f"Rows: {len(rows)}")
    print("Shifted features: region, error_rate, latency_ms")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a controlled drift demo dataset.")
    parser.add_argument("--source", type=Path, default=Path("data/synthetic_incidents.csv"))
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/drift_demo/synthetic_incidents_drifted.csv"),
    )
    args = parser.parse_args()
    generate_demo(args.source, args.output)


if __name__ == "__main__":
    main()
