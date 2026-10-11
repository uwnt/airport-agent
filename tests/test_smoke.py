"""Smoke test: the package imports. Real tests arrive with the scoring engine in Step 4."""

import airport_agent


def test_package_imports():
    assert callable(airport_agent.main)
