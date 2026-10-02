"""File upload handling with strict validation.

Logos are validated by magic-bytes signature, given safe random filenames,
and stored outside any executable directory.  Custom DOCX quotation templates
are validated for MIME type, ZIP/DOCX magic, size, and python-docx parseability.
Original filenames are never trusted.
"""

from __future__ import annotations

import io
import re
import secrets
import xml.etree.ElementTree as ET
from pathlib import Path

from fastapi import UploadFile

from app.core.config import settings
from app.core.errors import bad_request, payload_too_large, unprocessable, unsupported_media

# ── Logos ──────────────────────────────────────────────────────────────
# tuple[signature, length] for magic-byte validation; SVG is validated by XML
# parsing instead (no fixed binary signature).
ALLOWED_TYPES: dict[str, tuple[tuple[bytes, int] | None, str]] = {
    "image/png": ((b"\x89PNG\r\n\x1a\n", 8), ".png"),
    "image/jpeg": ((b"\xff\xd8\xff", 3), ".jpg"),
    "image/webp": ((b"RIFF", 4), ".webp"),
    "image/svg+xml": (None, ".svg"),
}
_ALLOWED_LOGO_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".svg"}
MAX_LOGOS_PER_USER = 3

# ── Custom quotation templates (DOCX only) ────────────────────────────
DOCX_MIME_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
MAX_TEMPLATE_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB

# Only printable characters are allowed in an original filename.
_SAFE_FILENAME_RE = re.compile(r"[^\w .\-()]+", re.UNICODE)


def safe_original_name(name: str | None, fallback: str) -> str:
    """Sanitize a client-provided filename: strip path separators, control
    characters, and empty it down to a safe stub. Never used for storage."""
    if not name:
        return fallback
    # Reject path traversal outright; a split filename is never a path.
    name = _SAFE_FILENAME_RE.sub("", name or "").strip(" .")
    name = name[:150]
    if not name or name in (".", ".."):
        return fallback
    return name


def _upload_dir() -> Path:
    path = Path(settings.upload_dir).resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path


def safe_stored_name(extension: str) -> str:
    return f"{secrets.token_hex(16)}{extension}"


# ── Logo helpers ──────────────────────────────────────────────────────
def _validate_svg(data: bytes) -> bool:
    """Strict SVG validation.

    Rejects DTD/entity declarations (possible XXE / entity-expansion bombs)
    and any script/foreign content, event handler attributes, or external
    hrefs/srcs.
    """
    head = data.lower()
    if b"<!doctype" in head or b"<!entity" in head:
        return False
    try:
        root = ET.fromstring(data)
    except ET.ParseError:
        return False
    if root.tag.rsplit("}", 1)[-1].lower() != "svg":
        return False
    for elem in root.iter():
        tag = (elem.tag.rsplit("}", 1)[-1] or "").lower()
        if tag in {"script", "foreignobject", "iframe", "embed", "object"}:
            return False
        for key, value in elem.attrib.items():
            k = (key.rsplit("}", 1)[-1] or "").lower()
            lowered = value.strip().lower()
            if k.startswith("on"):
                return False
            if k in ("href", "xlink:href", "src", "action") and lowered.startswith(
                ("http:", "https:", "//", "javascript:", "file:", "data:text/html", "data:application")
            ):
                return False
    return True


def validate_logo(file: UploadFile) -> tuple[str, bytes, int]:
    """Validate MIME + extension + content. Returns (content_type, data, size).

    Errors are 400 (bad_request). SVG content is validated structurally, not
    by magic bytes.
    """
    declared = (file.content_type or "").lower()
    if declared not in ALLOWED_TYPES:
        raise bad_request("Logo must be a PNG, JPEG, WebP, or SVG image.")

    filename = (file.filename or "").lower()
    if "." not in filename or ("." + filename.rsplit(".", 1)[1]) not in _ALLOWED_LOGO_EXTENSIONS:
        raise bad_request("Logo must have a .png, .jpg, .jpeg, .webp, or .svg extension.")

    data = file.file.read(settings.max_logo_size_bytes + 1)
    if len(data) > settings.max_logo_size_bytes:
        raise bad_request("Logo file is too large (max 2 MB).")
    if not data:
        raise bad_request("Logo file is empty.")

    if declared == "image/svg+xml":
        if not _validate_svg(data):
            raise bad_request("Logo SVG file is invalid or contains disallowed content.")
        return declared, data, len(data)

    (signature, sig_len), _ext = ALLOWED_TYPES[declared]
    if not data[:sig_len] == signature:
        raise bad_request("Logo file content does not match its declared type.")

    if declared == "image/webp":
        # WebP files are RIFF containers; verify the WEBP FOURCC at offset 8.
        if len(data) < 12 or data[8:12] != b"WEBP":
            raise bad_request("Logo file is not a valid WebP image.")

    # reject anything that tries to smuggle SVG/HTML/scripts into rasters
    low = data[:1024].lower()
    for marker in (b"<svg", b"<script", b"<?php", b"%pdf"):
        if marker in low:
            raise bad_request("Logo file content rejected.")

    return declared, data, len(data)


def store_logo(content_type: str, data: bytes) -> Path:
    ext = ALLOWED_TYPES[content_type][1]
    stored = _upload_dir() / safe_stored_name(ext)
    stored.write_bytes(data)
    return stored


def read_logo(stored_name: str) -> bytes | None:
    path = _upload_dir() / stored_name
    if not path.exists() or not path.is_file():
        return None
    return path.read_bytes()


def delete_logo(stored_name: str) -> None:
    path = _upload_dir() / stored_name
    if path.exists() and path.is_file():
        path.unlink()


# ── Template helpers (DOCX only) ──────────────────────────────────────
def validate_template(file: UploadFile) -> tuple[str, bytes, int]:
    """Validate a custom DOCX template upload.

    Checks declared MIME type, file extension, ZIP/DOCX magic bytes,
    and python-docx parseability.  Returns (content_type, data, size).
    Raises HTTPException: 415 for wrong type, 413 for oversized, 422 for
    empty/corrupted content.
    """
    filename = (file.filename or "").lower()
    if not filename.endswith(".docx"):
        raise unsupported_media("Template must be a .docx file.")

    declared = (file.content_type or "").lower()
    if declared != DOCX_MIME_TYPE:
        raise unsupported_media("Template must be a DOCX file.")

    data = file.file.read(MAX_TEMPLATE_SIZE_BYTES + 1)
    if len(data) > MAX_TEMPLATE_SIZE_BYTES:
        raise payload_too_large("Template file is too large (max 5 MB).")
    if not data:
        raise unprocessable("Template file is empty.")

    # Verify ZIP / DOCX magic signature.
    if len(data) < 4 or data[:4] != b"PK\x03\x04":
        raise unsupported_media("Template file content does not match its declared type.")

    # Verify python-docx can actually parse the file (catches corruption).
    try:
        from docx import Document

        Document(io.BytesIO(data))
    except Exception:
        raise unprocessable("Template file is corrupted or not a valid DOCX.") from None

    # Reject anything that tries to smuggle HTML/scripts/executables.
    low = data[:2048].lower()
    for marker in (b"<script", b"<?php", b"#!/bin/", b"<html", b"<body"):
        if marker in low:
            raise unsupported_media("Template file content rejected.")

    return declared, data, len(data)


def store_template(content_type: str, data: bytes) -> Path:
    stored = _upload_dir() / safe_stored_name(".docx")
    stored.write_bytes(data)
    return stored


def read_template(stored_name: str) -> bytes | None:
    return read_logo(stored_name)


def delete_template(stored_name: str) -> None:
    delete_logo(stored_name)
