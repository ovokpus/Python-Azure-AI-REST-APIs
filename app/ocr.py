"""Local OCR through Tesseract.

The binary is provided by the API Docker image (``tesseract-ocr``). A host
install works the same way. When the binary is missing, callers get
:class:`app.errors.OcrUnavailable` and a message that says how to fix it.
"""

from __future__ import annotations

import io
import logging
import shutil

import pytesseract
from PIL import Image, UnidentifiedImageError

from app.errors import InvalidImage, OcrUnavailable

logger = logging.getLogger(__name__)

MAX_IMAGE_BYTES = 10 * 1024 * 1024


def tesseract_available() -> bool:
    """True when the ``tesseract`` executable is on ``PATH``."""
    return shutil.which("tesseract") is not None


def extract_text(image_bytes: bytes, lang: str = "eng") -> str:
    """Read text from image bytes.

    Raises:
        OcrUnavailable: Tesseract is not installed.
        InvalidImage: the bytes are empty, too large, or not an image.
    """
    if not tesseract_available():
        raise OcrUnavailable()
    if not image_bytes:
        raise InvalidImage("The uploaded file is empty.")
    if len(image_bytes) > MAX_IMAGE_BYTES:
        raise InvalidImage("Each image must be 10 MB or smaller.")

    try:
        with Image.open(io.BytesIO(image_bytes)) as image:
            # Load now so a truncated file fails here, before Tesseract.
            image.load()
            text = pytesseract.image_to_string(image, lang=lang)
    except UnidentifiedImageError as exc:
        raise InvalidImage("The uploaded file is not a readable image.") from exc
    except OSError as exc:
        raise InvalidImage("The uploaded file could not be opened as an image.") from exc
    except pytesseract.TesseractNotFoundError as exc:
        raise OcrUnavailable() from exc
    except pytesseract.TesseractError as exc:
        logger.warning("Tesseract failed: %s", exc)
        raise InvalidImage("Tesseract could not read that image.") from exc

    return text.strip()
