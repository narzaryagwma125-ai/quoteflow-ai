"""DOCX → PDF conversion using a headless office suite (LibreOffice).

Detects a converter at import time.  When none is available, conversion is
reported as unavailable so the API can return a clear backend error instead of
producing a broken PDF.  The default QuoteFlow template never depends on this.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

logger = logging.getLogger("quoteflow")

_SOFFICE_CANDIDATES = [
    "soffice",
    "libreoffice",
    "soffice.exe",
    "libreoffice.exe",
    r"C:\Program Files\LibreOffice\program\soffice.exe",
    r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
]


def _find_soffice() -> str | None:
    for candidate in _SOFFICE_CANDIDATES:
        if os.path.isfile(candidate):
            return candidate
        found = shutil.which(candidate)
        if found:
            return found
    return None


_SOFFICE_PATH = _find_soffice()


def is_converter_available() -> bool:
    """True when a DOCX→PDF converter (LibreOffice) is installed and reachable."""
    return _SOFFICE_PATH is not None


class DocxConversionError(Exception):
    pass


class DocxConversionUnavailable(DocxConversionError):
    def __init__(self) -> None:
        super().__init__(
            "DOCX-to-PDF conversion is not available. Install LibreOffice on the "
            "server and restart the backend, or use the default QuoteFlow template."
        )


def convert_docx_to_pdf(docx_bytes: bytes) -> bytes:
    """Convert a DOCX document to PDF bytes using LibreOffice headless mode."""
    if _SOFFICE_PATH is None:
        raise DocxConversionUnavailable()

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        docx_path = tmp / "input.docx"
        docx_path.write_bytes(docx_bytes)

        out_dir = tmp / "output"
        out_dir.mkdir()

        result = subprocess.run(
            [
                _SOFFICE_PATH,
                "--headless",
                "--nolockcheck",
                "--convert-to",
                "pdf",
                "--outdir",
                str(out_dir),
                str(docx_path),
            ],
            capture_output=True,
            timeout=90,
        )

        pdf_path = out_dir / "input.pdf"
        if result.returncode != 0 or not pdf_path.exists():
            stderr = result.stderr.decode("utf-8", errors="replace")[-500:]
            raise DocxConversionError(
                f"LibreOffice conversion failed (exit {result.returncode}): {stderr}"
            )

        return pdf_path.read_bytes()
