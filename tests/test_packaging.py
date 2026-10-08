"""The App Service package must contain the app and only runtime dependencies."""
from __future__ import annotations

from pathlib import Path

from scripts.package_api import stage

ROOT = Path(__file__).resolve().parents[1]


def test_api_package_is_self_contained_and_lean(tmp_path):
    out = stage(tmp_path / "pkg")

    assert (out / "app" / "main.py").is_file()
    assert (out / "genai" / "tracing" / "telemetry.py").is_file()
    assert (out / "genai" / "prompts" / "v2.txt").is_file()
    assert (out / "src" / "training" / "features.py").is_file()

    for excluded in ("tests", "outputs", "mlruns", "azure_ml", ".pytest_cache"):
        assert not (out / excluded).exists()

    lines = (out / "requirements.txt").read_text().lower().splitlines()
    requirements = "\n".join(
        line.split("#")[0] for line in lines if not line.lstrip().startswith("#")
    )
    for heavy in ("mlflow", "scikit-learn", "pytest", "azure-ai-ml", "azureml"):
        assert heavy not in requirements
    assert "azure-monitor-opentelemetry" in requirements
    assert "fastapi" in requirements


def test_full_requirements_include_runtime_and_pin_sqlalchemy():
    text = (ROOT / "requirements.txt").read_text()
    assert "-r requirements-runtime.txt" in text
    assert "SQLAlchemy>=2.0,<2.1" in text
