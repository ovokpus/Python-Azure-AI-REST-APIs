"""FastAPI application: text analytics and OCR.

Run it with ``uvicorn app.main:app`` or, for the historical App Service
command, ``gunicorn -k uvicorn.workers.UvicornWorker main:app``. The root
``main.py`` module re-exports this ``app`` object.
"""

from __future__ import annotations

import logging
import re
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator

from app.config import (
    MISSING_CREDENTIALS_MESSAGE,
    OCR_UNAVAILABLE_MESSAGE,
    load_settings,
)
from app.errors import (
    AzureLanguageError,
    CredentialsNotConfigured,
    InvalidImage,
    OcrUnavailable,
)
from app.ocr import extract_text, tesseract_available
from app.text_analytics import analyze_texts

logger = logging.getLogger(__name__)

_LANGUAGE_CODE = re.compile(r"^[a-zA-Z]{2,3}(-[a-zA-Z0-9]{2,8})?$")
_MAX_DOCUMENTS = 25
_MAX_DOCUMENT_CHARS = 5120


class AnalyzeRequest(BaseModel):
    """Documents to send to Azure AI Language."""

    text_to_analyze: list[str] = Field(..., min_length=1, max_length=_MAX_DOCUMENTS)
    language: str = "en"

    @field_validator("text_to_analyze")
    @classmethod
    def texts_must_be_usable(cls, texts: list[str]) -> list[str]:
        cleaned: list[str] = []
        for text in texts:
            stripped = text.strip()
            if not stripped:
                raise ValueError("Each entry in text_to_analyze must contain text.")
            if len(stripped) > _MAX_DOCUMENT_CHARS:
                raise ValueError(
                    f"Each document must be {_MAX_DOCUMENT_CHARS} characters or fewer."
                )
            cleaned.append(stripped)
        return cleaned

    @field_validator("language")
    @classmethod
    def language_must_be_a_code(cls, language: str) -> str:
        candidate = language.strip()
        if not _LANGUAGE_CODE.fullmatch(candidate):
            raise ValueError("language must be a short code such as en or en-US.")
        return candidate


def _status_payload() -> dict[str, Any]:
    settings = load_settings()
    ocr_ready = tesseract_available()
    messages: list[str] = []
    if settings.azure_language_configured:
        messages.append("Azure Language credentials are configured.")
    else:
        messages.append(MISSING_CREDENTIALS_MESSAGE)
    if ocr_ready:
        messages.append("Tesseract OCR is available.")
    else:
        messages.append(OCR_UNAVAILABLE_MESSAGE)
    return {
        "azure_language_configured": settings.azure_language_configured,
        "ocr_available": ocr_ready,
        "messages": messages,
    }


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Log which backends are ready. Never log secret values."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    for message in _status_payload()["messages"]:
        if message in (MISSING_CREDENTIALS_MESSAGE, OCR_UNAVAILABLE_MESSAGE):
            logger.warning(message)
        else:
            logger.info(message)
    yield


app = FastAPI(
    title="Text & OCR Workbench API",
    description=(
        "Sentiment and key phrases through Azure AI Language, and image OCR "
        "through Tesseract. Azure credentials come from the environment. "
        "When they are missing, text analysis returns HTTP 503 with setup instructions."
    ),
    version="1.1.0",
    lifespan=lifespan,
)


@app.exception_handler(CredentialsNotConfigured)
async def credentials_not_configured(_request: object, _exc: CredentialsNotConfigured) -> JSONResponse:
    return JSONResponse(status_code=503, content={"detail": MISSING_CREDENTIALS_MESSAGE})


@app.exception_handler(OcrUnavailable)
async def ocr_unavailable(_request: object, _exc: OcrUnavailable) -> JSONResponse:
    return JSONResponse(status_code=503, content={"detail": OCR_UNAVAILABLE_MESSAGE})


@app.exception_handler(AzureLanguageError)
async def azure_language_error(_request: object, exc: AzureLanguageError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"detail": str(exc)})


@app.exception_handler(InvalidImage)
async def invalid_image(_request: object, exc: InvalidImage) -> JSONResponse:
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness probe. This stays healthy when Azure is not configured."""
    return {"status": "ok"}


@app.get("/api/v1/status")
def status() -> dict[str, Any]:
    """Report whether text analysis and OCR can run. Does not reveal secrets."""
    return _status_payload()


@app.get("/")
def home() -> dict[str, str]:
    """Point a browser at the interactive docs and the Streamlit UI."""
    return {
        "message": (
            "Text & OCR API. Interactive docs are at /docs. "
            "The Streamlit UI listens on port 8501 when you use Docker Compose."
        ),
        "analyze": "POST /api/v1/analyze",
        "ocr": "POST /api/v1/extract_text",
        "health": "GET /health",
        "status": "GET /api/v1/status",
    }


def _analyze(body: AnalyzeRequest) -> dict[str, Any]:
    return analyze_texts(body.text_to_analyze, language=body.language)


@app.post("/api/v1/analyze")
def analyze(body: AnalyzeRequest) -> dict[str, Any]:
    """Sentiment and key phrases for one or more documents."""
    return _analyze(body)


@app.post("/")
def analyze_legacy(body: AnalyzeRequest) -> dict[str, Any]:
    """Same handler as ``/api/v1/analyze``.

    The original App Service exposed text analysis on ``POST /``.
    """
    return _analyze(body)


@app.post("/api/v1/extract_text")
async def extract_text_route(images: list[UploadFile] = File(...)) -> dict[str, Any]:
    """OCR each uploaded image. The response keeps the original filename map."""
    if not images:
        raise HTTPException(status_code=400, detail="Upload at least one image.")

    started = time.perf_counter()
    results: list[dict[str, str]] = []
    by_filename: dict[str, str] = {}
    for upload in images:
        filename = upload.filename or "upload"
        contents = await upload.read()
        try:
            text = extract_text(contents)
        except InvalidImage as exc:
            # Include the filename so a multi-file request says which one failed.
            raise InvalidImage(f"{filename}: {exc}") from exc
        results.append({"filename": filename, "text": text})
        by_filename[filename] = text

    elapsed = round(time.perf_counter() - started, 2)
    response: dict[str, Any] = {
        "results": results,
        "time_taken_seconds": elapsed,
        # Original OCR route used this key. Kept so older clients still parse.
        "Time Taken": elapsed,
    }
    response.update(by_filename)
    return response
