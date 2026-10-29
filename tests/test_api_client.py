"""The UI's HTTP client, without starting Streamlit."""

from __future__ import annotations

import py_compile
from typing import Any

import pytest

from frontend.api_client import ApiConnectionError, ApiError, analyze_text, format_detail, get_status


def test_format_detail_reads_a_string() -> None:
    assert format_detail({"detail": "Azure Language credentials are not configured."}, "fallback") == (
        "Azure Language credentials are not configured."
    )


def test_format_detail_flattens_validation_errors() -> None:
    payload = {
        "detail": [
            {"loc": ["body", "text_to_analyze"], "msg": "Field required", "type": "missing"},
        ]
    }
    assert format_detail(payload, "fallback") == "text_to_analyze: Field required"


def test_format_detail_uses_the_fallback() -> None:
    assert format_detail({"unexpected": True}, "fallback") == "fallback"


def test_get_status_returns_the_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Response:
        status_code = 200

        def json(self) -> dict[str, Any]:
            return {"azure_language_configured": False, "ocr_available": True, "messages": ["ok"]}

    monkeypatch.setattr("frontend.api_client.requests.request", lambda *args, **kwargs: _Response())
    assert get_status()["ocr_available"] is True


def test_analyze_text_surfaces_503(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Response:
        status_code = 503

        def json(self) -> dict[str, str]:
            return {"detail": "Azure Language credentials are not configured."}

    monkeypatch.setattr("frontend.api_client.requests.request", lambda *args, **kwargs: _Response())
    with pytest.raises(ApiError) as caught:
        analyze_text(["Hello"])
    assert caught.value.status_code == 503
    assert "not configured" in caught.value.detail


def test_connection_error_names_the_base_url(monkeypatch: pytest.MonkeyPatch) -> None:
    import requests

    def _boom(*args: object, **kwargs: object) -> None:
        raise requests.ConnectionError("refused")

    monkeypatch.setattr("frontend.api_client.requests.request", _boom)
    with pytest.raises(ApiConnectionError) as caught:
        get_status()
    assert "localhost:8000" in str(caught.value)


def test_streamlit_app_compiles() -> None:
    py_compile.compile("frontend/streamlit_app.py", doraise=True)
