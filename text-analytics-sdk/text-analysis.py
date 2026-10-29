"""Batch text analytics for the sample hotel reviews.

Run from anywhere:

    python text-analytics-sdk/text-analysis.py

Credentials come from the environment (or a ``.env`` file in the current
working directory). When they are missing, the script prints how to set them
and exits with status 1. It does not call Azure in that case.
"""

from __future__ import annotations

import sys
from pathlib import Path

from dotenv import load_dotenv

# The script lives in a subfolder; the shared config module lives at the repo root.
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from azure.ai.textanalytics import TextAnalyticsClient
from azure.core.credentials import AzureKeyCredential

from app.config import MISSING_CREDENTIALS_MESSAGE, load_settings

_REVIEWS_DIR = Path(__file__).resolve().parent / "reviews"


def _load_documents() -> list[dict[str, str]]:
    documents: list[dict[str, str]] = []
    if not _REVIEWS_DIR.is_dir():
        return documents
    for file_path in sorted(_REVIEWS_DIR.glob("*.txt")):
        text = file_path.read_text(encoding="utf8")
        documents.append({"id": file_path.name, "text": text})
    return documents


def main() -> int:
    """Analyze every review file. Returns a process exit code."""
    load_dotenv()
    settings = load_settings()
    if not settings.azure_language_configured:
        print(MISSING_CREDENTIALS_MESSAGE)
        return 1

    documents = _load_documents()
    if not documents:
        print(f"No review files found in {_REVIEWS_DIR}.")
        return 1

    # load_settings() only returns configured when both values are present.
    assert settings.azure_language_endpoint is not None
    assert settings.azure_language_key is not None
    client = TextAnalyticsClient(
        endpoint=settings.azure_language_endpoint,
        credential=AzureKeyCredential(settings.azure_language_key),
    )

    try:
        print("\nProcessing batch request...\n")

        language_results = client.detect_language(documents=documents)
        for doc, result in zip(documents, language_results):
            if result.is_error:
                print(f"\nFile: {doc['id']}\nLanguage error: {result.error}")
                continue
            print(f"\nFile: {doc['id']}\nLanguage: {result.primary_language.name}")

        sentiment_results = client.analyze_sentiment(documents=documents)
        for doc, result in zip(documents, sentiment_results):
            if result.is_error:
                print(f"\nFile: {doc['id']}\nSentiment error: {result.error}")
                continue
            print(f"\nFile: {doc['id']}\nSentiment: {result.sentiment}")

        key_phrase_results = client.extract_key_phrases(documents=documents)
        for doc, result in zip(documents, key_phrase_results):
            if result.is_error:
                print(f"\nFile: {doc['id']}\nKey phrase error: {result.error}")
                continue
            if result.key_phrases:
                print(f"\nFile: {doc['id']}\nKey Phrases: {', '.join(result.key_phrases)}")

        entity_results = client.recognize_entities(documents=documents)
        for doc, result in zip(documents, entity_results):
            if result.is_error:
                print(f"\nFile: {doc['id']}\nEntity error: {result.error}")
                continue
            if result.entities:
                print(f"\nFile: {doc['id']}\nEntities:")
                for entity in result.entities:
                    print(f"\t{entity.text} ({entity.category})")

        linked_entity_results = client.recognize_linked_entities(documents=documents)
        for doc, result in zip(documents, linked_entity_results):
            if result.is_error:
                print(f"\nFile: {doc['id']}\nLinked entity error: {result.error}")
                continue
            if result.entities:
                print(f"\nFile: {doc['id']}\nLinked Entities:")
                for entity in result.entities:
                    print(f"\t{entity.name} ({entity.url})")
    except Exception as exc:
        print(f"Error talking to Azure AI Language: {exc}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
