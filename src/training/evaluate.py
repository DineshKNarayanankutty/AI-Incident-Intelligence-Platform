"""Evaluation helpers for the local severity classifier."""

from __future__ import annotations

from collections import Counter

from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score


def classification_metrics(y_true: list[str], y_pred: list[str], labels: list[str]) -> dict[str, object]:
    report = classification_report(y_true, y_pred, labels=labels, output_dict=True, zero_division=0)
    return {
        "accuracy": accuracy_score(y_true, y_pred),
        "macro_f1": f1_score(y_true, y_pred, labels=labels, average="macro", zero_division=0),
        "weighted_f1": f1_score(y_true, y_pred, labels=labels, average="weighted", zero_division=0),
        "per_class": {label: report[label] for label in labels},
        "confusion_matrix": confusion_matrix(y_true, y_pred, labels=labels).tolist(),
    }


def majority_class_baseline(y_train: list[str], y_test: list[str], labels: list[str]) -> dict[str, object]:
    majority_class = Counter(y_train).most_common(1)[0][0]
    predictions = [majority_class] * len(y_test)
    metrics = classification_metrics(y_test, predictions, labels)
    metrics["majority_class"] = majority_class
    return metrics
