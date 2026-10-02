"""Placeholder for background workers (e.g. quote expiry, follow-up reminders).

The MVP does not send automated messages; reminders are surfaced in-app only.
"""

from __future__ import annotations

import logging

logger = logging.getLogger("quoteflow.workers")


def placeholder() -> None:
    """Workers are integrated via the task orchestrator in a later phase."""
    logger.info("workers module loaded")
