"""Errors the API turns into clear HTTP responses.

These are raised by the text-analytics and OCR services and handled in
``app.main`` so callers see a message they can act on.
"""


class CredentialsNotConfigured(Exception):
    """Azure Language settings are missing or still placeholders."""


class AzureLanguageError(Exception):
    """Azure AI Language rejected the call or could not be reached."""

    def __init__(self, message: str, status_code: int = 502) -> None:
        super().__init__(message)
        self.status_code = status_code


class OcrUnavailable(Exception):
    """The Tesseract binary is not installed on this machine."""


class InvalidImage(Exception):
    """An upload is empty, too large, or not a readable image."""
