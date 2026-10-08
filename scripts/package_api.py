"""Stage the FastAPI app into a clean zip for Azure App Service (Oryx build).

Only application code and the runtime requirements are packaged. Tests,
outputs/, mlruns/, caches and training dependencies are intentionally excluded.

Usage: python scripts/package_api.py [--out build/api-package]
Produces <out>/ (staged tree) and <out>.zip.
"""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INCLUDE_DIRS = ["app", "genai", "src"]
IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache")


def stage(out: Path) -> Path:
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    for name in INCLUDE_DIRS:
        shutil.copytree(ROOT / name, out / name, ignore=IGNORE)
    # Oryx looks for requirements.txt at the package root.
    shutil.copyfile(ROOT / "requirements-runtime.txt", out / "requirements.txt")
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="build/api-package")
    args = parser.parse_args()
    out = Path(args.out)
    if not out.is_absolute():
        out = ROOT / out
    stage(out)
    archive = shutil.make_archive(str(out), "zip", root_dir=out)
    print(f"Staged {out} and wrote {archive}")


if __name__ == "__main__":
    main()
