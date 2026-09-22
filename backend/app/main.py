from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.router import api_router
from app.core.config import settings
from app.core.logging import setup_logging
from app.core.security_headers import SecurityHeadersMiddleware

setup_logging(settings.log_level)
logger = logging.getLogger("quoteflow")

MAX_BODY_BYTES = max(
    1_000_000,
    settings.max_logo_size_bytes + 512 * 1024,
    # Custom quote templates may be up to 5 MB; allow multipart overhead on top.
    5 * 1024 * 1024 + 512 * 1024,
)

app = FastAPI(
    title="QuoteFlow AI API",
    version="0.1.0",
    description="Secure backend for QuoteFlow AI — quotation management for cleaning businesses.",
    docs_url="/api/docs" if not settings.is_production else None,
    redoc_url=None,
    openapi_url="/api/openapi.json" if not settings.is_production else None,
)

# Restricted CORS — explicit allowed origins only, credentials enabled. Never "*".
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-CSRF-Token"],
)


class BodySizeLimitMiddleware:
    """Reject oversized request bodies before they are parsed."""

    def __init__(self, app, max_bytes: int):
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        for header, value in scope.get("headers", []):
            if header == b"content-length":
                try:
                    if int(value) > self.max_bytes:
                        response = JSONResponse(
                            status_code=413, content={"detail": "Request body too large."}
                        )
                        await response(scope, receive, send)
                        return
                except (TypeError, ValueError):
                    pass
        await self.app(scope, receive, send)


app.add_middleware(BodySizeLimitMiddleware, max_bytes=MAX_BODY_BYTES)
app.add_middleware(SecurityHeadersMiddleware)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    # Never leak stack traces or internal details in any environment.
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error."})


app.include_router(api_router)


@app.get("/")
async def root() -> dict:
    return {"service": "QuoteFlow AI API", "health": "/api/health", "docs": "/api/docs" if not settings.is_production else None}
