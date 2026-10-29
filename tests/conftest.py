"""Fixtures shared by the API tests.

Azure variables are cleared for every test so a developer's ``.env`` cannot
leak into the suite. Tests that need credentials set them explicitly.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.main import app

_AZURE_ENV_VARS = (
    "AZURE_LANGUAGE_ENDPOINT",
    "AZURE_LANGUAGE_KEY",
    "COG_SERVICE_ENDPOINT",
    "COG_SERVICE_KEY",
)


@pytest.fixture(autouse=True)
def _clear_azure_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in _AZURE_ENV_VARS:
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def client() -> Iterator[TestClient]:
    """In-process API client. Entering the client runs the app lifespan."""
    with TestClient(app) as test_client:
        yield test_client
