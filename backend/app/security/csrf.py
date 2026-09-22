"""Double-submit cookie CSRF protection.

Used for state-changing public-quote actions, where the double-submit cookie
pattern works without server-side state: the server sets a random cookie when
the public page is loaded and requires that same value be echoed back in the
X-CSRF-Token header. Cross-origin attackers cannot read another origin's cookies.
"""

from __future__ import annotations

import secrets

from starlette.requests import Request

from app.core.errors import forbidden

CSRF_COOKIE = "quoteflow_csrf"
CSRF_HEADER = "x-csrf-token"


def new_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def set_csrf_cookie(response, request: Request) -> None:
    token = new_csrf_token()
    response.set_cookie(
        key=CSRF_COOKIE,
        value=token,
        max_age=3600,
        httponly=False,
        secure=request.url.scheme == "https",
        samesite="lax",
        path="/",
    )


def verify_double_submit(request: Request) -> bool:
    """Compare the X-CSRF-Token header against the CSRF cookie value."""
    cookie = request.cookies.get(CSRF_COOKIE)
    header = request.headers.get(CSRF_HEADER)
    if not cookie or not header:
        return False
    return secrets.compare_digest(cookie, header)


def require_csrf(request: Request) -> None:
    if not verify_double_submit(request):
        raise forbidden("CSRF validation failed.")
