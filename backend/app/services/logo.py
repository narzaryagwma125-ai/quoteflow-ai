"""Logo rendering helpers.

python-docx cannot embed SVG images directly, so SVG logos are rasterized to
PNG (with svglib + reportlab) before being inserted into a DOCX document.
Raster logos (PNG/JPEG/WebP) are passed through unchanged.
"""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path

logger = logging.getLogger("quoteflow")

SVG_MIME_TYPE = "image/svg+xml"


def svg_to_png(svg_bytes: bytes) -> bytes | None:
    """Rasterize SVG bytes to PNG.

    Returns ``None`` when the SVG cannot be rendered (the caller then falls
    back to showing the business name only).
    """
    from reportlab.graphics import renderPM
    from svglib.svglib import svg2rlg

    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".svg", delete=False) as handle:
            handle.write(svg_bytes)
            tmp_path = Path(handle.name)
        drawing = svg2rlg(str(tmp_path))
        if drawing is None:
            return None
        return renderPM.drawToString(drawing, fmt="PNG")
    except Exception:
        logger.exception("SVG logo rasterization failed; skipping logo.")
        return None
    finally:
        if tmp_path is not None:
            tmp_path.unlink(missing_ok=True)


def logo_bytes_for_docx(logo_bytes: bytes, content_type: str) -> bytes | None:
    """Return logo bytes safe to embed into a DOCX image.

    SVG logos are rasterized to PNG; raster formats pass through unchanged.
    Returns ``None`` when an SVG cannot be rasterized.
    """
    if content_type == SVG_MIME_TYPE:
        return svg_to_png(logo_bytes)
    return logo_bytes
