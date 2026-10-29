"""Sentiment and key-phrase calls against Azure AI Language.

The REST shape matches the original root API: one request per operation to
``/text/analytics/v3.1/{sentiment|keyPhrases}``. Documents are sent in batches
of ten, which is the service limit for these routes.
"""

from __future__ import annotations

import logging
from typing import Any

import requests

from app.config import load_settings
from app.errors import AzureLanguageError, CredentialsNotConfigured

logger = logging.getLogger(__name__)

_BATCH_SIZE = 10
_TIMEOUT_SECONDS = 30


def _analytics_url(endpoint: str, route: str) -> str:
    """Build a v3.1 URL, even if the env value already includes the prefix."""
    base = endpoint.rstrip("/")
    marker = "/text/analytics/v3.1"
    if base.lower().endswith(marker):
        return f"{base}/{route}"
    return f"{base}{marker}/{route}"


def _headers(key: str) -> dict[str, str]:
    return {
        "Ocp-Apim-Subscription-Key": key,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def _error_message(payload: Any) -> str:
    """Pull a human-readable message out of an Azure error body."""
    if not isinstance(payload, dict):
        return ""
    error = payload.get("error")
    if isinstance(error, dict):
        message = error.get("message") or error.get("innererror", {})
        if isinstance(message, str) and message.strip():
            return message.strip()
        if isinstance(message, dict):
            inner = message.get("message")
            if isinstance(inner, str) and inner.strip():
                return inner.strip()
    message = payload.get("message")
    if isinstance(message, str):
        return message.strip()
    return ""


def _post(endpoint: str, key: str, route: str, documents: list[dict[str, Any]]) -> dict[str, Any]:
    """POST one batch. The subscription key is sent as a header and never logged."""
    url = _analytics_url(endpoint, route)
    try:
        response = requests.post(
            url,
            headers=_headers(key),
            json={"documents": documents},
            timeout=_TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        logger.warning("Azure Language request to %s failed: %s", route, exc.__class__.__name__)
        raise AzureLanguageError(
            "Could not reach Azure AI Language. "
            "Check AZURE_LANGUAGE_ENDPOINT and that this machine can reach Azure."
        ) from exc

    try:
        payload: Any = response.json()
    except ValueError:
        payload = {}

    if response.status_code in (401, 403):
        logger.info("Azure Language rejected credentials for %s (HTTP %s)", route, response.status_code)
        raise AzureLanguageError(
            "Azure rejected the Language credentials "
            f"(HTTP {response.status_code}). "
            "Check AZURE_LANGUAGE_KEY and that AZURE_LANGUAGE_ENDPOINT belongs to "
            "that same Language resource."
        )

    if response.status_code >= 400:
        message = _error_message(payload) or (
            f"Azure AI Language returned HTTP {response.status_code} for {route}."
        )
        logger.info("Azure Language %s failed: HTTP %s", route, response.status_code)
        raise AzureLanguageError(message)

    if not isinstance(payload, dict):
        raise AzureLanguageError(f"Azure AI Language returned an unexpected payload for {route}.")
    return payload


def _index_documents(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    documents = payload.get("documents") or []
    indexed: dict[str, dict[str, Any]] = {}
    if isinstance(documents, list):
        for document in documents:
            if isinstance(document, dict) and "id" in document:
                indexed[str(document["id"])] = document
    return indexed


def _index_errors(payload: dict[str, Any]) -> dict[str, str]:
    errors = payload.get("errors") or []
    indexed: dict[str, str] = {}
    if not isinstance(errors, list):
        return indexed
    for item in errors:
        if not isinstance(item, dict) or "id" not in item:
            continue
        error = item.get("error")
        message = ""
        if isinstance(error, dict):
            message = str(error.get("message") or "").strip()
        indexed[str(item["id"])] = message or "Azure could not analyze this document."
    return indexed


def analyze_texts(texts: list[str], language: str = "en") -> dict[str, Any]:
    """Run sentiment and key-phrase extraction for each text.

    Raises:
        CredentialsNotConfigured: endpoint or key is missing.
        AzureLanguageError: Azure returned an error or could not be reached.
    """
    settings = load_settings()
    if not settings.azure_language_configured:
        raise CredentialsNotConfigured()

    endpoint = settings.azure_language_endpoint
    key = settings.azure_language_key
    # The check above guarantees both are set. The locals keep the type narrow.
    assert endpoint is not None and key is not None

    sentiment_documents: list[dict[str, Any]] = []
    keyphrase_documents: list[dict[str, Any]] = []
    results: list[dict[str, Any]] = []

    for start in range(0, len(texts), _BATCH_SIZE):
        chunk = texts[start : start + _BATCH_SIZE]
        documents = [
            {"id": str(start + index + 1), "language": language, "text": text}
            for index, text in enumerate(chunk)
        ]
        sentiment_payload = _post(endpoint, key, "sentiment", documents)
        keyphrase_payload = _post(endpoint, key, "keyPhrases", documents)
        sentiment_by_id = _index_documents(sentiment_payload)
        phrases_by_id = _index_documents(keyphrase_payload)
        errors = _index_errors(sentiment_payload)
        errors.update(_index_errors(keyphrase_payload))

        for document in documents:
            doc_id = str(document["id"])
            sentiment_doc = sentiment_by_id.get(doc_id)
            phrase_doc = phrases_by_id.get(doc_id)
            if sentiment_doc is not None:
                sentiment_documents.append(sentiment_doc)
            if phrase_doc is not None:
                keyphrase_documents.append(phrase_doc)

            item: dict[str, Any] = {
                "id": doc_id,
                "text": document["text"],
                "sentiment": None if sentiment_doc is None else sentiment_doc.get("sentiment"),
                "confidence_scores": None
                if sentiment_doc is None
                else sentiment_doc.get("confidenceScores"),
                "key_phrases": [] if phrase_doc is None else list(phrase_doc.get("keyPhrases") or []),
            }
            if doc_id in errors and sentiment_doc is None:
                item["error"] = errors[doc_id]
            elif doc_id in errors:
                item["warning"] = errors[doc_id]
            results.append(item)

    logger.info("Analyzed %s document(s) with Azure Language", len(texts))
    return {
        "sentiment": sentiment_documents,
        "keyphrases": keyphrase_documents,
        "results": results,
    }
