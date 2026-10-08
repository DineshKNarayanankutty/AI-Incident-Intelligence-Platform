"""Return the next numeric Azure ML model version from a JSON model list."""
from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python scripts/next_model_version.py <models.json>", file=sys.stderr)
        return 2

    payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("Expected Azure ML model list JSON array.")

    versions: list[int] = []
    for item in payload:
        try:
            versions.append(int(item["version"]))
        except (KeyError, TypeError, ValueError):
            continue

    print(max(versions, default=0) + 1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
