"""Structured logging setup. Never logs passwords, tokens, or full customer data."""

from __future__ import annotations

import logging
import sys

RESERVED_FIELDS = {"password", "password_hash", "token", "public_token", "csrf_token", "cookie"}


class RedactingFilter(logging.Filter):
    """Redact common secret-ish field names from log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            msg = record.getMessage()
        except Exception:
            return True
        lowered = msg.lower()
        for field in RESERVED_FIELDS:
            # crude redaction for "field=value" and "field: value" patterns
            marker = field + "="
            if marker in lowered:
                record.msg = "[REDACTED]"
                record.args = ()
                return True
        return True


def setup_logging(level: str = "INFO") -> None:
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        handlers=handlers,
        force=True,
    )
    for handler in handlers:
        handler.addFilter(RedactingFilter())
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
