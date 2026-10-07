"""Lightweight deterministic GenAIOps evaluators for incident analysis."""
from __future__ import annotations

import re
from typing import Any


UNSUPPORTED_CAUSAL_PATTERNS = (
    r"\bconfirmed root cause\b",
    r"\broot cause is\b",
    r"\bdefinitely caused by\b",
    r"\bwas caused by\b",
    r"\bresolved successfully\b",
    r"\bhas been fixed\b",
)

ACTION_TERMS = (
    "inspect",
    "check",
    "validate",
    "review",
    "compare",
    "verify",
    "investigate",
    "rollback",
    "correlate",
    "monitor",
    "confirm",
)

SIGNAL_TERMS = (
    "error rate",
    "latency",
    "duration",
    "affected users",
    "customer impact",
    "impact",
    "security",
    "data loss",
    "availability",
    "dependency",
)


def _contains_any(text: str, terms: tuple[str, ...]) -> bool:
    return any(term in text for term in terms)


def _mentions_observed_signal(text: str, incident: dict[str, Any]) -> bool:
    values = (
        str(incident.get("service", "")).lower(),
        str(incident.get("region", "")).lower(),
        str(incident.get("incident_type", "")).lower(),
    )
    return _contains_any(text, SIGNAL_TERMS) or any(value and value in text for value in values)


def evaluate_response(
    output: str,
    expected_severity: str,
    incident: dict[str, Any],
    criteria: list[str] | None = None,
) -> dict[str, float]:
    """Score an incident-analysis response against a small deterministic rubric.

    The evaluator is intentionally transparent and reproducible. It is a baseline QA
    layer, not a substitute for model-based evaluators.
    """
    text = output.lower().strip()
    unsupported_invention = _contains_any(text, UNSUPPORTED_CAUSAL_PATTERNS)

    severity_alignment = float(expected_severity.lower() in text)
    grounding = (
        float(_mentions_observed_signal(text, incident))
        + float("uncertainty" in text or "unknown" in text or "missing" in text)
        + float(not unsupported_invention)
    ) / 3.0

    relevance = (
        float(str(incident.get("service", "")).lower() in text)
        + float("incident" in text or "impact" in text)
        + float("severity" in text)
    ) / 3.0

    actionability = float(_contains_any(text, ACTION_TERMS))

    completeness = (
        float(_contains_any(text, ("impact", "customer")))
        + float(_contains_any(text, ("evidence", "signal", "latency", "error rate")))
        + float(_contains_any(text, ACTION_TERMS))
        + float("uncertainty" in text or "missing" in text)
    ) / 4.0

    overall = (
        severity_alignment * 0.20
        + grounding * 0.30
        + relevance * 0.20
        + completeness * 0.20
        + actionability * 0.10
    )

    # Preserve a transparent mapping to the supplied criteria without changing the
    # deterministic rubric based on free-form criterion wording.
    criteria_coverage = 1.0
    if criteria:
        hits = 0
        for criterion in criteria:
            normalized = criterion.lower()
            if "concise" in normalized:
                hits += int(len(text.split()) <= 180)
            elif "impact" in normalized:
                hits += int("impact" in text or "customer" in text)
            elif "signal" in normalized:
                hits += int(_mentions_observed_signal(text, incident))
            elif "root cause" in normalized or "facts" in normalized or "invent" in normalized:
                hits += int(not unsupported_invention)
            elif "action" in normalized:
                hits += int(actionability > 0)
            elif "severe" in normalized or "severity" in normalized:
                hits += int(severity_alignment > 0)
        criteria_coverage = hits / len(criteria)

    return {
        "severity_alignment": round(severity_alignment, 4),
        "grounding": round(grounding, 4),
        "relevance": round(relevance, 4),
        "completeness": round(completeness, 4),
        "actionability": round(actionability, 4),
        "criteria_coverage": round(criteria_coverage, 4),
        "overall": round(overall, 4),
    }
