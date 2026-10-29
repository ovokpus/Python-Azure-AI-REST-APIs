"""HTTP client used by the Streamlit UI.

The UI never talks to Azure itself. It calls the FastAPI service so both
surfaces share the same credential checks and error messages.
"""

from __future__ import annotations

import os
from typing import Any

import requests

DEFAULT_API_BASE_URL = "http://localhost:8000"
_TIMEOUT_SECONDS = 120


class ApiConnectionError(Exception):
    """The API process is not reachable at ``API_BASE_URL``."""


class ApiError(Exception):
    """The API responded with an error payload."""

    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


def api_base_url() -> str:
    """Base URL of the FastAPI service, without a trailing slash."""
    return os.getenv("API_BASE_URL", DEFAULT_API_BASE_URL).strip().rstrip("/") or DEFAULT_API_BASE_URL


def format_detail(payload: Any, fallback: str) -> str:
    """Turn FastAPI's ``detail`` field into one readable sentence.

    Validation errors arrive as a list of objects. Configuration and Azure
    errors arrive as a string.
    """
    if isinstance(payload, dict) and "detail" in payload:
        detail = payload["detail"]
    else:
        detail = payload

    if isinstance(detail, str) and detail.strip():
        return detail.strip()
    if isinstance(detail, list):
        parts: list[str] = []
        for item in detail:
            if isinstance(item, dict):
                message = str(item.get("msg") or item.get("message") or "").strip()
                loc = item.get("loc") or []
                field = ".".join(str(part) for part in loc if part not in ("body",))
                if message and field:
                    parts.append(f"{field}: {message}")
                elif message:
                    parts.append(message)
            elif isinstance(item, str) and item.strip():
                parts.append(item.strip())
        if parts:
            return " ".join(parts)
    return fallback


def _request(method: str, path: str, **kwargs: Any) -> Any:
    url = f"{api_base_url()}{path}"
    try:
        response = requests.request(method, url, timeout=_TIMEOUT_SECONDS, **kwargs)
    except requests.RequestException as exc:
        raise ApiConnectionError(
            f"Could not reach the API at {api_base_url()}. "
            "Start it with Docker Compose (`docker compose up --build`) "
            "or run `uvicorn app.main:app --port 8000`."
        ) from exc

    if response.status_code >= 400:
        try:
            payload: Any = response.json()
        except ValueError:
            payload = {}
        raise ApiError(
            response.status_code,
            format_detail(payload, f"The API returned HTTP {response.status_code}."),
        )

    try:
        return response.json()
    except ValueError as exc:
        raise ApiError(response.status_code, "The API returned a response that was not JSON.") from exc


def get_status() -> dict[str, Any]:
    """Return the API's readiness report."""
    payload = _request("GET", "/api/v1/status")
    if not isinstance(payload, dict):
        raise ApiError(200, "The API status response had an unexpected shape.")
    return payload


def analyze_text(texts: list[str], language: str = "en") -> dict[str, Any]:
    """Ask the API to score sentiment and extract key phrases."""
    payload = _request(
        "POST",
        "/api/v1/analyze",
        json={"text_to_analyze": texts, "language": language},
    )
    if not isinstance(payload, dict):
        raise ApiError(200, "The API analysis response had an unexpected shape.")
    return payload


def extract_text(files: list[tuple[str, bytes, str]]) -> dict[str, Any]:
    """Send images to the OCR route.

    Each tuple is ``(filename, content, content_type)``.
    """
    multipart = [
        ("images", (filename, content, content_type))
        for filename, content, content_type in files
    ]
    payload = _request("POST", "/api/v1/extract_text", files=multipart)
    if not isinstance(payload, dict):
        raise ApiError(200, "The API OCR response had an unexpected shape.")
    return payload
