"""HTTP behavior for health, text analysis, and OCR."""

from __future__ import annotations

import io
import shutil
from typing import Any

import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

from app.config import MISSING_CREDENTIALS_MESSAGE, OCR_UNAVAILABLE_MESSAGE


def _png_bytes(text: str = "Hello OCR") -> bytes:
    """A tiny PNG. OCR tests that mock Tesseract only need it to be a real image."""
    image = Image.new("RGB", (480, 120), "white")
    draw = ImageDraw.Draw(image)
    draw.text((16, 40), text, fill="black")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _azure_post(url: str, headers: dict[str, str], json: dict[str, Any], timeout: int) -> Any:
    """Stand-in for ``requests.post`` that echoes the documents it was given."""

    class _Response:
        status_code = 200

        def json(self) -> dict[str, Any]:
            documents = json["documents"]
            if url.endswith("/sentiment"):
                return {
                    "documents": [
                        {
                            "id": document["id"],
                            "sentiment": "positive",
                            "confidenceScores": {
                                "positive": 0.9,
                                "neutral": 0.08,
                                "negative": 0.02,
                            },
                        }
                        for document in documents
                    ],
                    "errors": [],
                }
            return {
                "documents": [
                    {"id": document["id"], "keyPhrases": ["royal hotel"]}
                    for document in documents
                ],
                "errors": [],
            }

    assert headers["Ocp-Apim-Subscription-Key"] == "test-key"
    assert timeout == 30
    return _Response()


def test_health(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_home_lists_routes(client: TestClient) -> None:
    body = client.get("/").json()
    assert "/api/v1/analyze" in body["analyze"]
    assert body["ocr"] == "POST /api/v1/extract_text"


def test_status_when_azure_is_not_configured(client: TestClient) -> None:
    body = client.get("/api/v1/status").json()
    assert body["azure_language_configured"] is False
    assert any("not configured" in message for message in body["messages"])
    assert "test-key" not in response_text(body)


def response_text(body: dict[str, Any]) -> str:
    return " ".join(body["messages"])


def test_analyze_without_credentials_is_a_clear_503(client: TestClient) -> None:
    response = client.post("/api/v1/analyze", json={"text_to_analyze": ["A lovely stay."]})
    assert response.status_code == 503
    assert response.json()["detail"] == MISSING_CREDENTIALS_MESSAGE


def test_legacy_post_root_uses_the_same_credential_check(client: TestClient) -> None:
    response = client.post("/", json={"text_to_analyze": ["A lovely stay."]})
    assert response.status_code == 503
    assert "AZURE_LANGUAGE_KEY" in response.json()["detail"]


def test_placeholder_credentials_are_treated_as_missing(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(
        "AZURE_LANGUAGE_ENDPOINT",
        "https://your-resource.cognitiveservices.azure.com",
    )
    monkeypatch.setenv("AZURE_LANGUAGE_KEY", "your-key-here")
    response = client.post("/api/v1/analyze", json={"text_to_analyze": ["Hello"]})
    assert response.status_code == 503


def test_analyze_rejects_blank_text(client: TestClient) -> None:
    response = client.post("/api/v1/analyze", json={"text_to_analyze": ["   "]})
    assert response.status_code == 422


def test_analyze_with_credentials_shapes_the_response(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("AZURE_LANGUAGE_ENDPOINT", "https://contoso.cognitiveservices.azure.com")
    monkeypatch.setenv("AZURE_LANGUAGE_KEY", "test-key")
    monkeypatch.setattr("app.text_analytics.requests.post", _azure_post)

    response = client.post(
        "/api/v1/analyze",
        json={"text_to_analyze": ["The Royal Hotel was wonderful."], "language": "en"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["results"][0]["sentiment"] == "positive"
    assert body["results"][0]["key_phrases"] == ["royal hotel"]
    assert body["sentiment"][0]["sentiment"] == "positive"
    assert body["keyphrases"][0]["keyPhrases"] == ["royal hotel"]


def test_analyze_batches_more_than_ten_documents(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[str] = []

    def counting_post(url: str, headers: dict[str, str], json: dict[str, Any], timeout: int) -> Any:
        calls.append(url)
        return _azure_post(url, headers, json, timeout)

    monkeypatch.setenv("COG_SERVICE_ENDPOINT", "https://legacy.cognitiveservices.azure.com/")
    monkeypatch.setenv("COG_SERVICE_KEY", "test-key")
    monkeypatch.setattr("app.text_analytics.requests.post", counting_post)

    texts = [f"Review number {index}" for index in range(11)]
    response = client.post("/api/v1/analyze", json={"text_to_analyze": texts})
    assert response.status_code == 200
    assert len(response.json()["results"]) == 11
    # Two batches, and each batch calls sentiment and key phrases.
    assert len(calls) == 4
    assert calls[0].endswith("/text/analytics/v3.1/sentiment")


def test_analyze_reports_rejected_credentials(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    class _Denied:
        status_code = 401

        def json(self) -> dict[str, str]:
            return {"error": {"message": "Access denied due to invalid subscription key"}}

    monkeypatch.setenv("AZURE_LANGUAGE_ENDPOINT", "https://contoso.cognitiveservices.azure.com")
    monkeypatch.setenv("AZURE_LANGUAGE_KEY", "test-key")
    monkeypatch.setattr("app.text_analytics.requests.post", lambda *args, **kwargs: _Denied())

    response = client.post("/api/v1/analyze", json={"text_to_analyze": ["Hello"]})
    assert response.status_code == 502
    detail = response.json()["detail"]
    assert "rejected" in detail
    assert "test-key" not in detail


def test_ocr_when_tesseract_is_missing(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.ocr.tesseract_available", lambda: False)
    response = client.post(
        "/api/v1/extract_text",
        files=[("images", ("note.png", _png_bytes(), "image/png"))],
    )
    assert response.status_code == 503
    assert response.json()["detail"] == OCR_UNAVAILABLE_MESSAGE


def test_ocr_rejects_a_non_image(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.ocr.tesseract_available", lambda: True)
    response = client.post(
        "/api/v1/extract_text",
        files=[("images", ("notes.txt", b"not an image", "text/plain"))],
    )
    assert response.status_code == 400
    assert "notes.txt" in response.json()["detail"]


def test_ocr_rejects_an_oversized_upload(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.ocr.tesseract_available", lambda: True)
    monkeypatch.setattr("app.ocr.MAX_IMAGE_BYTES", 8)
    response = client.post(
        "/api/v1/extract_text",
        files=[("images", ("big.png", b"0123456789", "image/png"))],
    )
    assert response.status_code == 400
    assert "10 MB" in response.json()["detail"] or "smaller" in response.json()["detail"]


def test_ocr_returns_text_from_tesseract(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.ocr.tesseract_available", lambda: True)
    monkeypatch.setattr("app.ocr.pytesseract.image_to_string", lambda image, lang="eng": "Hello from Tesseract")

    response = client.post(
        "/api/v1/extract_text",
        files=[("images", ("board.png", _png_bytes(), "image/png"))],
    )
    assert response.status_code == 200
    body = response.json()
    assert body["results"][0] == {"filename": "board.png", "text": "Hello from Tesseract"}
    assert body["board.png"] == "Hello from Tesseract"
    assert "Time Taken" in body
    assert body["time_taken_seconds"] == body["Time Taken"]


@pytest.mark.skipif(shutil.which("tesseract") is None, reason="tesseract binary is not installed")
def test_ocr_reads_the_sample_image(client: TestClient) -> None:
    sample = open("samples/ocr-sample.png", "rb")
    try:
        response = client.post(
            "/api/v1/extract_text",
            files=[("images", ("ocr-sample.png", sample.read(), "image/png"))],
        )
    finally:
        sample.close()
    assert response.status_code == 200
    text = response.json()["results"][0]["text"]
    assert "quick brown" in text.lower()
