"""Runtime configuration loaded from the environment.

The API starts even when Azure credentials are absent. Text analysis then
returns :data:`MISSING_CREDENTIALS_MESSAGE` instead of crashing or calling
Azure with an empty key. Image OCR does not read these settings.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

# Obvious stand-ins from .env.example. Treating them as "unset" means a copied
# example file still gets the configuration message rather than a 401 from Azure.
_PLACEHOLDER_KEYS = {
    "your-key-here",
    "changeme",
    "<your-key>",
    "paste-your-key-here",
}
_PLACEHOLDER_ENDPOINT_MARKERS = (
    "your-resource",
    "your-language-resource",
    "example.cognitiveservices.azure.com",
)

MISSING_CREDENTIALS_MESSAGE = (
    "Azure Language credentials are not configured. "
    "Copy .env.example to .env, set AZURE_LANGUAGE_ENDPOINT and "
    "AZURE_LANGUAGE_KEY to the endpoint and key of an Azure AI Language "
    "resource, then restart the API. "
    "Sentiment and key-phrase analysis stay unavailable until those values "
    "are real. Image OCR does not use them."
)

OCR_UNAVAILABLE_MESSAGE = (
    "Tesseract OCR is not installed. "
    "Run the API with Docker Compose (the API image installs tesseract-ocr), "
    "or install the tesseract binary on the host and restart the API."
)


@dataclass(frozen=True)
class Settings:
    """Azure Language connection details, when both values are present."""

    azure_language_endpoint: str | None
    azure_language_key: str | None

    @property
    def azure_language_configured(self) -> bool:
        """True when both the endpoint and the key look usable."""
        return bool(self.azure_language_endpoint and self.azure_language_key)


def _clean(value: str | None) -> str:
    return (value or "").strip()


def _usable_endpoint(endpoint: str) -> str:
    """Drop a trailing slash and reject example hostnames."""
    cleaned = endpoint.rstrip("/")
    lowered = cleaned.lower()
    if not cleaned:
        return ""
    if any(marker in lowered for marker in _PLACEHOLDER_ENDPOINT_MARKERS):
        return ""
    return cleaned


def _usable_key(key: str) -> str:
    if key.lower() in _PLACEHOLDER_KEYS:
        return ""
    return key


def load_settings() -> Settings:
    """Read Azure Language settings from the process environment.

    ``AZURE_LANGUAGE_ENDPOINT`` and ``AZURE_LANGUAGE_KEY`` are the names this
    project documents. The original batch script's ``COG_SERVICE_ENDPOINT``
    and ``COG_SERVICE_KEY`` are still accepted so an existing local ``.env``
    keeps working.
    """
    endpoint = _usable_endpoint(
        _clean(os.getenv("AZURE_LANGUAGE_ENDPOINT") or os.getenv("COG_SERVICE_ENDPOINT"))
    )
    key = _usable_key(
        _clean(os.getenv("AZURE_LANGUAGE_KEY") or os.getenv("COG_SERVICE_KEY"))
    )
    return Settings(
        azure_language_endpoint=endpoint or None,
        azure_language_key=key or None,
    )
