"""Local-first GenAIOps evaluation runner; Azure Foundry execution can be plugged in."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Callable

from genai.prompts.loader import load_prompt


def load_dataset(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def heuristic_score(output: str, expected_severity: str, criteria: list[str]) -> dict[str, float]:
    text = output.lower()
    severity_hit = float(expected_severity.lower() in text)
    forbidden_invention = any(term in text for term in ("confirmed root cause", "definitely caused by", "resolved successfully"))
    criterion_hits = sum(
        [
            float("impact" in text or "customer" in text),
            float("signal" in text or "error" in text or "latency" in text),
            float(not forbidden_invention),
        ]
    )
    return {
        "severity_alignment": severity_hit,
        "grounding": criterion_hits / 3.0,
        "overall": (severity_hit + criterion_hits / 3.0) / 2.0,
    }


def run_evaluation(
    dataset_path: Path,
    prompt_version: str,
    responder: Callable[[str], str],
    output_path: Path,
) -> dict:
    cases = load_dataset(dataset_path)
    results = []
    for case in cases:
        incident = case["incident"]
        prompt = load_prompt(prompt_version).format(
            severity=case["expected_severity"],
            incident=json.dumps(incident, indent=2),
        )
        output = responder(prompt)
        scores = heuristic_score(output, case["expected_severity"], case["criteria"])
        results.append({"id": case["id"], "output": output, "scores": scores})
    averages = {
        key: sum(item["scores"][key] for item in results) / len(results)
        for key in ("severity_alignment", "grounding", "overall")
    }
    report = {"prompt_version": prompt_version, "cases": results, "averages": averages}
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def compare_reports(v1: dict, v2: dict) -> dict:
    return {
        "v1": v1["averages"],
        "v2": v2["averages"],
        "delta": {key: v2["averages"][key] - v1["averages"][key] for key in v1["averages"]},
        "winner": "v2" if v2["averages"]["overall"] >= v1["averages"]["overall"] else "v1",
    }


def _local_responder(prompt: str) -> str:
    """Credential-free responder used only for local evaluation plumbing."""
    import re
    match = re.search(r"Predicted severity:\s*([A-Za-z]+)", prompt)
    severity = match.group(1) if match else "unknown"
    return (
        f"The predicted severity is {severity}. "
        "Impact is based on the observed customer impact and operational signals. "
        "The available signals should be validated before declaring root cause. "
        "Next actions are to inspect the affected service, dependency health, "
        "error rate, latency, and recent changes."
    )


def _foundry_responder():
    from app.clients.foundry import FoundryAgentClient
    from app.core.config import Settings
    client = FoundryAgentClient(Settings.from_env())
    return client.analyze


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, default=Path("genai/evaluation/dataset.jsonl"))
    parser.add_argument("--prompt", choices=["v1", "v2"], default="v2")
    parser.add_argument("--output", type=Path, default=Path("outputs/evaluation/report.json"))
    parser.add_argument("--backend", choices=["local", "foundry"], default="local")
    args = parser.parse_args()

    responder = _local_responder if args.backend == "local" else _foundry_responder()
    report = run_evaluation(args.dataset, args.prompt, responder, args.output)
    print(json.dumps(report["averages"], indent=2))


if __name__ == "__main__":
    main()
