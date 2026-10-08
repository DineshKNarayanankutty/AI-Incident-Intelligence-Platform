"""Deterministic reference split shared by training, evaluation and the baseline.

The fixed evaluation dataset (data/reference/candidate_evaluation.csv) is the
stratified 25% holdout of data/synthetic_incidents.csv with random_state=42.
Production model v1 was trained on the complementary 75%, so every model is
compared on the same clean rows.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

from sklearn.model_selection import train_test_split

TEST_SIZE = 0.25
RANDOM_STATE = 42


def reference_split(rows: list[dict[str, str]]) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    """Return (train_rows, evaluation_rows) using the fixed protocol."""
    labels = [row["severity"] for row in rows]
    train_rows, evaluation_rows = train_test_split(
        rows,
        test_size=TEST_SIZE,
        random_state=RANDOM_STATE,
        stratify=labels,
    )
    return list(train_rows), list(evaluation_rows)


def dataset_fingerprint(rows: list[dict[str, Any]]) -> str:
    """Line-ending independent SHA-256 of the parsed rows (order sensitive)."""
    canonical = json.dumps(
        [{key: row[key] for key in sorted(row)} for row in rows],
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
