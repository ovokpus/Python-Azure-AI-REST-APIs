"""Streamlit page behavior, driven with Streamlit's AppTest harness.

These tests do not open a browser. They run the script, set widgets, and
read the elements the page would show.
"""

from __future__ import annotations

from typing import Any

import pytest
from streamlit.testing.v1 import AppTest


def _response(status_code: int, payload: dict[str, Any]) -> Any:
    class _Response:
        def __init__(self) -> None:
            self.status_code = status_code

        def json(self) -> dict[str, Any]:
            return payload

    return _Response()


def test_ui_explains_when_the_api_is_down(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("API_BASE_URL", "http://127.0.0.1:9")
    app = AppTest.from_file("frontend/streamlit_app.py")
    app.run(timeout=30)
    assert not app.exception
    assert any("Could not reach the API" in item.value for item in app.error)
    assert any(item.value == "Text & OCR Workbench" for item in app.title)


def test_ui_shows_the_azure_setup_message(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_request(method: str, url: str, timeout: int, **kwargs: Any) -> Any:
        if url.endswith("/api/v1/status"):
            return _response(
                200,
                {
                    "azure_language_configured": False,
                    "ocr_available": True,
                    "messages": [
                        "Azure Language credentials are not configured. Set AZURE_LANGUAGE_KEY.",
                        "Tesseract OCR is available.",
                    ],
                },
            )
        return _response(
            503,
            {"detail": "Azure Language credentials are not configured. Set AZURE_LANGUAGE_KEY."},
        )

    monkeypatch.setattr("frontend.api_client.requests.request", fake_request)
    app = AppTest.from_file("frontend/streamlit_app.py")
    app.run(timeout=30)
    assert not app.exception
    assert any("not configured" in item.value for item in app.warning)

    text_area = next(item for item in app.text_area if item.label == "Text to analyze")
    text_area.set_value("A lovely stay.").run()
    analyze = next(item for item in app.button if item.label == "Analyze text")
    analyze.click().run()
    assert not app.exception
    assert any("AZURE_LANGUAGE_KEY" in item.value for item in app.warning)
