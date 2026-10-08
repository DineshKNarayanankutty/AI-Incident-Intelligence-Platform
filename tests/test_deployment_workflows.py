from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read_workflow(name: str) -> str:
    return (ROOT / ".github/workflows" / name).read_text(encoding="utf-8")


def test_blue_green_deployment_does_not_force_all_traffic() -> None:
    text = read_workflow("deployment.yml")
    assert "Azure ML Blue-Green Deployment" in text
    assert "--deployment-name \"$CANDIDATE\"" in text
    assert "--all-traffic" not in text
    assert '--traffic "${CANDIDATE}=100 ${ACTIVE}=0"' in text
    assert '--traffic "${ACTIVE}=100 ${CANDIDATE}=0"' in text


def test_blue_green_workflow_validates_candidate_before_promotion() -> None:
    text = read_workflow("deployment.yml")
    assert "Smoke test candidate directly" in text
    assert 'if: ${{ inputs.promote }}' in text
    assert "Live smoke test failed. Restoring previous production deployment" in text


def test_rollback_workflow_exists_and_smoke_tests_target() -> None:
    text = read_workflow("rollback.yml")
    assert "Azure ML Rollback" in text
    assert "Smoke test rollback target directly" in text
    assert '--traffic "${ROLLBACK_TO}=100 ${CURRENT}=0"' in text
