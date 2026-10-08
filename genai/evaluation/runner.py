"""Local-first GenAIOps evaluation runner with optional Foundry execution."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Callable

from genai.evaluation.evaluators import evaluate_response
from genai.evaluation.gate import DEFAULT_MIN_OVERALL, run_gate
from genai.prompts.loader import load_prompt


def load_dataset(path: Path) -> list[dict]:
    cases: list[dict] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            case = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSONL at {path}:{line_number}") from exc
        if not {"id", "incident", "expected_severity", "criteria"}.issubset(case):
            raise ValueError(f"Missing required fields at {path}:{line_number}")
        cases.append(case)
    if not cases:
        raise ValueError(f"Evaluation dataset is empty: {path}")
    return cases


def build_prompt(prompt_version: str, case: dict) -> str:
    return load_prompt(prompt_version).format(
        severity=case["expected_severity"],
        incident=json.dumps(case["incident"], indent=2),
    )


def aggregate_scores(results: list[dict]) -> dict[str, float]:
    keys = (
        "severity_alignment",
        "grounding",
        "relevance",
        "completeness",
        "actionability",
        "criteria_coverage",
        "overall",
    )
    return {
        key: round(sum(item["scores"][key] for item in results) / len(results), 4)
        for key in keys
    }


def run_evaluation(
    dataset_path: Path,
    prompt_version: str,
    responder: Callable[[str], str],
    output_path: Path,
) -> dict:
    cases = load_dataset(dataset_path)
    results: list[dict] = []

    for case in cases:
        prompt = build_prompt(prompt_version, case)
        output = responder(prompt)
        scores = evaluate_response(
            output=output,
            expected_severity=case["expected_severity"],
            incident=case["incident"],
            criteria=case.get("criteria", []),
        )
        results.append(
            {
                "id": case["id"],
                "expected_severity": case["expected_severity"],
                "output": output,
                "scores": scores,
            }
        )

    report = {
        "prompt_version": prompt_version,
        "dataset": str(dataset_path),
        "case_count": len(results),
        "averages": aggregate_scores(results),
        "cases": results,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def compare_reports(v1: dict, v2: dict) -> dict:
    v1_scores = v1["averages"]
    v2_scores = v2["averages"]
    delta = {key: round(v2_scores[key] - v1_scores[key], 4) for key in v1_scores}

    # Safety/grounding regression blocks promotion even if the aggregate improves.
    grounding_regression = delta["grounding"] < 0
    winner = "v1" if grounding_regression or v2_scores["overall"] < v1_scores["overall"] else "v2"

    return {
        "v1": v1_scores,
        "v2": v2_scores,
        "delta_v2_minus_v1": delta,
        "grounding_regression": grounding_regression,
        "winner": winner,
    }


def _local_responder(prompt: str) -> str:
    """Credential-free responder used to validate evaluation plumbing."""
    import re

    match = re.search(r"Predicted severity:\s*([A-Za-z]+)", prompt)
    severity = match.group(1) if match else "unknown"
    return (
        f"The predicted severity is {severity}. "
        "Observed customer impact and operational signals support the assessment. "
        "The available signals should be validated before declaring root cause. "
        "Next actions are to inspect the affected service, dependency health, "
        "error rate, latency, recent changes, and monitoring data. "
        "Uncertainty remains around the underlying root cause."
    )


def _foundry_responder() -> Callable[[str], str]:
    from app.clients.foundry import FoundryAgentClient
    from app.core.config import Settings

    client = FoundryAgentClient(Settings.from_env())
    return client.analyze


def main() -> None:
    parser = argparse.ArgumentParser(description="Run GenAIOps prompt evaluations.")
    parser.add_argument("--dataset", type=Path, default=Path("genai/evaluation/dataset.jsonl"))
    parser.add_argument("--prompt", choices=["v1", "v2", "both"], default="both")
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/evaluation"))
    parser.add_argument("--backend", choices=["local", "foundry"], default="local")
    parser.add_argument("--quality-gate", action="store_true", help="Run the promotion quality gate after comparing V1 and V2.")
    parser.add_argument("--min-overall", type=float, default=DEFAULT_MIN_OVERALL, help="Minimum V2 overall score required by the quality gate.")
    args = parser.parse_args()

    responder = _local_responder if args.backend == "local" else _foundry_responder()
    versions = ["v1", "v2"] if args.prompt == "both" else [args.prompt]
    reports: dict[str, dict] = {}

    for version in versions:
        reports[version] = run_evaluation(
            dataset_path=args.dataset,
            prompt_version=version,
            responder=responder,
            output_path=args.output_dir / f"{version}.json",
        )
        print(f"{version}: {json.dumps(reports[version]['averages'])}")

    if len(versions) == 2:
        comparison = compare_reports(reports["v1"], reports["v2"])
        comparison_path = args.output_dir / "comparison.json"
        comparison_path.write_text(json.dumps(comparison, indent=2), encoding="utf-8")
        print(json.dumps(comparison, indent=2))

        if args.quality_gate:
            raise SystemExit(run_gate(comparison_path, min_overall=args.min_overall))


if __name__ == "__main__":
    main()
