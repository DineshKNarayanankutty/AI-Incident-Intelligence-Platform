"""Prompt optimization comparison utilities."""
from __future__ import annotations

from genai.evaluation.runner import compare_reports


def compare_prompt_versions(v1_report: dict, v2_report: dict) -> dict:
    comparison = compare_reports(v1_report, v2_report)
    comparison["recommendation"] = (
        "Promote V2 only if the aggregate score improves without a grounding regression."
        if comparison["winner"] == "v2"
        else "Keep V1 until V2 improves without a grounding regression."
    )
    return comparison
