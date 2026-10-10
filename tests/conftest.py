"""Shared fixtures for Commons Radio tests."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _enable_custom_integrations(enable_custom_integrations) -> None:
    """Let Home Assistant load this repository's custom integration."""
