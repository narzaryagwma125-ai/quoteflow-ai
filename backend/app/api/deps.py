"""Shared FastAPI dependencies: auth, authorization, pagination, CSRF, rate limits."""

from __future__ import annotations

from fastapi import Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import forbidden, unauthorized
from app.db.session import get_db
from app.models.user import User
from app.security.rate_limit import client_ip_key, enforce
from app.security.sessions import resolve_session
from app.services.subscription import require_plan_feature

MAX_PAGE_SIZE = 100


async def get_current_user(request: Request, db: AsyncSession = Depends(get_db)) -> User:
    token = request.cookies.get(settings.session_cookie_name)
    session = await resolve_session(db, token)
    if session is None:
        raise unauthorized("Not authenticated.")
    user = await db.get(User, session.user_id)
    if user is None or not user.is_active:
        raise unauthorized("Account unavailable.")
    return user


def client_ip(request: Request) -> str:
    return client_ip_key(request)


async def enforce_rate_limit(
    request: Request,
    action: str,
    limit: int,
    window_seconds: int = 3600,
) -> None:
    await enforce(client_ip_key(request), action, limit, window_seconds)


async def require_quote_access(user: User = Depends(get_current_user)) -> User:
    return user


async def require_ai(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> User:
    await require_plan_feature(db, user, "ai")
    return user


async def require_quotes(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> User:
    await require_plan_feature(db, user, "quotes")
    return user


def verify_origin(request: Request) -> None:
    """Reject cross-origin state-changing requests unless the origin is allowed.

    Combined with SameSite cookies this blocks CSRF. Cookies are never shared
    cross-origin thanks to SameSite=Lax and this check.
    """
    method = request.method.upper()
    if method in ("GET", "HEAD", "OPTIONS"):
        return
    origin = request.headers.get("origin")
    if not origin:
        return  # non-browser clients; SameSite still protects cookies
    allowed = list(settings.cors_origins)
    try:
        request_host = request.headers.get("host", "")
    except Exception:
        request_host = ""
    if origin in allowed or (origin and request_host and origin.split("://")[-1] == request_host):
        return
    raise forbidden("Cross-origin request rejected.")


async def pagination_params(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=MAX_PAGE_SIZE),
    q: str | None = Query(default=None, max_length=200),
    sort: str = Query(default="created_at", max_length=40),
    order: str = Query(default="desc", pattern="^(asc|desc)$"),
) -> dict:
    return {"page": page, "page_size": page_size, "q": q, "sort": sort, "order": order}
