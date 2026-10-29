"""Browser UI for the text-analytics and OCR API.

Run from the repository root:

    streamlit run frontend/streamlit_app.py

Docker Compose sets ``API_BASE_URL`` to the API service. On a laptop the
client defaults to ``http://localhost:8000``.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

# Streamlit puts the script directory on sys.path, not the repository root.
# Adding the root lets `frontend` import the same way the tests do.
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import streamlit as st

from frontend.api_client import ApiConnectionError, ApiError, analyze_text, extract_text, get_status

# Dark text on tinted backgrounds. Streamlit's light theme supplies the page
# colors; these chips stay readable if a custom theme shifts the card color.
_SENTIMENT_COLORS = {
    "positive": ("#14532d", "#dcfce7"),
    "negative": ("#7f1d1d", "#fee2e2"),
    "neutral": ("#1f2937", "#e5e7eb"),
    "mixed": ("#78350f", "#fef3c7"),
}

_EXAMPLE_TEXT = (
    "The Royal Hotel in London was a pleasure. Clean rooms, a peaceful courtyard, "
    "and a short walk to Westminster Abbey. The restaurant next door served a "
    "fabulous taster menu. Thoroughly recommended."
)


def _sentiment_chip(label: str | None) -> str:
    key = (label or "unknown").lower()
    foreground, background = _SENTIMENT_COLORS.get(key, ("#1c1917", "#f5f5f4"))
    shown = label or "unknown"
    return (
        f"<span style=\"display:inline-block;padding:0.35rem 0.75rem;"
        f"border-radius:999px;background:{background};color:{foreground};"
        f"font-weight:700;letter-spacing:0.02em;\">{shown}</span>"
    )


def _render_status() -> None:
    """Show whether Azure and Tesseract are ready. Stop if the API is down."""
    try:
        status = get_status()
    except ApiConnectionError as exc:
        st.error(str(exc))
        st.stop()
    except ApiError as exc:
        st.error(exc.detail)
        st.stop()

    messages = status.get("messages") or []
    azure_ready = bool(status.get("azure_language_configured"))
    ocr_ready = bool(status.get("ocr_available"))

    left, right = st.columns(2)
    with left:
        if azure_ready:
            st.success("Azure Language is configured.")
        else:
            st.warning(next((msg for msg in messages if "not configured" in msg), messages[0] if messages else ""))
    with right:
        if ocr_ready:
            st.success("Tesseract OCR is available.")
        else:
            st.warning(next((msg for msg in messages if "Tesseract" in msg), "Tesseract OCR is not available."))


def _render_analysis(payload: dict[str, Any]) -> None:
    results = payload.get("results") or []
    if not results:
        st.info("Azure returned no per-document results.")
        return

    for item in results:
        title = item.get("sentiment") or "result"
        with st.container(border=True):
            st.markdown(_sentiment_chip(item.get("sentiment")), unsafe_allow_html=True)
            st.caption(f"Document {item.get('id', '')}")
            st.write(item.get("text") or "")
            if item.get("error"):
                st.error(item["error"])
                continue
            if item.get("warning"):
                st.warning(item["warning"])

            scores = item.get("confidence_scores") or {}
            if isinstance(scores, dict) and scores:
                score_cols = st.columns(3)
                for column, label in zip(score_cols, ("positive", "neutral", "negative")):
                    value = float(scores.get(label) or 0)
                    column.metric(label.capitalize(), f"{value:.0%}")
                    column.progress(min(max(value, 0.0), 1.0))

            phrases = item.get("key_phrases") or []
            if phrases:
                st.markdown("**Key phrases**")
                st.write(", ".join(f"`{phrase}`" for phrase in phrases))
            elif title:
                st.caption("No key phrases returned for this document.")

    with st.expander("Raw API response"):
        st.json(payload)


def _show_message(message: tuple[str, str] | None) -> None:
    """Render a stored error or warning. ``message`` is ``(level, text)``."""
    if not message:
        return
    level, detail = message
    if level == "error":
        st.error(detail)
        return
    st.warning(detail)


def _text_tab() -> None:
    st.subheader("Sentiment and key phrases")
    st.caption("Text is sent to your API, which calls Azure AI Language. Nothing is stored.")

    if "draft_text" not in st.session_state:
        st.session_state.draft_text = ""

    def _load_example() -> None:
        st.session_state.draft_text = _EXAMPLE_TEXT

    st.button("Load example review", on_click=_load_example)

    text = st.text_area(
        "Text to analyze",
        key="draft_text",
        height=180,
        placeholder="Paste a review, an email, or any short passage.",
    )
    language = st.selectbox(
        "Language",
        options=["en", "es", "fr", "de", "it", "pt", "nl", "ja", "zh-Hans"],
        index=0,
        help="BCP-47 style code passed through to Azure AI Language.",
    )

    # Keep the last result in session state. Streamlit reruns the script on
    # every widget change, and a message drawn only inside the button block
    # disappears on the next run.
    if st.button("Analyze text", type="primary"):
        st.session_state.analysis_message = None
        st.session_state.analysis_payload = None
        if not text.strip():
            st.session_state.analysis_message = ("warning", "Enter some text first.")
        else:
            try:
                st.session_state.analysis_payload = analyze_text([text], language=language)
            except ApiConnectionError as exc:
                st.session_state.analysis_message = ("error", str(exc))
            except ApiError as exc:
                level = "warning" if exc.status_code == 503 else "error"
                st.session_state.analysis_message = (level, exc.detail)

    _show_message(st.session_state.get("analysis_message"))
    if st.session_state.get("analysis_payload"):
        _render_analysis(st.session_state.analysis_payload)


def _ocr_tab() -> None:
    st.subheader("Read text from an image")
    st.caption("Images are sent to the API and read with Tesseract. Azure is not involved. 10 MB per file.")

    uploads = st.file_uploader(
        "Images",
        type=["png", "jpg", "jpeg", "tif", "tiff", "bmp", "webp", "gif"],
        accept_multiple_files=True,
    )
    if st.button("Extract text", type="primary"):
        st.session_state.ocr_message = None
        st.session_state.ocr_payload = None
        if not uploads:
            st.session_state.ocr_message = ("warning", "Choose at least one image.")
        else:
            files = [
                (upload.name, upload.getvalue(), upload.type or "application/octet-stream")
                for upload in uploads
            ]
            try:
                st.session_state.ocr_payload = extract_text(files)
            except ApiConnectionError as exc:
                st.session_state.ocr_message = ("error", str(exc))
            except ApiError as exc:
                level = "warning" if exc.status_code == 503 else "error"
                st.session_state.ocr_message = (level, exc.detail)

    _show_message(st.session_state.get("ocr_message"))
    payload = st.session_state.get("ocr_payload")
    if payload:
        results = payload.get("results") or []
        elapsed = payload.get("time_taken_seconds")
        if elapsed is not None:
            st.caption(f"Finished in {elapsed}s.")
        for index, item in enumerate(results):
            upload = uploads[index] if uploads and index < len(uploads) else None
            with st.container(border=True):
                filename = item.get("filename") or (upload.name if upload is not None else "image")
                st.markdown(f"**{filename}**")
                preview, transcript = st.columns([1, 2])
                with preview:
                    if upload is not None:
                        st.image(upload, use_container_width=True)
                with transcript:
                    text = item.get("text") or ""
                    if text.strip():
                        state_key = f"ocr-{index}-{filename}"
                        # Seed once. Passing value= and a key on later reruns
                        # makes Streamlit reject the widget.
                        if state_key not in st.session_state:
                            st.session_state[state_key] = text
                        st.text_area("Extracted text", key=state_key, height=180)
                    else:
                        st.info("No text was found in this image.")
        with st.expander("Raw API response"):
            st.json(payload)


def main() -> None:
    """Draw the workbench. Streamlit reruns this function on each interaction."""
    st.set_page_config(
        page_title="Text & OCR Workbench",
        page_icon="🔎",
        layout="wide",
    )
    # Streamlit's default warning yellow is about 4.2:1 on this page.
    # Force alert copy to the same near-black as the rest of the UI.
    st.markdown(
        """
        <style>
        div[data-testid="stAlert"],
        div[data-testid="stAlert"] * {
            color: #1c1917 !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.title("Text & OCR Workbench")
    st.write(
        "Score sentiment, pull out key phrases, and read text out of images. "
        "This page talks only to the local FastAPI service."
    )
    _render_status()
    text_tab, ocr_tab = st.tabs(["Analyze text", "Read an image"])
    with text_tab:
        _text_tab()
    with ocr_tab:
        _ocr_tab()


main()
