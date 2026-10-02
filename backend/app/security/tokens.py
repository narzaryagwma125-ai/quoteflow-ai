"""Token generation and hashing utilities.

Only cryptographic hashes of tokens are stored in the database.
Never log tokens.
"""

from __future__ import annotations

import hashlib
import secrets


def generate_token(byte_length: int = 32) -> str:
    """Generate a high-entropy URL-safe random token."""
    return secrets.token_urlsafe(byte_length)


def generate_public_quote_token() -> str:
    """High-entropy token for customer-facing quote links (256 bits)."""
    return generate_token(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def hash_ip(ip: str) -> str:
    """Stable one-way hash of an IP for audit metadata."""
    return hashlib.sha256(ip.encode("utf-8")).hexdigest()[:32]
