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


# ── Deterministic syllabus parsing (DeepT Stage 1 fallback) ───────────────────
#
# DeepT's Stage 1 (``stage1.service.ts``) leans on a live LLM to pull the course
# contract from raw syllabus text. Maestro must also work fully offline (the
# LLM-stub philosophy), so we port DeepT's *intent* — "extract CLOs verbatim" —
# into a deterministic heuristic. When a live model is configured these helpers
# act purely as a safety net; when it is stubbed they are what actually populates
# the CLO rows from an uploaded syllabus.

# A line that opens the "Course/Student/Intended Learning Outcomes" section.
_CLO_SECTION_HEADER = re.compile(
    r"^\s*(?:\d+[.)]\s*)?"
    r"(?:course\s+|student\s+|intended\s+|program\s+|module\s+)?"
    r"learning\s+outcomes?(?:\s*\(?\s*clos?\s*\)?)?\s*[:.\-\u2013\u2014]?\s*$",
    re.IGNORECASE,
)
# A bare "CLOs:" / "CLO:" header.
_CLOS_BARE_HEADER = re.compile(r"^\s*clos?\s*[:.\-]?\s*$", re.IGNORECASE)
# A heading that ends the CLO section.
_NEXT_SECTION_HEADER = re.compile(
    r"^\s*(?:\d+[.)]\s*)?"
    r"(?:weekly|week\b|schedule|assessment|grading|grade|evaluation|reference"
    r"|bibliograph|textbook|reading|prerequisite|description|overview|instructor"
    r"|policy|policies|topic|material|content|outline|method|delivery|attendance"
    r"|academic\s+integrity|office\s+hours|contact)\b",
    re.IGNORECASE,
)
# A list marker that introduces an outcome (bullet / number / "CLO1" / "a)").
_ITEM_MARKER = re.compile(
    r"^\s*(?:clo[\s\-_]?\d+[a-z]?|lo[\s\-_]?\d+|outcome\s*\d+|\d{1,2}|[a-z])"
    r"\s*[.):\-\u2022]\s+"
    r"|^\s*[\-\*\u2022\u00b7\u25cf\u25aa\u2023\u2043\u2219]\s+",
    re.IGNORECASE,
)
# The same markers, used to strip the prefix off a captured outcome line.
_ITEM_MARKER_STRIP = re.compile(
    r"^\s*(?:clo[\s\-_]?\d+[a-z]?|lo[\s\-_]?\d+|outcome\s*\d+)\s*[.):\-\u2022]?\s*"
    r"|^\s*(?:\d{1,2}|[a-z])\s*[.):\-]\s*"
    r"|^\s*[\-\*\u2022\u00b7\u25cf\u25aa\u2023\u2043\u2219]\s*",
    re.IGNORECASE,
)
# An inline "CLO1: ..." statement anywhere in the document (header-less fallback).
_INLINE_CLO = re.compile(r"^\s*clo[\s\-_]?\d+[a-z]?\s*[.):\-\u2022]?\s*(\S.*)$", re.IGNORECASE)

_COURSE_CODE = re.compile(r"\b([A-Z]{2,4})\s?-?\s?(\d{3,4}[A-Z]?)\b")
# "Credit Hours: 3" / "Credits - 4" (label then number).
_CREDIT_LABELLED = re.compile(
    r"(?:credit\s*hours?|credits?|units?|cr\.?\s*hrs?)\s*[:.\-=]?\s*(\d{1,2})\b",
    re.IGNORECASE,
)
# "3 credit hours" / "4 credits" (number then label, same line only).
_CREDIT_INLINE = re.compile(
    r"\b(\d{1,2})[ \t]*(?:credit\s*hours?|credits?|units?|cr\.?[ \t]*hrs?)\b",
    re.IGNORECASE,
)
_LABELLED = {
    "title": re.compile(r"^\s*(?:course\s+)?title\s*[:.\-]\s*(\S.*)$", re.IGNORECASE),
    "course_code": re.compile(r"^\s*(?:course\s+)?code\s*[:.\-]\s*(\S.*)$", re.IGNORECASE),
}

_MIN_CLO_LEN = 8  # ignore stray fragments that aren't real outcome statements


def _strip_marker(line: str) -> str:
    return _ITEM_MARKER_STRIP.sub("", line, count=1).strip()


def _collect_section_items(section_lines: list[str]) -> list[str]:
    """Collect outcome statements from the lines following a CLO header."""

    raw_items: list[str] = []
    started = False
    blank_streak = 0
    saw_marker = False
    for line in section_lines:
        stripped = line.strip()
        if not stripped:
            blank_streak += 1
            # Two blank lines after we've started a list usually ends the section.
            if started and blank_streak >= 2:
                break
            continue
        if started and _NEXT_SECTION_HEADER.match(stripped):
            break
        blank_streak = 0
        if _ITEM_MARKER.match(line):
            saw_marker = True
            started = True
            raw_items.append(_strip_marker(line))
        elif started and raw_items:
            # Continuation of a wrapped outcome (common in PDF text).
            raw_items[-1] = f"{raw_items[-1]} {stripped}".strip()
        elif not saw_marker:
            # No markers yet: tolerate plain-line outcome lists / intro lines.
            if _looks_like_intro(stripped):
                continue
            started = True
            raw_items.append(stripped)
    return [item for item in (i.strip() for i in raw_items) if len(item) >= _MIN_CLO_LEN]


def _looks_like_intro(line: str) -> bool:
    """True for boilerplate like 'Upon completion students will be able to:'."""

    low = line.lower()
    return low.endswith(":") and (
        "able to" in low or "will be able" in low or "students will" in low
    )


def _collect_inline_clos(lines: list[str]) -> list[str]:
    out: list[str] = []
    for line in lines:
        m = _INLINE_CLO.match(line)
        if m:
            text = m.group(1).strip()
            if len(text) >= _MIN_CLO_LEN:
                out.append(text)
    return out


def extract_clos_from_text(text: str, *, limit: int = 60) -> list[str]:
    """Extract Course Learning Outcomes verbatim from raw syllabus text.

    Ports the *intent* of DeepT's Stage 1 extraction (CLOs as a plain ``string[]``
    copied as written) into a deterministic, dependency-free heuristic so CLOs are
    recovered even when the LLM is offline/stubbed. Returns an ordered, de-duped
    list of statement strings.
    """

    if not text or not text.strip():
        return []
    lines = text.splitlines()

    clos: list[str] = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
        is_header = (
            _CLO_SECTION_HEADER.match(stripped)
            or _CLOS_BARE_HEADER.match(stripped)
            or _looks_like_intro(stripped)
        )
        if is_header:
            clos = _collect_section_items(lines[i + 1 :])
            if clos:
                break

    # Header-less fallback: pick up "CLO1: ..." statements anywhere in the doc.
    if not clos:
        clos = _collect_inline_clos(lines)

    seen: set[str] = set()
    deduped: list[str] = []
    for clo in clos:
        key = clo.lower()
        if key not in seen:
            seen.add(key)
            deduped.append(clo)
        if len(deduped) >= limit:
            break
    return deduped


def _find_labelled(lines: list[str], pattern: re.Pattern[str]) -> str | None:
    for line in lines:
        m = pattern.match(line)
        if m:
            value = m.group(1).strip()
            if value:
                return value
    return None


def extract_course_contract(text: str, *, title: str | None = None) -> dict:
    """Best-effort course contract from raw syllabus text (DeepT Stage 1 shape).

    Returns ``{course_code, title, description, credit_hours, clos, gaps}`` where
    ``clos`` is a verbatim ``list[str]`` (the shape ``_normalize_clos`` accepts).
    Used as the offline fallback for the Course Intake stage.
    """

    text = text or ""
    lines = text.splitlines()
    clos = extract_clos_from_text(text)

    found_title = _find_labelled(lines, _LABELLED["title"])
    course_code = _find_labelled(lines, _LABELLED["course_code"])
    if not course_code:
        m = _COURSE_CODE.search(text)
        if m:
            course_code = f"{m.group(1)} {m.group(2)}"

    credit_hours: int | None = None
    cm = _CREDIT_LABELLED.search(text) or _CREDIT_INLINE.search(text)
    if cm:
        try:
            credit_hours = int(cm.group(1))
        except ValueError:
            credit_hours = None

    gaps: list[str] = []
    if not clos:
        gaps.append("No Course Learning Outcomes found in the syllabus text.")

    return {
        "course_code": course_code,
        "title": found_title or title,
        "description": None,
        "credit_hours": credit_hours,
        "clos": clos,
        "gaps": gaps,
    }


__all__ = [
    "extract_text",
    "extract_docx_text",
    "extract_pdf_text",
    "fetch_storage_text",
    "extract_clos_from_text",
    "extract_course_contract",
]
