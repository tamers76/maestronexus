"""Syllabus text extraction for the Course Intake stage.

Keeps dependencies light and degrades gracefully (matching the LLM-stub
philosophy): DOCX is parsed with the stdlib (zip + XML), PDF uses ``pypdf`` if
installed, and plain text passes through. Bytes can be supplied directly or
fetched from object storage by ``storage_key``.
"""

from __future__ import annotations

import io
import logging
import re
import xml.etree.ElementTree as ET
import zipfile

logger = logging.getLogger(__name__)

_WORD_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def extract_docx_text(data: bytes) -> str:
    """Extract paragraph text from a .docx file using only the stdlib."""

    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        xml_bytes = zf.read("word/document.xml")
    root = ET.fromstring(xml_bytes)
    paragraphs: list[str] = []
    for para in root.iter(f"{_WORD_NS}p"):
        texts = [node.text for node in para.iter(f"{_WORD_NS}t") if node.text]
        line = "".join(texts).strip()
        if line:
            paragraphs.append(line)
    return "\n".join(paragraphs)


def extract_pdf_text(data: bytes) -> str:
    """Extract text from a PDF if ``pypdf`` is available, else a clear note."""

    try:
        from pypdf import PdfReader  # lazy: optional dependency
    except Exception:  # pragma: no cover - environment dependent
        logger.info("pypdf not installed; skipping PDF text extraction")
        return ""
    try:
        reader = PdfReader(io.BytesIO(data))
        return "\n".join((page.extract_text() or "") for page in reader.pages).strip()
    except Exception as exc:  # pragma: no cover - malformed file
        logger.warning("PDF extraction failed: %s", exc)
        return ""


def extract_text(data: bytes, *, filename: str | None = None, mime_type: str | None = None) -> str:
    """Best-effort plain-text extraction from raw bytes given a filename/mime hint."""

    name = (filename or "").lower()
    mime = (mime_type or "").lower()

    if name.endswith(".docx") or "wordprocessingml" in mime:
        try:
            return extract_docx_text(data)
        except Exception as exc:
            logger.warning("DOCX extraction failed: %s", exc)
            return ""
    if name.endswith(".pdf") or "pdf" in mime:
        return extract_pdf_text(data)

    # Plain text / markdown / unknown — decode defensively.
    try:
        text = data.decode("utf-8", errors="ignore")
    except Exception:  # pragma: no cover
        return ""
    # Strip control chars but keep newlines.
    return re.sub(r"[^\S\n]+", " ", text).strip()


def fetch_storage_text(storage_key: str, *, bucket: str | None = None) -> str:
    """Fetch an object from S3-compatible storage and extract its text."""

    from app.core.config import settings
    from app.core.storage import get_s3_client

    client = get_s3_client()
    obj = client.get_object(Bucket=bucket or settings.s3_bucket, Key=storage_key)
    data = obj["Body"].read()
    return extract_text(data, filename=storage_key)


__all__ = ["extract_text", "extract_docx_text", "extract_pdf_text", "fetch_storage_text"]
