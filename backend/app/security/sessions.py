"""Server-managed session handling.

The client only ever holds a random opaque session token in an HTTP-only cookie.
The database stores only its SHA-256 hash. Revoking the session means deleting the row.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.session import UserSession
from app.security.tokens import generate_token, hash_token


def session_cookie_name() -> str:
    return settings.session_cookie_name


def create_session_token() -> str:
    return generate_token(32)


def new_session_expiry() -> datetime:
    return datetime.now(UTC) + timedelta(days=settings.session_lifetime_days)


async def store_session(db: AsyncSession, user_id: int, token: str, expires_at: datetime) -> UserSession:
    session = UserSession(user_id=user_id, token_hash=hash_token(token), expires_at=expires_at)
    db.add(session)
    await db.flush()
    return session


async def resolve_session(db: AsyncSession, token: str | None) -> UserSession | None:
    """Return a valid session for the given raw token, or None."""
    if not token:
        return None
    token_hash = hash_token(token)
    result = await db.execute(select(UserSession).where(UserSession.token_hash == token_hash))
    session = result.scalar_one_or_none()
    if session is None:
        return None
    now = datetime.now(UTC)
    expiry = session.expires_at
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=UTC)
    if expiry <= now:
        await db.delete(session)
        await db.commit()
        return None
    return session


async def revoke_session(db: AsyncSession, token: str | None) -> None:
    if not token:
        return
    await db.execute(delete(UserSession).where(UserSession.token_hash == hash_token(token)))
    await db.commit()


async def revoke_all_user_sessions(db: AsyncSession, user_id: int) -> None:
    await db.execute(delete(UserSession).where(UserSession.user_id == user_id))
    await db.commit()
