"""Credential-gated integration test stubs.

These tests are skipped unless explicitly enabled. They are intentionally not part of
the default test run so CI remains credential-free.
"""
from __future__ import annotations

import os

import pytest


@pytest.mark.skipif(
    os.getenv("RUN_AZURE_INTEGRATION_TESTS") != "1",
    reason="Azure integration tests require explicit opt-in and credentials.",
)
def test_azure_ml_configuration_present() -> None:
    required = ["AZURE_SUBSCRIPTION_ID", "AZURE_RESOURCE_GROUP", "AZURE_ML_WORKSPACE"]
    missing = [name for name in required if not os.getenv(name)]
    assert not missing, f"Missing Azure integration variables: {missing}"
