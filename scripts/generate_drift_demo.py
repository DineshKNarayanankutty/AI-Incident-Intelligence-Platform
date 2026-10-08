"""Generate a controlled drift dataset without changing model semantics.

The demo intentionally changes only the monitored ``text_length`` statistic by
adding whitespace to incident descriptions. TF-IDF tokenization ignores the
added whitespace, so the candidate model sees the same tokens/features while
the drift detector still observes a material distribution shift.

The committed production dataset is never modified.
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

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

    # Add whitespace only. This changes the monitored text_length distribution
    # but does not change TF-IDF tokens used by the production classifier.
    for index, row in enumerate(rows):
        padding = 600 if index % 2 == 0 else 900
        row["description"] = f"{row['description']}{' ' * padding}"

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Generated controlled drift dataset: {output}")
    print(f"Rows: {len(rows)}")
    print("Shifted monitoring statistic: text_length (whitespace only)")


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
