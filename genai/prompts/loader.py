"""Versioned prompt loader."""
from pathlib import Path

PROMPT_ROOT = Path(__file__).resolve().parent


def load_prompt(version: str) -> str:
    if version not in {"v1", "v2"}:
        raise ValueError(f"Unsupported prompt version: {version}")
    return (PROMPT_ROOT / f"{version}.txt").read_text(encoding="utf-8")
